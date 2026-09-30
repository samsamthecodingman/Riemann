// map.js
// -----------------------------------------------------------------------
// The spatial view: a region map of one document that mirrors the reader
// (docs/spatial-view-spec.md). Rectangles come from maplayout.js and never
// depend on the reader's zoom; this file draws whatever the reader has
// open (expanded nodes become frames, frontier nodes become solid tiles),
// outlines what is on screen, and owns the map's own camera.
//
// Camera: zooming re-runs the layout at (W*s, H*s) and translates, rather
// than CSS-scaling, so text stays the same size and tiles gain room for
// longer labels (semantic zoom).
// -----------------------------------------------------------------------
(function () {
  "use strict";

  const STORE_KEY = "riemann:map";
  const MIN_S = 1;
  const MAX_S = 6;
  const wideMQ = window.matchMedia("(min-width: 1100px)");
  // The map panel switches from compact ("key titles") to full density at
  // this pixel width. Chosen from the panel's current width, so dragging the
  // column handle changes it live.
  const FULL_MIN_W = 520;

  let api = null;
  let $app, $panel, $frame, $world, $sub, $btn, $pill;
  let isOpen = false;
  let s = 1;
  let ox = 0;
  let oy = 0;
  let W = 0;
  let H = 0;
  let treeId = null;
  let lay = null; // Map<id, rect> for the current (W*s, H*s)
  let layKey = "";
  let density = "compact";
  let drawn = []; // tiles in paint order: {key, id, kind, r}
  let drawnById = new Map(); // node id -> tile
  const els = new Map(); // tile key -> button
  let redrawQueued = false;
  let hereTimer = null;
  let zoomLogTimer = null;
  let lastHereKeys = "";

  const esc = (t) => (t == null ? "" : String(t)).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function readStore() {
    try {
      return localStorage.getItem(STORE_KEY) === "1";
    } catch (e) {
      return false;
    }
  }
  function writeStore(v) {
    try {
      localStorage.setItem(STORE_KEY, v ? "1" : "0");
    } catch (e) {}
  }

  // ------------------------------------------------------------------
  // Short-title backfill: trees built before `short_title` existed get their
  // key titles from one batched call (POST /api/tree/{id}/short-titles), once
  // per tree per session. Failures are silent; the map keeps the heuristic
  // key titles.
  // ------------------------------------------------------------------
  const backfillTried = new Set();
  const BACKFILL_KEY = (id) => `riemann:short-titles:${id}`;

  function maybeBackfill() {
    const tree = api.getTree();
    if (!tree || !isOpen || backfillTried.has(tree.id)) return;
    const secs = api.sectionsOf(tree);
    if (!secs.length || secs.every((id) => tree.nodes[id] && tree.nodes[id].short_title)) return;
    try {
      if (localStorage.getItem(BACKFILL_KEY(tree.id)) === "1") return;
    } catch (e) {}
    backfillTried.add(tree.id);
    fetch(`/api/tree/${encodeURIComponent(tree.id)}/short-titles`, { method: "POST" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || !data.titles) return;
        const cur = api.getTree();
        if (!cur || cur.id !== tree.id) return;
        for (const [id, t] of Object.entries(data.titles)) if (cur.nodes[id] && !cur.nodes[id].short_title) cur.nodes[id].short_title = t;
        try {
          localStorage.setItem(BACKFILL_KEY(tree.id), "1");
        } catch (e) {}
        lay = null;
        layKey = "";
        for (const b of els.values()) b._sig = null;
        scheduleRedraw();
      })
      .catch(() => {});
  }

  // ------------------------------------------------------------------
  // Geometry helpers
  // ------------------------------------------------------------------
  function measure() {
    const w = $frame.clientWidth;
    const h = $frame.clientHeight;
    const changed = Math.abs(w - W) > 0.5 || Math.abs(h - H) > 0.5;
    W = w;
    H = h;
    return changed;
  }

  function clampCamera() {
    ox = clamp(ox, Math.min(0, W - W * s), 0);
    oy = clamp(oy, Math.min(0, H - H * s), 0);
  }

  function applyCamera() {
    $world.style.transform = `translate(${ox}px, ${oy}px)`;
    stickLabels();
  }

  // A tile bigger than the view keeps its label in sight: when its top or left
  // edge is scrolled out of the frame, the label slides in (never out of the
  // tile). Frames are left alone: their label sits over their children's
  // header strip.
  function stickLabels() {
    const topEdge = -oy;
    const leftEdge = -ox;
    for (const t of drawn) {
      if (t.kind === "frame" || t.kind === "sec-frame") continue;
      const b = els.get(t.key);
      if (!b) continue;
      let sy = 0;
      let sx = 0;
      if (t.r.y < topEdge && t.r.y + t.r.h > topEdge) sy = clamp(topEdge - t.r.y, 0, Math.max(0, t.r.h - (b._lh || 0) - 20));
      if (t.r.x < leftEdge && t.r.x + t.r.w > leftEdge) sx = clamp(leftEdge - t.r.x, 0, Math.max(0, t.r.w - (b._lw || 0) - 28));
      sy = Math.round(sy);
      sx = Math.round(sx);
      if (b._sy !== sy || b._sx !== sx) {
        b._sy = sy;
        b._sx = sx;
        b.firstChild.style.transform = sx || sy ? `translate(${sx}px, ${sy}px)` : "";
      }
    }
  }

  function computeDensity() {
    const pw = $panel.offsetWidth;
    return pw >= FULL_MIN_W ? "full" : "compact";
  }

  function getLayout() {
    const tree = api.getTree();
    const key = `${tree.id}|${Math.round(W * s * 10)}|${Math.round(H * s * 10)}|${density}`;
    if (key !== layKey || !lay) {
      lay = window.MapLayout.layout(tree, W * s, H * s, { titleOf: (n) => api.nodeTitle(n), density });
      layKey = key;
    }
    return lay;
  }

  // ------------------------------------------------------------------
  // What to draw
  // ------------------------------------------------------------------
  function expandedSet(tree) {
    const set = new Set();
    for (const id of api.getFrontier()) {
      let p = tree.nodes[id] && tree.nodes[id].parent;
      while (p && !set.has(p)) {
        set.add(p);
        p = tree.nodes[p] && tree.nodes[p].parent;
      }
    }
    return set;
  }

  function topLevelIds(tree) {
    const secs = api.sectionsOf(tree);
    if (secs.length) return secs;
    const root = tree.nodes[tree.root];
    return root && root.children.length ? root.children : [tree.root];
  }

  function collectTiles(tree, L) {
    const open = expandedSet(tree);
    const tiles = [];
    const secs = topLevelIds(tree);
    const walk = (id, level) => {
      const r = L.get(id);
      const n = tree.nodes[id];
      if (!r || !n) return;
      const kids = n.children || [];
      const expanded = open.has(id) && kids.length > 0 && L.has(kids[0]);
      let kind;
      if (level === 0) kind = expanded ? "sec-frame" : "sec-solid";
      else if (n.is_leaf) kind = "leaf";
      else kind = expanded ? "frame" : "solid";
      tiles.push({ key: `${id}:${kind}`, id, kind, level, r, node: n });
      if (expanded) for (const c of kids) walk(c, level + 1);
    };
    for (const id of secs) walk(id, 0);
    return tiles;
  }

  function slotOf(tree, id) {
    const secs = api.sectionsOf(tree);
    const sec = api.sectionAncestor(tree, id);
    const idx = sec ? secs.indexOf(sec) : 0;
    return (Math.max(0, idx) % 5) + 1;
  }

  function nn(i) {
    return String(i + 1).padStart(2, "0");
  }

  // ------------------------------------------------------------------
  // Label variants, best first. Each tile is fitted by trying them in
  // order and keeping the first that fits its box whole. If none does, the
  // one-line key title is cut at a word boundary with an ellipsis (`trunc`);
  // failing that the tile shows no text (or, for a district, just its numeral).
  // Text is never clipped mid-word.
  // ------------------------------------------------------------------
  function titleOf(n) {
    return api.nodeTitle(n);
  }

  function keyOf(n) {
    return window.MapLayout.keyTitle(n, titleOf(n));
  }

  function partVariants(tile) {
    const n = tile.node;
    const title = titleOf(n);
    const key = keyOf(n);
    if (density === "compact") {
      const line = (t) => `<span class="map-line">${esc(t)}</span>`;
      return { list: [line(key), ""], trunc: { text: key, html: line } };
    }
    const prov = tile.kind === "leaf" ? api.nodeProvenance(n) : "";
    const pre = prov ? `<span class="map-prov">${esc(prov)}</span> ` : "";
    const line = (t) => `${pre}<span class="map-line">${esc(t)}</span>`;
    const list = [];
    list.push(`${pre}<span class="map-title">${esc(title)}</span>`);
    if (n.short_title && n.short_title !== title) list.push(`${pre}<span class="map-title">${esc(n.short_title)}</span>`);
    list.push(line(key));
    return { list, trunc: { text: key, html: line }, tail: prov ? [`<span class="map-prov">${esc(prov)}</span>`, ""] : [""] };
  }

  function sectionVariants(tile, tree) {
    const n = tile.node;
    const secs = api.sectionsOf(tree);
    const i = Math.max(0, secs.indexOf(tile.id));
    const title = titleOf(n);
    const key = keyOf(n);
    const num = `<span class="map-num">${nn(i)}</span>`;
    const t = (x) => `<span class="map-title">${esc(x)}</span>`;
    if (density === "compact") {
      return { list: [`${num}${t(key)}`], trunc: { text: key, html: (x) => `${num}${t(x)}` }, tail: [num, ""] };
    }
    const words = window.MapLayout.wordsInSource(tree).get(tile.id) || n.words || 0;
    const parts = (n.children || []).length;
    const meta = parts ? `${parts} part${parts === 1 ? "" : "s"} · ${Math.round(words).toLocaleString()} words` : `${Math.round(words).toLocaleString()} words`;
    const m = `<span class="map-meta">${esc(meta)}</span>`;
    const list = [];
    if (tile.kind === "sec-solid" && n.hook) list.push(`${num}${t(title)}${m}<span class="map-hook">${esc(n.hook)}</span>`);
    list.push(`${num}${t(title)}${m}`);
    list.push(`${num}${t(title)}`);
    if (n.short_title && n.short_title !== title) list.push(`${num}${t(n.short_title)}`);
    else if (key !== title) list.push(`${num}${t(key)}`);
    return { list, trunc: { text: key, html: (x) => `${num}${t(x)}` }, tail: [num, ""] };
  }

  // Box (in px) the label may occupy, and the label's width.
  function labelBox(tile) {
    const { r } = tile;
    const c = density === "compact";
    if (tile.kind === "sec-solid") return c ? { w: r.w - 24, h: r.h - 16 } : { w: r.w - 28, h: r.h - 22 };
    if (tile.kind === "sec-frame") {
      const hw = r.side ? Math.min(200, 0.35 * r.w) : r.w;
      if (c) return { w: hw - 24, h: r.side ? r.h - 16 : r.headerH - 16 };
      return { w: hw - 28, h: r.side ? r.h - 22 : r.headerH - 22 };
    }
    if (tile.kind === "frame") {
      const hw = r.side ? Math.min(200, 0.35 * r.w) : r.w;
      return { w: hw - 20, h: r.side ? r.h - 16 : r.headerH - 12 };
    }
    const padv = r.h >= 44 ? 8 : 4;
    return { w: r.w - 20, h: r.h - 2 * padv };
  }

  // ------------------------------------------------------------------
  // DOM reconcile
  // ------------------------------------------------------------------
  function makeTile(tile) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "map-tile";
    b.dataset.nodeId = tile.id;
    const label = document.createElement("span");
    label.className = tile.kind.startsWith("sec") ? "map-head" : "map-label";
    b.appendChild(label);
    return b;
  }

  function styleTile(b, tile, tree) {
    const { r, kind } = tile;
    const isSec = kind.startsWith("sec");
    b.className = `map-tile map-${kind}${b.classList.contains("here") ? " here" : ""}`;
    b.style.left = `${r.x}px`;
    b.style.top = `${r.y}px`;
    b.style.width = `${r.w}px`;
    b.style.height = `${r.h}px`;
    const slot = slotOf(tree, tile.id);
    if (isSec || kind === "leaf") b.style.background = `var(--sec-${slot})`;
    else b.style.background = "";
    const title = titleOf(tile.node);
    if (isSec) {
      const secs = api.sectionsOf(tree);
      b.setAttribute("aria-label", `Section ${nn(Math.max(0, secs.indexOf(tile.id)))}: ${title}`);
    } else {
      b.setAttribute("aria-label", title);
    }
    b.style.padding = isSec ? "0" : r.h >= 44 || kind === "frame" ? "8px 10px" : "4px 10px";
    const label = b.firstChild;
    const box = labelBox(tile);
    label.style.width = `${Math.max(0, box.w)}px`;
    label.style.maxHeight = `${Math.max(0, box.h)}px`;
  }

  function redraw() {
    redrawQueued = false;
    if (!isOpen || !api.getTree()) return;
    const tree = api.getTree();
    if (treeId !== tree.id) {
      treeId = tree.id;
      s = 1;
      ox = oy = 0;
      lay = null;
      layKey = "";
    }
    measure();
    if (W < 20 || H < 20) return;
    const nd = computeDensity();
    if (nd !== density) {
      density = nd;
      lay = null;
      for (const b of els.values()) b._sig = null;
    }
    $panel.classList.toggle("compact", density === "compact");
    clampCamera();
    const L = getLayout();
    drawn = collectTiles(tree, L);
    drawnById = new Map(drawn.map((t) => [t.id, t]));

    // reconcile
    const want = new Set();
    const refit = [];
    let order = 0;
    for (const tile of drawn) {
      want.add(tile.key);
      let b = els.get(tile.key);
      const fresh = !b;
      if (fresh) {
        b = makeTile(tile);
        els.set(tile.key, b);
      }
      const box = labelBox(tile);
      const sig = `${density}|${Math.round(tile.r.w * 10)}|${Math.round(tile.r.h * 10)}|${Math.round(tile.r.headerH)}|${tile.r.side}|${box.w > 0}`;
      const changed = b._sig !== sig;
      if (changed || fresh || b._x !== tile.r.x || b._y !== tile.r.y) {
        styleTile(b, tile, tree);
        b._x = tile.r.x;
        b._y = tile.r.y;
      }
      if (changed || fresh) {
        b._sig = sig;
        b._tile = tile;
        refit.push({ b, tile, v: tile.kind.startsWith("sec") ? sectionVariants(tile, tree) : partVariants(tile) });
      } else {
        b._tile = tile;
      }
      // paint order == DOM order
      if ($world.children[order] !== b) $world.insertBefore(b, $world.children[order] || null);
      order += 1;
    }
    for (const [key, b] of els) {
      if (!want.has(key)) {
        b.remove();
        els.delete(key);
      }
    }
    fitLabels(refit);
    applyCamera();
    updateSubtitle(tree);
    lastHereKeys = "";
    applyHere();
  }

  const overflows = (l) => l.scrollHeight > l.clientHeight + 0.5 || l.scrollWidth > l.clientWidth + 0.5;

  // Try each label variant in order; keep the first that fits its box whole.
  // Otherwise cut the key title at a word boundary (binary search on the word
  // count), otherwise fall back to the tail (numeral / provenance / nothing).
  function fitOne(e) {
    const l = e.b.firstChild;
    const { list, trunc, tail } = e.v;
    for (const html of list) {
      l.innerHTML = html;
      if (!overflows(l)) return;
    }
    if (trunc) {
      const words = trunc.text.split(/\s+/).filter(Boolean);
      const cutHtml = (k) => trunc.html(words.slice(0, k).join(" ").replace(/[\s,;:.\-\u2013\u2014]+$/, "") + "\u2026");
      let lo = 1;
      let hi = words.length - 1;
      let best = 0;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        l.innerHTML = cutHtml(mid);
        if (!overflows(l)) {
          best = mid;
          lo = mid + 1;
        } else hi = mid - 1;
      }
      if (best) {
        l.innerHTML = cutHtml(best);
        return;
      }
    }
    for (const html of tail || [""]) {
      l.innerHTML = html;
      if (!html || !overflows(l)) return;
    }
    l.innerHTML = "";
  }

  function fitLabels(entries) {
    for (const e of entries) {
      fitOne(e);
      const l = e.b.firstChild;
      e.b._lh = l.offsetHeight;
      e.b._lw = l.offsetWidth;
      // tooltip when the tile does not show the whole title
      const full = titleOf(e.tile.node);
      e.b.title = l.textContent.includes(full) ? "" : full;
    }
  }

  function updateSubtitle(tree) {
    const secs = api.sectionsOf(tree);
    const open = expandedSet(tree);
    const opened = secs.map((id, i) => (open.has(id) ? nn(i) : null)).filter(Boolean);
    let txt;
    if (!secs.length) txt = "Mirrors the reader";
    else if (!opened.length) txt = "Mirrors the reader · at the gist";
    else if (opened.length === secs.length) txt = "Mirrors the reader · every section is open";
    else if (opened.length === 1) txt = `Mirrors the reader · ${opened[0]} is open`;
    else txt = `Mirrors the reader · ${opened.slice(0, -1).join(", ")} and ${opened[opened.length - 1]} are open`;
    if ($sub.textContent !== txt) $sub.textContent = txt;
  }

  // ------------------------------------------------------------------
  // "You are here"
  // ------------------------------------------------------------------
  function tileForNode(id) {
    const tree = api.getTree();
    let cur = id;
    let guard = 0;
    while (cur && guard++ < 100) {
      if (drawnById.has(cur)) return drawnById.get(cur);
      const n = tree.nodes[cur];
      cur = n ? n.parent : null;
    }
    return null;
  }

  function applyHere() {
    if (!isOpen || !api.getTree()) return;
    const ids = api.visibleFrontierIds();
    const keys = [];
    const seen = new Set();
    for (const id of ids) {
      const t = tileForNode(id);
      if (t && !seen.has(t.key)) {
        seen.add(t.key);
        keys.push(t.key);
      }
    }
    const sig = keys.join(",") + `|${s}|${W}|${H}`;
    if (sig === lastHereKeys && $pill.isConnected) return;
    lastHereKeys = sig;
    for (const [key, b] of els) b.classList.toggle("here", seen.has(key));
    if (!keys.length) {
      $pill.hidden = true;
      return;
    }
    const first = drawn.find((t) => t.key === keys[0]);
    const pw = 112;
    const ph = 28;
    const r = first.r;
    let px;
    let py;
    if (r.h >= 72 && r.w >= pw + 24) {
      px = r.x + r.w - pw - 8;
      py = r.y + r.h - ph - 8;
    } else {
      // Small tile: hang the pill just below it (or above when there is no
      // room), left-aligned, inside the map, so it does not cover a label.
      px = Math.min(r.x, W * s - pw - 2);
      py = r.y + r.h + 2 + ph <= H * s ? r.y + r.h + 2 : r.y - ph - 2;
    }
    $pill.style.left = `${Math.max(2, px)}px`;
    $pill.style.top = `${Math.max(2, py)}px`;
    $pill.hidden = false;
  }

  // ------------------------------------------------------------------
  // Camera: wheel zoom at the pointer, drag to pan, Fit
  // ------------------------------------------------------------------
  // Zoom to scale `ns`, keeping the tile under (px, py) (frame coords) fixed
  // at the same fractional position inside itself.
  function zoomTo(ns, px, py) {
    ns = clamp(ns, MIN_S, MAX_S);
    if (Math.abs(ns - s) < 1e-4 || !api.getTree()) return;
    const wx = px - ox;
    const wy = py - oy;
    let anchor = null;
    for (const t of drawn) {
      const r = t.r;
      if (wx >= r.x && wx <= r.x + r.w && wy >= r.y && wy <= r.y + r.h) anchor = t; // later == deeper
    }
    const os = s;
    s = ns;
    lay = null;
    const L = getLayout();
    let nwx;
    let nwy;
    const nr = anchor && L.get(anchor.id);
    if (anchor && nr) {
      nwx = nr.x + ((wx - anchor.r.x) / Math.max(1, anchor.r.w)) * nr.w;
      nwy = nr.y + ((wy - anchor.r.y) / Math.max(1, anchor.r.h)) * nr.h;
    } else {
      nwx = (wx * ns) / os;
      nwy = (wy * ns) / os;
    }
    ox = px - nwx;
    oy = py - nwy;
    clampCamera();
    scheduleRedraw();
    logZoom();
  }

  function logZoom() {
    clearTimeout(zoomLogTimer);
    zoomLogTimer = setTimeout(() => {
      const tree = api.getTree();
      if (tree) api.logEvent("map", { action: "zoom", tree_id: tree.id, scale: Math.round(s * 100) / 100 });
    }, 500);
  }

  function fit() {
    s = 1;
    ox = oy = 0;
    lay = null;
    scheduleRedraw();
  }

  let pendingWheel = null;
  function onWheel(e) {
    if (e.ctrlKey) return; // Ctrl+wheel is the reader's zoom
    e.preventDefault();
    const rect = $frame.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const unit = e.deltaMode === 1 ? 0.05 : e.deltaMode === 2 ? 0.5 : 0.0016;
    const factor = Math.exp(-e.deltaY * unit);
    if (!pendingWheel) {
      pendingWheel = { factor, px, py };
      requestAnimationFrame(() => {
        const p = pendingWheel;
        pendingWheel = null;
        if (p) zoomTo(s * p.factor, p.px, p.py);
      });
    } else {
      pendingWheel.factor *= factor;
      pendingWheel.px = px;
      pendingWheel.py = py;
    }
  }

  let drag = null;
  let suppressClick = false;
  function onPointerDown(e) {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY, ox, oy, moved: false };
  }
  function onPointerMove(e) {
    if (!drag || e.pointerId !== drag.id) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 4) return;
    if (!drag.moved) {
      drag.moved = true;
      try {
        $frame.setPointerCapture(e.pointerId);
      } catch (err) {}
      $frame.classList.add("dragging");
    }
    ox = drag.ox + dx;
    oy = drag.oy + dy;
    clampCamera();
    applyCamera();
  }
  function onPointerUp(e) {
    if (!drag || e.pointerId !== drag.id) return;
    if (drag.moved) {
      suppressClick = true;
      setTimeout(() => (suppressClick = false), 0);
      $frame.classList.remove("dragging");
      try {
        $frame.releasePointerCapture(e.pointerId);
      } catch (err) {}
    }
    drag = null;
  }

  function onClick(e) {
    if (suppressClick) {
      e.preventDefault();
      return;
    }
    const b = e.target.closest && e.target.closest(".map-tile");
    if (!b || !api.getTree()) return;
    const id = b.dataset.nodeId;
    api.logEvent("map", { action: "jump", tree_id: api.getTree().id, node_id: id });
    api.jumpToNode(id);
    if (!wideMQ.matches) setOpen(false, { restoreFocus: false });
  }

  // ------------------------------------------------------------------
  // Open / close
  // ------------------------------------------------------------------
  function applyChrome() {
    $app.classList.toggle("map-open", isOpen);
    $panel.hidden = !isOpen;
    $btn.setAttribute("aria-pressed", String(isOpen));
    if (window.RiemannCols) window.RiemannCols.refresh();
  }

  function setOpen(v, opts) {
    opts = opts || {};
    if (v === isOpen) return;
    const change = () => {
      isOpen = v;
      applyChrome();
    };
    if (wideMQ.matches && api.keepReadingPosition) api.keepReadingPosition(change);
    else change();
    if (opts.persist !== false && wideMQ.matches) writeStore(v);
    if (v) {
      lastHereKeys = "";
      redraw();
      maybeBackfill();
      if (!wideMQ.matches) $panel.querySelector("#map-close").focus();
    } else if (!wideMQ.matches && opts.restoreFocus !== false) {
      $btn.focus();
    }
    if (api.getTree()) api.logEvent("map", { action: v ? "open" : "close", tree_id: api.getTree().id });
  }

  function scheduleRedraw() {
    if (redrawQueued) return;
    redrawQueued = true;
    requestAnimationFrame(redraw);
  }

  function update() {
    if (!api) return;
    if (!api.getTree()) {
      // Left the document: clear the map (the preference stays).
      for (const b of els.values()) b.remove();
      els.clear();
      drawn = [];
      drawnById = new Map();
      treeId = null;
      lay = null;
      layKey = "";
      lastHereKeys = "";
      return;
    }
    if (!isOpen) return;
    scheduleRedraw();
    maybeBackfill();
  }

  function init(a) {
    api = a;
    $app = document.getElementById("app");
    $panel = document.getElementById("map-panel");
    $frame = document.getElementById("map-frame");
    $world = document.getElementById("map-world");
    $sub = document.getElementById("map-sub");
    $btn = document.getElementById("map-btn");
    $pill = document.getElementById("map-here");

    $btn.addEventListener("click", toggle);
    document.getElementById("map-close").addEventListener("click", () => setOpen(false));
    document.getElementById("map-fit").addEventListener("click", fit);
    document.getElementById("map-out").addEventListener("click", () => zoomTo(s / 1.5, W / 2, H / 2));
    document.getElementById("map-in").addEventListener("click", () => zoomTo(s * 1.5, W / 2, H / 2));

    $frame.addEventListener("wheel", onWheel, { passive: false });
    $frame.addEventListener("pointerdown", onPointerDown);
    $frame.addEventListener("pointermove", onPointerMove);
    $frame.addEventListener("pointerup", onPointerUp);
    $frame.addEventListener("pointercancel", onPointerUp);
    $frame.addEventListener("click", onClick);

    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "Escape" && isOpen && !wideMQ.matches) {
        setOpen(false);
        return;
      }
      if (e.key !== "g" && e.key !== "G") return;
      if (e.repeat || !$app.classList.contains("active")) return;
      const t = e.target;
      const tag = ((t && t.tagName) || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable)) return;
      e.preventDefault();
      toggle();
    });

    window.addEventListener(
      "scroll",
      () => {
        if (!isOpen) return;
        clearTimeout(hereTimer);
        hereTimer = setTimeout(applyHere, 120);
      },
      { passive: true }
    );

    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (isOpen && $frame.clientWidth > 0 && (Math.abs($frame.clientWidth - W) > 0.5 || Math.abs($frame.clientHeight - H) > 0.5)) scheduleRedraw();
      }).observe($frame);
    }
    window.addEventListener("resize", () => {
      if (isOpen) scheduleRedraw();
    });

    // Crossing the desktop/phone breakpoint: the sheet never opens by itself.
    let wasWide = wideMQ.matches;
    const onBreak = () => {
      const wide = wideMQ.matches;
      if (wide === wasWide) return;
      wasWide = wide;
      isOpen = wide ? readStore() : false;
      applyChrome();
      lastHereKeys = "";
      if (isOpen) scheduleRedraw();
    };
    if (wideMQ.addEventListener) wideMQ.addEventListener("change", onBreak);
    else if (wideMQ.addListener) wideMQ.addListener(onBreak);

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => {
        for (const b of els.values()) b._sig = null;
        if (isOpen) scheduleRedraw();
      });
    }

    isOpen = wideMQ.matches && readStore();
    applyChrome();
    if (isOpen) scheduleRedraw();
  }

  function open(opts) {
    setOpen(true, opts);
  }
  function close(opts) {
    setOpen(false, opts);
  }
  function isOpenNow() {
    return isOpen;
  }
  function toggle() {
    setOpen(!isOpen);
  }

  window.RiemannMap = { init, update, open, close, toggle, isOpen: isOpenNow };
})();
