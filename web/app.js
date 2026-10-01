// app.js — Riemann v2 frontend: Macaron Command Centre.
// Reads docs/v2-macaron-spec.md as the contract. The zoom algorithm itself
// lives in frontier.js and is untouched here; this file is chrome,
// rendering (sections/rail/nav), palette, highlights, events and state.

(function () {
  "use strict";

  const WPM = 238;
  const REDUCED_MOTION = window.matchMedia("(prefers-motion-reduce), (prefers-reduced-motion: reduce)").matches;
  const IS_FIXTURE = new URLSearchParams(location.search).get("fixture") === "1";

  // ---------------------------------------------------------------------
  // Palette constants (design/Macaron-Palette.dc.html, design/softpastel-tokens.json)
  // ---------------------------------------------------------------------
  const PALETTE = [
    ["Blush", "#F6D5D1"], ["Pastel pink", "#F9D3E3"], ["Rose quartz", "#F3C6D3"], ["Candy floss", "#FBDDEB"],
    ["Peach", "#FBDCC8"], ["Apricot", "#F8E0B8"], ["Butter", "#F7E8B5"], ["Lemon", "#F5F0B8"],
    ["Pistachio", "#E1ECCB"], ["Sage", "#D5E6CF"], ["Mint", "#D2EBDD"], ["Seafoam", "#CFE8E1"],
    ["Sky", "#D3E4F2"], ["Periwinkle", "#D9DDF4"], ["Lavender", "#E2D8F0"], ["Lilac", "#EBD9F0"],
  ];
  const PRESETS = [
    { name: "Macaron", sections: ["#F6D5D1", "#D5E6CF", "#F7E8B5", "#D3E4F2", "#E2D8F0"], hl: "#F9D3E3" },
    { name: "Pink party", sections: ["#F9D3E3", "#F3C6D3", "#FBDDEB", "#F6D5D1", "#EBD9F0"], hl: "#F9D3E3" },
    { name: "Garden", sections: ["#E1ECCB", "#D5E6CF", "#F5F0B8", "#FBDCC8", "#D2EBDD"], hl: "#F5F0B8" },
    { name: "Sky & lilac", sections: ["#D3E4F2", "#D9DDF4", "#E2D8F0", "#CFE8E1", "#EBD9F0"], hl: "#D9DDF4" },
  ];
  const TOOLBAR_SWATCH_IDX = [0, 1, 2, 6, 9, 12, 14]; // blush, pastel pink, rose quartz, butter, sage, sky, lavender
  const DEFAULT_PALETTE = { sections: PRESETS[0].sections.slice(), hl: PRESETS[0].hl, preset: "Macaron" };

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  const state = {
    tree: null,
    z: 0,
    sequence: [],
    frontier: [],
    prose: new Set(), // internal nodes shown as their summary paragraph; others on the page are in skim form
    anchorNodeId: null,
    sequenceAnchor: null,
    anchorOffset: null,
    minimalChrome: false,
    eventSource: null,
    lastAnnounce: 0,
    announceTimer: null,
    dwellTimer: null,
    dwellStart: 0,
    dwellNode: null,
    idleTimer: null,
    lastInputAt: Date.now(),
    lastDialChangeAt: 0,
    events: [],
    leafIndex: null,
    lastRailSection: undefined,
    palette: DEFAULT_PALETTE,
    paletteOpen: false,
    paletteMode: "highlight",
    paletteSlot: 0,
    highlights: [],
    hlContext: null,
    reading: { spacing: false, width: "normal" },
  };

  const el = (id) => document.getElementById(id);
  const $startScreen = el("start-screen");
  const $app = el("app");
  const $content = el("content");
  const $docTitle = el("doc-title");
  const $docHook = el("doc-hook");
  const $dial = el("dial");
  const $liveRegion = el("live-region");
  const $resumeCard = el("resume-card");
  const $resumeCardText = el("resume-card-text");
  const $zoomHint = el("zoom-hint");
  const $topSpacer = el("top-spacer");
  const $sectionNav = el("section-nav");
  const $navItems = el("nav-items");
  const $rail = el("rail");
  const $paletteBtn = el("palette-btn");
  const $palettePanel = el("palette-panel");
  const $hlToolbar = el("highlight-toolbar");
  let topSpacerPx = 0;
  function resetTopSpacer() {
    topSpacerPx = 0;
    $topSpacer.style.height = "0px";
  }

  // ---------------------------------------------------------------------
  // Pointer tracking — used to resolve "the passage under the pointer" for
  // every zoom gesture (Z-drag, ctrl+wheel/pinch, arrow/+-/pill keys).
  // ---------------------------------------------------------------------
  const lastMouse = { x: null, y: null };
  window.addEventListener(
    "mousemove",
    (e) => {
      lastMouse.x = e.clientX;
      lastMouse.y = e.clientY;
    },
    { passive: true }
  );

  function isPointOverContent(x, y) {
    if (x == null || y == null) return false;
    const rect = $content.getBoundingClientRect();
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function nodeAtScreenPoint(x, y) {
    const hit = document.elementFromPoint(x, y);
    const found = hit && hit.closest && hit.closest("[data-node-id]");
    if (found) return found.dataset.nodeId;
    // Fell in the gap between nodes: pick the nearest by vertical distance.
    let best = null;
    let bestDist = Infinity;
    for (const n of $content.querySelectorAll("[data-node-id]")) {
      const r = n.getBoundingClientRect();
      if (y >= r.top && y <= r.bottom) return n.dataset.nodeId;
      const d = y < r.top ? r.top - y : y - r.bottom;
      if (d < bestDist) {
        bestDist = d;
        best = n;
      }
    }
    return best ? best.dataset.nodeId : null;
  }

  // ---------------------------------------------------------------------
  // Event log — batched POST /api/events every 5s, sendBeacon on pagehide
  // ---------------------------------------------------------------------
  function logEvent(type, data) {
    state.events.push(Object.assign({ type }, data));
  }

  function flushEvents(useBeacon) {
    if (state.events.length === 0) return;
    if (IS_FIXTURE) {
      state.events = [];
      return;
    }
    const payload = state.events;
    state.events = [];
    const body = JSON.stringify(payload);
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon("/api/events", new Blob([body], { type: "application/json" }));
    } else {
      fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body }).catch(() => {});
    }
  }

  setInterval(() => flushEvents(false), 5000);
  window.addEventListener("pagehide", () => {
    if (state.tree) logEvent("close", { tree_id: state.tree.id });
    flushEvents(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      savePosition();
      flushEvents(true);
    }
  });

  function markInput() {
    const now = Date.now();
    const idleMs = now - state.lastInputAt;
    if (idleMs > 60000 && state.tree) {
      logEvent("idle", { tree_id: state.tree.id, ms: idleMs });
    }
    state.lastInputAt = now;
  }

  // ---------------------------------------------------------------------
  // localStorage: resume, palette, highlights
  // ---------------------------------------------------------------------
  function posKey(treeId) {
    return "riemann:pos:" + treeId;
  }

  function savePosition() {
    if (!state.tree) return;
    try {
      localStorage.setItem(
        posKey(state.tree.id),
        JSON.stringify({ z: state.z, anchor_node_id: state.anchorNodeId, anchor_offset: state.anchorOffset })
      );
    } catch (e) {}
  }

  const savePositionDebounced = debounce(savePosition, 400);

  // Anything read back from localStorage is untrusted (another tool, a
  // corrupted write, a hand edit): validate its shape before it reaches the
  // DOM or the zoom maths.
  const isHexColour = (v) => typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v);

  function loadPosition(treeId) {
    try {
      const raw = localStorage.getItem(posKey(treeId));
      const p = raw ? JSON.parse(raw) : null;
      if (!p || typeof p !== "object") return null;
      if (typeof p.z !== "number" || !isFinite(p.z)) return null;
      if (p.anchor_node_id != null && typeof p.anchor_node_id !== "string") return null;
      if (p.anchor_offset != null && !(typeof p.anchor_offset === "number" && isFinite(p.anchor_offset))) return null;
      return p;
    } catch (e) {
      return null;
    }
  }

  function debounce(fn, ms) {
    let t = null;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(null, args), ms);
    };
  }

  function loadPalette() {
    try {
      const raw = localStorage.getItem("riemann:palette");
      if (raw) {
        const p = JSON.parse(raw);
        if (p && Array.isArray(p.sections) && p.sections.length === 5 && p.sections.every(isHexColour) && isHexColour(p.hl)) {
          const known = PRESETS.some((x) => x.name === p.preset);
          return { sections: p.sections.slice(), hl: p.hl, preset: known ? p.preset : null };
        }
      }
    } catch (e) {}
    return { sections: DEFAULT_PALETTE.sections.slice(), hl: DEFAULT_PALETTE.hl, preset: DEFAULT_PALETTE.preset };
  }

  function savePalette() {
    try {
      localStorage.setItem("riemann:palette", JSON.stringify(state.palette));
    } catch (e) {}
  }

  function applyPaletteToCSS() {
    const root = document.documentElement.style;
    state.palette.sections.forEach((c, i) => root.setProperty(`--sec-${i + 1}`, c));
    root.setProperty("--hl", state.palette.hl);
    if (window.RiemannMap) window.RiemannMap.update();
  }

  // Reading settings: letter-spacing on or off, and the reading column's width. Like the
  // palette, whatever is read back is checked against the known values.
  const READING_KEY = "riemann:reading";
  const READ_WIDTHS = { narrow: 34, normal: 40, wide: 48 };
  const DEFAULT_READING = { spacing: false, width: "normal" };

  function loadReading() {
    try {
      const p = JSON.parse(localStorage.getItem(READING_KEY) || "null");
      if (p && typeof p === "object") {
        return {
          spacing: p.spacing === true,
          width: typeof p.width === "string" && Object.prototype.hasOwnProperty.call(READ_WIDTHS, p.width) ? p.width : "normal",
        };
      }
    } catch (e) {}
    return Object.assign({}, DEFAULT_READING);
  }

  function saveReading() {
    try {
      localStorage.setItem(READING_KEY, JSON.stringify(state.reading));
    } catch (e) {}
  }

  function applyReadingToCSS() {
    const root = document.documentElement.style;
    root.setProperty("--reading-ls", state.reading.spacing ? "0.04em" : "0");
    root.setProperty("--read-em", String(READ_WIDTHS[state.reading.width]));
  }

  function renderReadingControls() {
    el("ls-toggle").setAttribute("aria-pressed", String(state.reading.spacing));
    for (const b of el("read-width").querySelectorAll("[data-width]")) {
      b.setAttribute("aria-checked", String(b.dataset.width === state.reading.width));
      b.tabIndex = b.dataset.width === state.reading.width ? 0 : -1;
    }
  }

  // Changing either reflows the text, so hold the reading position and re-decide the columns.
  function changeReading(next, field) {
    state.reading = next;
    saveReading();
    const apply = () => {
      applyReadingToCSS();
      applyColumnMode(false);
    };
    if (state.tree && $app.classList.contains("active")) keepReadingPosition(apply);
    else apply();
    renderReadingControls();
    logEvent("reading", { field, value: field === "spacing" ? next.spacing : next.width });
  }

  el("ls-toggle").addEventListener("click", () => changeReading({ spacing: !state.reading.spacing, width: state.reading.width }, "spacing"));
  el("read-width").addEventListener("click", (e) => {
    const b = e.target.closest("[data-width]");
    if (b && b.dataset.width !== state.reading.width) changeReading({ spacing: state.reading.spacing, width: b.dataset.width }, "width");
  });
  el("read-width").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const order = Object.keys(READ_WIDTHS);
    const i = order.indexOf(state.reading.width) + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1);
    changeReading({ spacing: state.reading.spacing, width: order[(i + order.length) % order.length] }, "width");
    const on = el("read-width").querySelector('[aria-checked="true"]');
    if (on) on.focus();
    e.preventDefault();
  });

  function hlStorageKey(treeId) {
    return "riemann:hl:" + treeId;
  }

  function loadHighlights(treeId) {
    try {
      const raw = localStorage.getItem(hlStorageKey(treeId));
      const list = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(list)) return [];
      return list.filter(
        (h) =>
          h && typeof h === "object" && typeof h.id === "string" && /^[\w-]{1,40}$/.test(h.id) &&
          typeof h.nodeId === "string" && Number.isFinite(h.start) && Number.isFinite(h.end) && h.end > h.start && isHexColour(h.colour)
      );
    } catch (e) {
      return [];
    }
  }

  function saveHighlights() {
    if (!state.tree) return;
    try {
      localStorage.setItem(hlStorageKey(state.tree.id), JSON.stringify(state.highlights));
    } catch (e) {}
  }

  // ---------------------------------------------------------------------
  // Word / reading-time helpers
  // ---------------------------------------------------------------------
  // Same rules as the server (Han and Kana count per character), so zoom steps
  // and read times agree for Chinese and Japanese.
  const countWords = (text) => window.Frontier.countWords(text);

  function isSkim(node, prose) {
    return !node.is_leaf && node.id !== state.tree.root && !prose.has(node.id) && hasSkimContent(node);
  }

  function hasSkimContent(node) {
    return (node.key_points && node.key_points.length > 0) || !!node.hook;
  }

  function skimWords(node) {
    const points = node.key_points && node.key_points.length ? node.key_points : [node.hook];
    return countWords(nodeTitle(node)) + points.reduce((sum, p) => sum + countWords(p), 0);
  }

  function frontierWords(tree, frontier, prose) {
    let words = 0;
    for (const id of frontier) {
      const n = tree.nodes[id];
      if (!n) continue;
      words += prose && isSkim(n, prose) ? skimWords(n) : n.words;
    }
    return words;
  }

  function updateReadout() {
    const tree = state.tree;
    if (!tree) return;
    const words = frontierWords(tree, state.frontier, state.prose);
    const minutes = Math.max(1, Math.round(words / WPM));
    const pct = Math.max(1, Math.round((words / Math.max(1, tree.source_words)) * 100));
    $dial.textContent = `~${minutes} min · ${pct}% of original`;
    const valuetext = `about ${minutes} minute${minutes === 1 ? "" : "s"}, ${pct} percent of original`;
    $dial.setAttribute("aria-valuetext", valuetext);
    $dial.setAttribute("aria-valuenow", String(Math.round(state.z * 100)));
    scheduleAnnounce(valuetext);
  }

  // Move keyboard focus to a non-interactive landmark without scrolling or a
  // visible ring (used after a screen change hides the control that had it).
  function focusQuietly(elem) {
    if (!elem) return;
    if (!elem.hasAttribute("tabindex")) elem.setAttribute("tabindex", "-1");
    elem.focus({ preventScroll: true });
  }

  function scheduleAnnounce(text) {
    clearTimeout(state.announceTimer);
    state.announceTimer = setTimeout(() => {
      $liveRegion.textContent = text;
    }, 400);
  }

  // ---------------------------------------------------------------------
  // Anchor detection
  // ---------------------------------------------------------------------
  function findCentreNodeId() {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    let node = document.elementFromPoint(cx, cy);
    while (node && node !== document.body) {
      if (node.dataset && node.dataset.nodeId) return node.dataset.nodeId;
      node = node.parentElement;
    }
    return state.frontier[0] || state.tree.root;
  }

  // A new anchor reorders future expansions around it, but must not change
  // what's on screen: the currently expanded nodes stay first in the new
  // sequence and z is re-expressed against it, so the next step changes
  // exactly one passage instead of reshuffling the page.
  function sequenceKeepingPage(anchorId) {
    const nodes = state.tree.nodes;
    if (!state.frontier || !state.frontier.length) {
      return window.Frontier.buildExpansionSequence(state.tree, anchorId);
    }
    const P = window.Frontier.PROSE;
    const keep = new Set();
    const onPage = new Set(state.frontier);
    for (const id of state.frontier) {
      let p = nodes[id] && nodes[id].parent;
      while (p && !keep.has(p)) {
        keep.add(p);
        p = nodes[p].parent;
      }
    }
    for (const id of state.prose) if (onPage.has(id) && id !== state.tree.root) keep.add(P + id);
    const seq = window.Frontier.buildExpansionSequence(state.tree, anchorId, keep);
    if (seq.length) state.z = keep.size / seq.length;
    return seq;
  }

  // state.anchorNodeId is "the passage you're on" and drifts as zoom steps
  // hand it to a child; state.sequenceAnchor is the passage the zoom order
  // was actually built around. Rebuild whenever they differ, or a zoom
  // started over one passage would keep following an older anchor's order
  // and open something elsewhere on the page.
  function setAnchor(nodeId) {
    const prev = state.anchorNodeId;
    state.anchorNodeId = nodeId;
    state.pinMode = "point";
    const n = state.tree.nodes[nodeId];
    state.anchorOffset = n ? (n.source_span[0] + n.source_span[1]) / 2 : null;
    if (nodeId !== state.sequenceAnchor) {
      state.sequence = sequenceKeepingPage(nodeId);
      state.sequenceAnchor = nodeId;
    }
    if (prev !== nodeId) {
      handleDwellChange(nodeId);
      updateNavCurrent();
      updateRail();
    }
    savePositionDebounced();
  }

  function handleDwellChange(newNodeId) {
    const now = Date.now();
    if (state.dwellNode && state.dwellStart) {
      const ms = now - state.dwellStart;
      if (ms > 1500) {
        logEvent("dwell", { tree_id: state.tree.id, node_id: state.dwellNode, ms });
      }
    }
    state.dwellNode = newNodeId;
    state.dwellStart = now;
  }

  // ---------------------------------------------------------------------
  // Sections: node grouping, nav, rail
  // ---------------------------------------------------------------------
  function sectionsOf(tree) {
    return tree.sections && tree.sections.length ? tree.sections : [];
  }

  function sectionAncestor(tree, nodeId) {
    const secs = sectionsOf(tree);
    if (!secs.length) return null;
    const secSet = new Set(secs);
    let id = nodeId;
    let guard = 0;
    while (id != null && guard++ < 200) {
      if (secSet.has(id)) return id;
      const n = tree.nodes[id];
      if (!n) return null;
      id = n.parent;
    }
    return null;
  }

  const firstClause = (text) => window.Frontier.firstClause(text);

  function nodeTitle(node) {
    return (node && (node.title || firstClause(node.text))) || "";
  }

  function computeLeafIndex(tree) {
    const index = {};
    let counter = 0;
    (function walk(id) {
      const n = tree.nodes[id];
      if (!n) return;
      if (n.is_leaf) {
        counter += 1;
        index[id] = counter;
      } else {
        for (const c of n.children) walk(c);
      }
    })(tree.root);
    return index;
  }

  function nodeProvenance(node) {
    const li = state.leafIndex;
    if (!li) return "";
    if (node.is_leaf) {
      const idx = li[node.id];
      return idx ? `¶ ${idx}` : "";
    }
    const idxs = (node.cites || []).map((id) => li[id]).filter((x) => x != null);
    if (!idxs.length) return "";
    const mn = Math.min(...idxs);
    const mx = Math.max(...idxs);
    return mn === mx ? `¶ ${mn}` : `¶ ${mn}–${mx}`;
  }

  function buildNav() {
    const tree = state.tree;
    const secs = sectionsOf(tree);
    const hasSections = secs.length > 0;
    $app.classList.toggle("no-sections", !hasSections);
    if (!hasSections) {
      $navItems.innerHTML = "";
      return;
    }
    $navItems.innerHTML = secs
      .map((id, i) => {
        const n = tree.nodes[id];
        const nn = String(i + 1).padStart(2, "0");
        const slot = (i % 5) + 1;
        return `<button type="button" class="nav-item" data-section-id="${id}" data-slot="${slot}">
          <span class="nav-dot" style="background: var(--sec-${slot})"></span>
          <span class="nav-n">${nn}</span><span class="nav-title">${escapeHtml(nodeTitle(n))}</span>
        </button>`;
      })
      .join("");
  }

  function updateNavCurrent() {
    if (!state.tree) return;
    const secId = state.anchorNodeId ? sectionAncestor(state.tree, state.anchorNodeId) : null;
    for (const btn of $navItems.querySelectorAll(".nav-item")) {
      const isCur = btn.dataset.sectionId === secId;
      btn.classList.toggle("current", isCur);
      const dot = btn.querySelector(".nav-dot");
      if (isCur) {
        dot.style.visibility = "hidden";
        btn.style.background = `var(--sec-${btn.dataset.slot})`;
      } else {
        dot.style.visibility = "";
        btn.style.background = "";
      }
    }
  }

  $navItems.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-section-id]");
    if (!btn) return;
    jumpToNode(btn.dataset.sectionId);
  });

  function renderRailCardsHTML(secNode, upNextNode, secs, idx) {
    const parts = [];
    if (secNode.key_fact) {
      parts.push(
        `<div class="rail-card key-fact"><span class="rail-label">KEY FACT</span>` +
          `<span class="fact-big">${escapeHtml(secNode.key_fact.big)}</span>` +
          `<span class="fact-detail">${escapeHtml(secNode.key_fact.detail)}</span></div>`
      );
    }
    if (secNode.steps && secNode.steps.length) {
      parts.push(
        `<div class="rail-card panel"><span class="rail-label">HOW IT WORKS</span>` +
          `<div class="step-chips">${secNode.steps.map((s) => `<span class="step-chip">${escapeHtml(s)}</span>`).join("")}</div></div>`
      );
    } else if (secNode.key_points && secNode.key_points.length && !sectionPointsOnPage(secNode)) {
      parts.push(
        `<div class="rail-card panel"><span class="rail-label">KEY POINTS</span>` +
          `<ul class="key-points">${secNode.key_points.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul></div>`
      );
    }
    if (upNextNode) {
      const nn2 = String(idx + 2).padStart(2, "0");
      parts.push(
        `<button type="button" class="rail-card up-next" data-jump="${secs[idx + 1]}">` +
          `<span class="rail-label">UP NEXT &middot; ${nn2}</span>` +
          `<span class="up-next-title">${escapeHtml(nodeTitle(upNextNode))}</span>` +
          (upNextNode.hook ? `<span class="up-next-hook">${escapeHtml(upNextNode.hook)}</span>` : "") +
          `</button>`
      );
    }
    return parts.join("");
  }

  function sectionPointsOnPage(secNode) {
    return state.frontier.includes(secNode.id) && isSkim(secNode, state.prose);
  }

  function railCardsForSection(tree, secId) {
    const secs = sectionsOf(tree);
    const idx = secs.indexOf(secId);
    if (idx < 0) return "";
    const secNode = tree.nodes[secId];
    const upNextId = secs[idx + 1];
    const upNextNode = upNextId ? tree.nodes[upNextId] : null;
    return renderRailCardsHTML(secNode, upNextNode, secs, idx);
  }

  function updateRail() {
    const tree = state.tree;
    if (!tree || !$rail) return;
    const secId = state.anchorNodeId ? sectionAncestor(tree, state.anchorNodeId) : null;
    // Re-render when the section changes, or when its bullets move between
    // the page (skim) and the rail.
    const key = secId ? `${secId}:${sectionPointsOnPage(tree.nodes[secId]) ? 1 : 0}` : null;
    if (key === state.lastRailSection) return;
    state.lastRailSection = key;
    const doUpdate = () => {
      $rail.innerHTML = secId ? railCardsForSection(tree, secId) : "";
    };
    if (REDUCED_MOTION) {
      doUpdate();
      return;
    }
    $rail.style.opacity = "0";
    setTimeout(() => {
      // Home or another document may have replaced this one during the fade.
      if (state.tree !== tree) {
        $rail.style.opacity = "1";
        return;
      }
      doUpdate();
      requestAnimationFrame(() => {
        $rail.style.opacity = "1";
      });
    }, 180);
  }

  $rail.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-jump]");
    if (!btn) return;
    jumpToNode(btn.dataset.jump);
  });

  // ---------------------------------------------------------------------
  // Reader columns: two only while each still gets a comfortable line
  // ---------------------------------------------------------------------
  const MIN_CPL = 45; // characters per line below which two columns turn into one
  const SAMPLE_TEXT = "It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness.";
  // A real line is a little shorter than width / average character width: a word that
  // does not fit moves down. Measured at about 10% on running English text.
  const WRAP_LOSS = 1.1;
  let measureCtx = null;
  const charWidthCache = new Map();

  // Average character width of running text in the font of a probe element.
  function avgCharWidth(probeId) {
    const probe = el(probeId);
    if (!probe) return 0;
    const cs = getComputedStyle(probe);
    const font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const ls = parseFloat(cs.letterSpacing) || 0;
    const key = font + "|" + ls;
    if (charWidthCache.has(key)) return charWidthCache.get(key);
    if (!measureCtx) measureCtx = document.createElement("canvas").getContext("2d");
    measureCtx.font = font;
    const w = (measureCtx.measureText(SAMPLE_TEXT).width / SAMPLE_TEXT.length + ls) * WRAP_LOSS;
    charWidthCache.set(key, w);
    return w;
  }

  // The reading column's content width, in px (the padding is not text room).
  function contentInnerWidth() {
    const cs = getComputedStyle($content);
    return $content.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
  }

  // How many columns the reading grid and the overview tiles get at the current
  // width, font, letter-spacing and reading width, with the characters per line
  // each choice gives. Pure given its inputs, so it can be tested.
  function columnPlan(innerW, charW, opts) {
    const gap = opts.gap;
    const maxCol = opts.maxCol == null ? Infinity : opts.maxCol;
    const twoW = Math.min((innerW - gap) / 2, maxCol);
    const oneW = Math.min(innerW, maxCol);
    const cpl = (w) => (charW > 0 ? Math.max(0, (w - opts.pad) / charW) : 99);
    const two = cpl(twoW) >= MIN_CPL;
    return { two, cpl: two ? cpl(twoW) : cpl(oneW), cplTwo: cpl(twoW), cplOne: cpl(oneW) };
  }

  // Sets .one-col / .ov-one-col on #content. Called while (re)rendering, and,
  // with keep = true, when only the width or a setting changed (the reading
  // position is held across the reflow).
  function applyColumnMode(keep) {
    if (!$app.classList.contains("active")) return;
    const innerW = contentInnerWidth();
    if (innerW <= 0) return;
    const bodyCw = avgCharWidth("probe-body");
    const tileCw = avgCharWidth("probe-tile");
    const grid = columnPlan(innerW, bodyCw, { gap: 36, pad: 16, maxCol: readingMaxPx() });
    const tiles = columnPlan(innerW, tileCw, { gap: 6, pad: 20, maxCol: Infinity });
    const wantOne = !grid.two;
    const wantOvOne = !tiles.two;
    $content.dataset.cols = grid.two ? "2" : "1";
    $content.dataset.cpl = String(Math.round(grid.cpl));
    if ($content.classList.contains("one-col") === wantOne && $content.classList.contains("ov-one-col") === wantOvOne) return;
    const flip = () => {
      $content.classList.toggle("one-col", wantOne);
      $content.classList.toggle("ov-one-col", wantOvOne);
    };
    if (keep && state.tree) keepReadingPosition(flip);
    else flip();
  }

  // Maximum width of one reading column in px (the reading-width setting, in em of the 17 px body).
  function readingMaxPx() {
    return READ_WIDTHS[state.reading.width] * 17;
  }

  if (window.ResizeObserver) {
    let lastW = 0;
    new ResizeObserver(() => {
      const w = $content.clientWidth;
      if (w === lastW) return;
      lastW = w;
      applyColumnMode(true);
    }).observe($content);
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      charWidthCache.clear();
      applyColumnMode(true);
    });
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------
  // A summary is shown in one of two forms: skim (its title plus key-point
  // bullets, how it first appears when its parent opens) or prose (its
  // summary paragraph). Zooming in on it goes skim -> prose -> its parts, so
  // you can get the idea from titles and bullets before reading paragraphs.
  // A section's own block drops its title: the section header right above
  // already shows it.
  function renderNodeBlockHTML(node, opts) {
    opts = opts || {};
    const skim = isSkim(node, state.prose);
    let html;
    if (skim) {
      const points = node.key_points && node.key_points.length ? node.key_points : [node.hook];
      html = `<ul class="skim-points">${points.map((p) => `<li>${renderInline(p)}</li>`).join("")}</ul>`;
    } else {
      html = renderMarkdown(node.text || "");
    }
    const isLeaf = node.is_leaf;
    const cls = ["node", isLeaf ? "leaf" : "summary", skim ? "skim" : "", node.atomic ? "atomic" : "", opts.sectionSelf ? "section-self" : ""]
      .filter(Boolean)
      .join(" ");
    const prov = nodeProvenance(node);
    // Summaries link to their original text via the small ¶ label only (the
    // whole body used to be a hover target, which popped a bubble mid-zoom
    // that never closed because its element was replaced under the pointer).
    const provHTML = !prov
      ? ""
      : isLeaf || !(node.cites && node.cites.length)
        ? `<span class="provenance">${escapeHtml(prov)}</span>`
        : `<button type="button" class="provenance source-link" title="Read the original text">${escapeHtml(prov)}<span class="source-link-more"> · original</span></button>`;
    const titleHTML = opts.sectionSelf ? "" : `<h2 class="node-title">${escapeHtml(nodeTitle(node))}</h2>`;
    return `<div class="${cls}" data-node-id="${node.id}" data-form="${skim ? "skim" : "prose"}">
      <div class="node-head">${titleHTML}${provHTML}</div>
      <div class="node-body">${html}</div>
    </div>`;
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // Inline markdown for short strings (key points, essentials): everything
  // escaped first, then only **bold**, *italic* and `code` are turned into tags.
  function renderInline(s) {
    return escapeHtml(s || "")
      .replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?!\w)/g, "$1<em>$2</em>")
      .replace(/`([^`\n]+?)`/g, "<code>$1</code>");
  }

  // Block markdown for prose and source leaves. marked does the parsing when
  // it loaded (it is a CDN script); a small built-in renderer covers paragraphs,
  // lists, headings, bold/italic/code when it did not. Either way the result
  // is sanitised: only a short list of harmless tags survives, raw HTML in the
  // source is shown as text, and links are limited to http(s)/mailto.
  const SAFE_TAGS = new Set(["P", "UL", "OL", "LI", "STRONG", "EM", "B", "I", "CODE", "PRE", "BR", "HR", "BLOCKQUOTE", "A",
    "H1", "H2", "H3", "H4", "H5", "H6", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD", "DEL", "SUB", "SUP"]);

  function miniMarkdown(src) {
    const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) {
        i++;
        continue;
      }
      const h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        out.push(`<h${h[1].length}>${renderInline(h[2])}</h${h[1].length}>`);
        i++;
        continue;
      }
      const ul = /^\s*[-*+]\s+/;
      const ol = /^\s*\d{1,3}[.)]\s+/;
      if (ul.test(line) || ol.test(line)) {
        const re = ul.test(line) ? ul : ol;
        const tag = re === ul ? "ul" : "ol";
        const items = [];
        while (i < lines.length && re.test(lines[i])) {
          items.push(`<li>${renderInline(lines[i].replace(re, ""))}</li>`);
          i++;
        }
        out.push(`<${tag}>${items.join("")}</${tag}>`);
        continue;
      }
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^#{1,6}\s/.test(lines[i]) && !ul.test(lines[i]) && !ol.test(lines[i])) {
        para.push(lines[i].trim());
        i++;
      }
      out.push(`<p>${renderInline(para.join(" "))}</p>`);
    }
    return out.join("");
  }

  function sanitizeHTML(html) {
    const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
    const walk = (parent) => {
      for (const child of Array.from(parent.childNodes)) {
        if (child.nodeType === 3) continue;
        if (child.nodeType !== 1) {
          child.remove();
          continue;
        }
        if (!SAFE_TAGS.has(child.tagName)) {
          child.replaceWith(document.createTextNode(child.textContent || ""));
          continue;
        }
        for (const attr of Array.from(child.attributes)) {
          const keep = child.tagName === "A" && attr.name === "href" && /^(https?:|mailto:|#)/i.test(attr.value.trim());
          if (!keep) child.removeAttribute(attr.name);
        }
        if (child.tagName === "A") {
          child.setAttribute("target", "_blank");
          child.setAttribute("rel", "noopener noreferrer");
        }
        walk(child);
      }
    };
    walk(doc.body);
    return doc.body.innerHTML;
  }

  function renderMarkdown(text) {
    let html = null;
    if (window.marked && typeof window.marked.parse === "function") {
      try {
        // Raw HTML in the source is escaped, not passed through.
        html = window.marked.parse(escapeRawHtml(text || ""), { gfm: true, breaks: false });
      } catch (e) {
        html = null;
      }
    }
    if (html == null) html = miniMarkdown(text || "");
    return sanitizeHTML(html);
  }

  function escapeRawHtml(src) {
    // Only the tag-open character: markdown syntax (>, &, quotes) is untouched.
    return String(src).replace(/<(?=[A-Za-z\/!?])/g, "&lt;");
  }

  function groupFrontierBySections(tree, frontier) {
    const groups = [];
    let cur = null;
    for (const id of frontier) {
      const sec = sectionAncestor(tree, id);
      if (!cur || cur.sectionId !== sec) {
        cur = { sectionId: sec, ids: [] };
        groups.push(cur);
      }
      cur.ids.push(id);
    }
    return groups;
  }

  function renderSectionGroupHTML(tree, group) {
    if (!group.sectionId) {
      return `<div class="section-grid">${group.ids.map((id) => renderNodeBlockHTML(tree.nodes[id])).join("")}</div>`;
    }
    const secs = sectionsOf(tree);
    const idx = secs.indexOf(group.sectionId);
    const slot = (idx % 5) + 1;
    const nn = String(idx + 1).padStart(2, "0");
    const secNode = tree.nodes[group.sectionId];
    const title = nodeTitle(secNode);
    const railHTML = railCardsForSection(tree, group.sectionId);
    return `<div class="section-block" data-section-id="${group.sectionId}" style="--sec-n: var(--sec-${slot})">
      <div class="section-header">
        <span class="section-kicker"><span class="pill-n">${nn}</span> &middot; ${escapeHtml(title.toUpperCase())}</span>
        <h1>${escapeHtml(title)}</h1>
        ${secNode.hook ? `<p class="section-hook">${escapeHtml(secNode.hook)}</p>` : ""}
      </div>
      <div class="section-grid">${group.ids
        .map((id) => renderNodeBlockHTML(tree.nodes[id], { sectionSelf: id === group.sectionId }))
        .join("")}</div>
      <div class="section-rail-inline">${railHTML}</div>
    </div>`;
  }

  // Provenance label for a list of leaf ids: "¶ 3" or "¶ 3–5".
  function citesProvenance(cites) {
    const li = state.leafIndex;
    if (!li) return "";
    const idxs = (cites || []).map((id) => li[id]).filter((x) => x != null);
    if (!idxs.length) return "";
    const mn = Math.min(...idxs);
    const mx = Math.max(...idxs);
    return mn === mx ? `¶ ${mn}` : `¶ ${mn}–${mx}`;
  }

  // The "what is this" card above section 01, shown at every zoom level:
  // kind pill, the document's own title, one plain sentence, and the few
  // essentials as a compact label/value grid (each with a ¶ link to the
  // source). Not a [data-node-id] block, so zoom anchoring ignores it.
  //
  // A task-like document ("Do it": an assignment, meeting notes, or a
  // do/plan goal) adds, in this order: Start here (the one first step),
  // Due (the deadline, as "Due in 5 days" worked out here from today's date),
  // Size of the job, then the essentials in the server's act-first order; and,
  // for meeting notes, an Actions list (who, what, due), earliest first as served.
  function sourceLinkHTML(cites) {
    const prov = citesProvenance(cites);
    return prov
      ? `<button type="button" class="provenance source-link" data-leaf="${escapeHtml((cites || [])[0] || "")}" title="Read the original text">${escapeHtml(prov)}</button>`
      : "";
  }

  // "Due in 5 days" plus the date as written; recomputed on every render.
  function dueInfo(iso, time, now) {
    const rel = window.DoIt && window.DoIt.relativeDue(iso, now);
    if (!rel) return null;
    return { rel, abs: window.DoIt.dueDateText(iso, time, now) };
  }

  const START_LABEL = /^(start here|first step|next action)\b/i;
  const DUE_LABEL = /^(due|deadline|reply by|submit by|submission)\b/i;

  function doItTilesHTML(ov, now) {
    const tiles = [];
    if (ov.start_here && ov.start_here.text) {
      tiles.push(`<div class="ov-item ov-start" style="--sec-n: var(--sec-2)">
        <dt><span>Start here</span>${sourceLinkHTML(ov.start_here.cites)}</dt>
        <dd><span>${renderInline(ov.start_here.text)}</span></dd>
      </div>`);
    }
    const dl = ov.deadline;
    const due = dl && dueInfo(dl.iso, dl.time, now);
    if (due) {
      tiles.push(`<div class="ov-item ov-due ov-due-${due.rel.state}" style="--sec-n: var(--sec-3)" data-due-iso="${escapeHtml(dl.iso)}" data-due-time="${escapeHtml(dl.time || "")}">
        <dt><span>Due</span>${sourceLinkHTML(dl.cites)}</dt>
        <dd><span><strong class="due-rel">${escapeHtml(due.rel.text)}</strong><span class="due-abs"> &middot; ${escapeHtml(due.abs)}</span>${dl.year_inferred ? ' <span class="year-assumed">year assumed</span>' : ""}${dl.label ? `<span class="due-what">${renderInline(dl.label)}</span>` : ""}</span></dd>
      </div>`);
    }
    const size = ov.size_of_job;
    if (size && size.text) {
      tiles.push(`<div class="ov-item ov-size" style="--sec-n: var(--sec-4)">
        <dt><span>Size of the job</span>${sourceLinkHTML(size.cites)}</dt>
        <dd><span>${renderInline(size.text)}${size.basis ? `<span class="ov-basis">Based on ${renderInline(size.basis)}</span>` : ""}</span></dd>
      </div>`);
    }
    return { html: tiles.join(""), hasStart: !!tiles.find((t) => t.includes("ov-start")), hasDue: !!due };
  }

  function actionsHTML(ov, now) {
    const acts = (ov.actions || []).filter((a) => a && a.who && a.what);
    if (!acts.length) return "";
    const rows = acts
      .map((a) => {
        const d = a.due_iso ? dueInfo(a.due_iso, null, now) : null;
        const written = a.due ? escapeHtml(a.due) : d ? escapeHtml(d.abs) : "";
        const dueHTML = d
          ? `<span class="act-due act-due-${d.rel.state}"><strong>${escapeHtml(d.rel.text)}</strong>${written ? ` &middot; ${written}` : ""}${a.year_inferred ? ' <span class="year-assumed">year assumed</span>' : ""}</span>`
          : written
            ? `<span class="act-due">${written}${a.year_inferred ? ' <span class="year-assumed">year assumed</span>' : ""}</span>`
            : "";
        return `<li class="ov-action">
          <span class="act-who">${escapeHtml(a.who)}</span>
          <span class="act-body"><span class="act-what">${renderInline(a.what)}</span>
            <span class="act-meta">${dueHTML}${sourceLinkHTML(a.cites)}</span></span>
        </li>`;
      })
      .join("");
    return `<div class="ov-actions"><h2 class="ov-actions-head">Actions</h2><ul class="ov-action-list">${rows}</ul></div>`;
  }

  function overviewHTML() {
    const tree = state.tree;
    const ov = tree && tree.overview;
    if (!ov || !ov.doc_title) return "";
    const now = new Date();
    const doit = doItTilesHTML(ov, now);
    const items = (ov.essentials || [])
      .filter((e) => !(doit.hasStart && START_LABEL.test((e.label || "").trim())) && !(doit.hasDue && DUE_LABEL.test((e.label || "").trim())))
      .map((e, i) => {
        const stated = !/^not stated\.?$/i.test((e.value || "").trim());
        return `<div class="ov-item" style="--sec-n: var(--sec-${(i % 5) + 1})">
          <dt><span>${escapeHtml(e.label)}</span>${sourceLinkHTML(e.cites)}</dt>
          <dd class="${stated ? "" : "ov-unstated"}"><span>${renderInline(e.value)}</span></dd>
        </div>`;
      })
      .join("");
    const tiles = doit.html + items;
    return `<section class="overview-card" aria-label="What this document is">
      <span class="ov-kind">${escapeHtml(ov.doc_kind || "")}</span>
      <h1 class="ov-title">${escapeHtml(ov.doc_title)}</h1>
      ${ov.what_it_is ? `<p class="ov-what">${renderInline(ov.what_it_is)}</p>` : ""}
      ${tiles ? `<dl class="ov-essentials">${tiles}</dl>` : ""}
      ${actionsHTML(ov, now)}
    </section>`;
  }

  // The day moves on while a document stays open: when the tab comes back,
  // re-word the due lines in place (no re-render, so nothing shifts).
  function refreshDueLines() {
    if (!state.tree || !state.tree.overview || !window.DoIt) return;
    const now = new Date();
    const dl = state.tree.overview.deadline;
    const tile = $content.querySelector(".ov-due");
    const due = dl && dueInfo(dl.iso, dl.time, now);
    if (tile && due) {
      tile.querySelector(".due-rel").textContent = due.rel.text;
      tile.className = tile.className.replace(/ov-due-\w+/, `ov-due-${due.rel.state}`);
    }
    const acts = (state.tree.overview.actions || []).filter((a) => a && a.who && a.what);
    $content.querySelectorAll(".ov-action").forEach((li, i) => {
      const a = acts[i];
      const d = a && a.due_iso ? dueInfo(a.due_iso, null, now) : null;
      const strong = li.querySelector(".act-due strong");
      if (d && strong) strong.textContent = d.rel.text;
    });
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshDueLines();
  });

  function contentHTML() {
    const tree = state.tree;
    const frontier = state.frontier;
    const overview = overviewHTML();
    if (frontier.length === 1 && frontier[0] === tree.root) {
      const root = tree.nodes[tree.root];
      const heading = overview
        ? `<span class="hero-kicker">THE GIST</span>`
        : `<h1>${escapeHtml(nodeTitle(root) || tree.title || "")}</h1>`;
      // A document short enough to be a single leaf has no summary: show its
      // own text, rendered as markdown like every other leaf.
      const body = !root.hook && root.is_leaf && root.text ? `<div class="node-body">${renderMarkdown(root.text)}</div>` : `<p>${escapeHtml(root.hook || root.text || "")}</p>`;
      return `${overview}<div class="root-hero${overview ? " has-overview" : ""}">${heading}${body}</div>`;
    }
    const groups = groupFrontierBySections(tree, frontier);
    return overview + groups.map((g) => renderSectionGroupHTML(tree, g)).join("");
  }

  // Natural (pre-transform) rects from the most recent render, keyed by
  // node id. FLIP applies a `transform` to persisted nodes immediately
  // after layout, which getBoundingClientRect() reflects right away — so
  // anything that needs the node's *true* resting position (the anchor
  // reposition logic in setZ) must read from here, not query the live DOM
  // mid-transition.
  let lastRenderRects = new Map();

  // Zoom transitions. Nothing here may change layout (the pointer anchor
  // is measured from lastRenderRects and pinned by scrolling), so every
  // effect is opacity, filter, box-shadow or a transform that settles to 0:
  // - passages leaving the frontier linger as fixed-position ghosts and fade out
  // - passages entering fade/unblur in with a brief pastel wash in their
  //   section hue, so it's obvious what just changed
  // - passages that stayed but moved glide to their new place (FLIP),
  //   measured after the anchor scroll so they don't start from a stale spot
  const GHOST_MS = 200;
  let $ghostLayer = null;

  function clearGhosts() {
    if ($ghostLayer) $ghostLayer.remove();
    $ghostLayer = null;
  }

  function captureGhosts(keepIds) {
    const ghosts = [];
    const vh = window.innerHeight;
    for (const elNode of $content.querySelectorAll("[data-node-id]")) {
      if (keepIds.has(elNode.dataset.nodeId)) continue;
      const r = elNode.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh || r.height === 0) continue;
      const clone = elNode.cloneNode(true);
      clone.removeAttribute("data-node-id");
      clone.querySelectorAll("[data-node-id]").forEach((n) => n.removeAttribute("data-node-id"));
      clone.classList.remove("fade-enter", "wash");
      clone.classList.add("zoom-ghost");
      const secN = getComputedStyle(elNode).getPropertyValue("--sec-n");
      Object.assign(clone.style, {
        left: `${r.left}px`,
        top: `${r.top}px`,
        width: `${r.width}px`,
        transform: "",
        transition: "",
      });
      if (secN) clone.style.setProperty("--sec-n", secN);
      ghosts.push(clone);
    }
    return ghosts;
  }

  function render(opts) {
    opts = opts || {};
    const prevRects = new Map();
    const animate = !REDUCED_MOTION && !opts.columnCrossfade;
    if (animate) {
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        prevRects.set(elNode.dataset.nodeId, elNode.getBoundingClientRect());
      }
    }

    const oldIds = Array.from($content.querySelectorAll("[data-node-id]")).map((n) => n.dataset.nodeId);
    const oldSet = new Set(oldIds);
    const oldForms = new Map(Array.from($content.querySelectorAll("[data-node-id]")).map((n) => [n.dataset.nodeId, n.dataset.form]));
    clearGhosts();
    const ghosts = animate && oldSet.size ? captureGhosts(new Set(state.frontier)) : [];

    if (opts.columnCrossfade && !REDUCED_MOTION) {
      $content.classList.add("column-crossfade");
      $content.style.opacity = "0";
      setTimeout(() => {
        doRender();
        if (opts.onRendered) opts.onRendered();
        if (window.RiemannMap) window.RiemannMap.update();
        requestAnimationFrame(() => {
          $content.style.opacity = "1";
          setTimeout(() => $content.classList.remove("column-crossfade"), 200);
        });
      }, 180);
      return;
    }

    doRender();
    if (opts.onRendered) opts.onRendered();
    if (animate) animateTransition();
    if (window.RiemannMap) window.RiemannMap.update();

    function doRender() {
      applyColumnMode(false);
      $content.innerHTML = contentHTML();
      applyHighlightsToDOM();
      if (search.open && search.query) applySearchMarks();
      updateHeader();
      updateNavCurrent();
      updateRail();

      lastRenderRects = new Map();
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        lastRenderRects.set(elNode.dataset.nodeId, elNode.getBoundingClientRect());
      }
    }

    function animateTransition() {
      if (ghosts.length) {
        $ghostLayer = document.createElement("div");
        $ghostLayer.className = "zoom-ghost-layer";
        $ghostLayer.setAttribute("aria-hidden", "true");
        ghosts.forEach((g) => $ghostLayer.appendChild(g));
        document.body.appendChild($ghostLayer);
        const layer = $ghostLayer;
        setTimeout(() => { if ($ghostLayer === layer) clearGhosts(); }, GHOST_MS + 40);
      }

      // Wash only on a real zoom step (something stayed on screen); on a
      // fresh open everything is new and a page-wide wash would just flash.
      const isStep = oldSet.size > 0 && state.frontier.some((id) => oldSet.has(id));
      for (const elNode of $content.querySelectorAll("[data-node-id]")) {
        const id = elNode.dataset.nodeId;
        if (oldForms.has(id) && oldForms.get(id) !== elNode.dataset.form) {
          elNode.classList.add("fade-enter", "wash");
          elNode.addEventListener("animationend", (e) => {
            if (e.target !== elNode) return;
            elNode.classList.remove("fade-enter", "wash");
          });
        } else if (prevRects.has(id)) {
          const dy = prevRects.get(id).top - elNode.getBoundingClientRect().top;
          if (Math.abs(dy) > 0.5) {
            elNode.style.transition = "none";
            elNode.style.transform = `translateY(${dy}px)`;
            requestAnimationFrame(() => {
              elNode.style.transition = "transform 260ms cubic-bezier(0.2, 0.7, 0.2, 1)";
              elNode.style.transform = "";
            });
          }
        } else if (!oldSet.has(id)) {
          elNode.classList.add("fade-enter");
          if (isStep) elNode.classList.add("wash");
          elNode.addEventListener("animationend", (e) => {
            if (e.target !== elNode) return;
            elNode.classList.remove("fade-enter", "wash");
          });
        }
      }
    }
  }

  function updateHeader() {
    const tree = state.tree;
    const root = tree.nodes[tree.root];
    $docTitle.textContent = ((tree.overview && tree.overview.doc_title) || tree.title || "").toUpperCase();
    const $obj = el("doc-objective");
    const objLabel = objectiveLabel(tree.objective);
    $obj.hidden = !objLabel;
    $obj.textContent = objLabel || "";
    let hookText = (root && (root.hook || root.text)) || "";
    if (tree.provisional_root) hookText += " · gist coming…";
    $docHook.textContent = hookText;
  }

  el("home-btn").addEventListener("click", () => goHome());

  // ---------------------------------------------------------------------
  // Highlights: apply to DOM, add/edit toolbar
  // ---------------------------------------------------------------------
  function applyHighlightsToDOM() {
    if (!state.highlights.length) return;
    for (const elNode of $content.querySelectorAll("[data-node-id]")) {
      const nodeId = elNode.dataset.nodeId;
      const body = elNode.querySelector(".node-body");
      if (!body) continue;
      const hls = state.highlights
        .filter((h) => h.nodeId === nodeId)
        .slice()
        .sort((a, b) => b.start - a.start); // reverse order so earlier offsets stay valid
      for (const h of hls) wrapTextRange(body, h.start, h.end, h.colour, h.id);
    }
  }

  function findTextPos(container, target) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let acc = 0;
    let node;
    while ((node = walker.nextNode())) {
      const len = node.textContent.length;
      if (acc + len >= target) return { node, offset: target - acc };
      acc += len;
    }
    return null;
  }

  function wrapTextRange(container, start, end, colour, hlId) {
    if (end <= start) return;
    const startPos = findTextPos(container, start);
    const endPos = findTextPos(container, end);
    if (!startPos || !endPos) return;
    try {
      const range = document.createRange();
      range.setStart(startPos.node, startPos.offset);
      range.setEnd(endPos.node, endPos.offset);
      const mark = document.createElement("mark");
      mark.style.setProperty("--mark-colour", colour);
      mark.dataset.hlId = hlId;
      try {
        range.surroundContents(mark);
      } catch (e) {
        const frag = range.extractContents();
        mark.appendChild(frag);
        range.insertNode(mark);
      }
    } catch (e) {
      /* offsets out of range for current markup; skip */
    }
  }

  function rangeStartOffset(container, range) {
    const pre = document.createRange();
    pre.selectNodeContents(container);
    pre.setEnd(range.startContainer, range.startOffset);
    return pre.toString().length;
  }

  function hideHighlightToolbar() {
    $hlToolbar.hidden = true;
    state.hlContext = null;
  }

  function positionToolbar(rect) {
    const top = Math.max(8, rect.top - 44);
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - 260));
    $hlToolbar.style.top = `${top}px`;
    $hlToolbar.style.left = `${left}px`;
  }

  function renderHighlightToolbar(ctx) {
    const current = ctx.mode === "edit" ? ctx.colour : state.palette.hl;
    const swatches = TOOLBAR_SWATCH_IDX.map((i) => {
      const [label, c] = PALETTE[i];
      return `<button type="button" class="hl-swatch" data-hex="${c}" aria-label="${label}" aria-pressed="${
        current === c
      }" style="background:${c}"></button>`;
    }).join("");
    const actionBtn =
      ctx.mode === "edit"
        ? `<button type="button" class="hl-action" data-action="remove">Remove</button>`
        : `<button type="button" class="hl-action" data-action="cancel">Cancel</button>`;
    $hlToolbar.innerHTML = `${swatches}<span class="hl-sep"></span>${actionBtn}`;
    $hlToolbar.hidden = false;
    state.hlContext = ctx;
  }

  function showHighlightToolbar(rect, ctx) {
    positionToolbar(rect);
    renderHighlightToolbar(ctx);
  }

  function handleSelectionMaybeShowToolbar() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !sel.toString().trim()) {
      if (state.hlContext && state.hlContext.mode === "add") hideHighlightToolbar();
      return;
    }
    const range = sel.getRangeAt(0);
    const container = range.commonAncestorContainer;
    const startEl = container.nodeType === 1 ? container : container.parentElement;
    const body = startEl && startEl.closest(".node-body");
    if (!body) return;
    const wrapper = body.closest("[data-node-id]");
    if (!wrapper) return;
    const nodeId = wrapper.dataset.nodeId;
    const start = rangeStartOffset(body, range);
    const end = start + range.toString().length;
    if (end <= start) return;
    showHighlightToolbar(range.getBoundingClientRect(), { mode: "add", nodeId, start, end });
  }

  // e.target on a mouseup/mousedown is frequently a Text node (a selection
  // commonly ends inside one) or even `document` itself — neither has
  // `.closest`, so normalize to the nearest Element first.
  function targetElement(e) {
    const t = e.target;
    if (!t) return null;
    if (t.nodeType === 1) return t;
    return t.parentElement || null;
  }

  document.addEventListener("mouseup", (e) => {
    const t = targetElement(e);
    if (t && t.closest("#highlight-toolbar")) return;
    setTimeout(handleSelectionMaybeShowToolbar, 0);
  });

  document.addEventListener("mousedown", (e) => {
    const t = targetElement(e);
    if (t && t.closest("#highlight-toolbar")) return;
    if (t && t.closest("mark[data-hl-id]")) return;
    if (!$hlToolbar.hidden) hideHighlightToolbar();
  });

  $hlToolbar.addEventListener("click", (e) => {
    const swatchBtn = e.target.closest(".hl-swatch");
    const actionBtn = e.target.closest(".hl-action");
    const ctx = state.hlContext;
    if (!ctx) return;
    if (swatchBtn) {
      const hex = swatchBtn.dataset.hex;
      if (ctx.mode === "add") {
        const id = "hl" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        state.highlights.push({ id, nodeId: ctx.nodeId, start: ctx.start, end: ctx.end, colour: hex });
        logEvent("highlight", { action: "add", tree_id: state.tree.id, node_id: ctx.nodeId, colour: hex });
      } else {
        const h = state.highlights.find((x) => x.id === ctx.id);
        if (h) {
          h.colour = hex;
          logEvent("highlight", { action: "recolour", tree_id: state.tree.id, node_id: h.nodeId, colour: hex });
        }
      }
      saveHighlights();
      hideHighlightToolbar();
      window.getSelection().removeAllRanges();
      render({});
    } else if (actionBtn && actionBtn.dataset.action === "remove") {
      const idx = state.highlights.findIndex((x) => x.id === ctx.id);
      if (idx >= 0) {
        const [rm] = state.highlights.splice(idx, 1);
        logEvent("highlight", { action: "remove", tree_id: state.tree.id, node_id: rm.nodeId, colour: rm.colour });
      }
      saveHighlights();
      hideHighlightToolbar();
      render({});
    } else {
      hideHighlightToolbar();
      window.getSelection().removeAllRanges();
    }
  });

  $content.addEventListener("click", (e) => {
    const mark = e.target.closest("mark[data-hl-id]");
    if (mark) {
      e.stopPropagation();
      const h = state.highlights.find((x) => x.id === mark.dataset.hlId);
      if (h) showHighlightToolbar(mark.getBoundingClientRect(), { mode: "edit", id: h.id, colour: h.colour });
      return;
    }
    const link = e.target.closest(".source-link");
    if (!link) {
      return;
    }
    if (link.dataset.leaf) {
      if (state.tree.nodes[link.dataset.leaf]) jumpToLeaf(link.dataset.leaf);
      return;
    }
    const nodeEl = link.closest("[data-node-id]");
    const node = state.tree.nodes[nodeEl.dataset.nodeId];
    if (!node || !node.cites || node.cites.length === 0) return;
    jumpToLeaf(node.cites[0]);
  });

  // ---------------------------------------------------------------------
  // Palette panel
  // ---------------------------------------------------------------------
  function renderPalettePanel() {
    const $presets = el("palette-presets");
    $presets.innerHTML = PRESETS.map((p) => {
      const pressed = state.palette.preset === p.name;
      const dots = p.sections.map((c) => `<span style="background:${c}"></span>`).join("");
      return `<button type="button" class="palette-preset" data-preset="${p.name}" aria-pressed="${pressed}"><span class="dots">${dots}</span><span>${p.name}</span></button>`;
    }).join("");

    const $slots = el("palette-slots");
    $slots.innerHTML = state.palette.sections
      .map((c, i) => {
        const pressed = state.paletteMode === "sections" && state.paletteSlot === i;
        return `<button type="button" class="palette-slot" data-slot="${i}" aria-pressed="${pressed}" aria-label="Section ${
          i + 1
        } colour" style="background:${c}">${String(i + 1).padStart(2, "0")}</button>`;
      })
      .join("");

    el("palette-swatch-heading").textContent =
      state.paletteMode === "highlight"
        ? "PASTELS · CHOOSING THE HIGHLIGHTER COLOUR"
        : `PASTELS · CHOOSING SECTION ${String(state.paletteSlot + 1).padStart(2, "0")}'S COLOUR`;

    const target = state.paletteMode === "highlight" ? state.palette.hl : state.palette.sections[state.paletteSlot];
    el("palette-swatches").innerHTML = PALETTE.map(([label, c]) => {
      const pressed = target === c;
      return `<button type="button" class="palette-swatch" data-hex="${c}" aria-label="${label}" title="${label}" aria-pressed="${pressed}" style="background:${c}"></button>`;
    }).join("");

    el("mode-highlight").setAttribute("aria-pressed", state.paletteMode === "highlight");
    el("mode-sections").setAttribute("aria-pressed", state.paletteMode === "sections");
  }

  function renderPaletteOpenState(opts) {
    $palettePanel.hidden = !state.paletteOpen;
    $paletteBtn.setAttribute("aria-expanded", String(state.paletteOpen));
    $paletteBtn.setAttribute("aria-pressed", String(state.paletteOpen));
    if (state.paletteOpen) {
      renderPalettePanel();
      const first = $palettePanel.querySelector("button");
      if (first) first.focus();
    } else if (!(opts && opts.keepFocus)) {
      $paletteBtn.focus();
    }
  }

  // Clicking anywhere outside the open palette closes it (focus stays
  // wherever the click put it, rather than jumping back to the button).
  document.addEventListener("pointerdown", (e) => {
    if (!state.paletteOpen) return;
    if ($palettePanel.contains(e.target) || $paletteBtn.contains(e.target)) return;
    state.paletteOpen = false;
    renderPaletteOpenState({ keepFocus: true });
  });

  $paletteBtn.addEventListener("click", () => {
    state.paletteOpen = !state.paletteOpen;
    renderPaletteOpenState();
  });
  el("palette-close").addEventListener("click", () => {
    state.paletteOpen = false;
    renderPaletteOpenState();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$hlToolbar.hidden) {
      hideHighlightToolbar();
      window.getSelection().removeAllRanges();
      return;
    }
    if (state.paletteOpen && e.key === "Escape") {
      state.paletteOpen = false;
      renderPaletteOpenState();
    }
  });
  $palettePanel.addEventListener("keydown", (e) => {
    if (e.key !== "Tab" || !state.paletteOpen) return;
    const f = Array.from($palettePanel.querySelectorAll("button")).filter((b) => b.offsetParent !== null);
    if (!f.length) return;
    const first = f[0];
    const last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  el("palette-presets").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-preset]");
    if (!btn) return;
    const p = PRESETS.find((pp) => pp.name === btn.dataset.preset);
    if (!p) return;
    state.palette = { sections: p.sections.slice(), hl: p.hl, preset: p.name };
    applyPaletteToCSS();
    savePalette();
    renderPalettePanel();
    logEvent("palette", { field: "preset", value: p.name });
  });

  el("palette-slots").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-slot]");
    if (!btn) return;
    state.paletteMode = "sections";
    state.paletteSlot = Number(btn.dataset.slot);
    renderPalettePanel();
  });

  el("palette-swatches").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-hex]");
    if (!btn) return;
    const hex = btn.dataset.hex;
    if (state.paletteMode === "highlight") {
      state.palette = { sections: state.palette.sections.slice(), hl: hex, preset: null };
      logEvent("palette", { field: "hl", value: hex });
    } else {
      const sections = state.palette.sections.slice();
      sections[state.paletteSlot] = hex;
      state.palette = { sections, hl: state.palette.hl, preset: null };
      logEvent("palette", { field: "slot", value: { slot: state.paletteSlot, colour: hex } });
    }
    applyPaletteToCSS();
    savePalette();
    renderPalettePanel();
  });

  el("mode-highlight").addEventListener("click", () => {
    state.paletteMode = "highlight";
    renderPalettePanel();
  });
  el("mode-sections").addEventListener("click", () => {
    state.paletteMode = "sections";
    renderPalettePanel();
  });

  // ---------------------------------------------------------------------
  // Dial control
  // ---------------------------------------------------------------------
  function setZ(newZ, inputType, forcedBeforeY) {
    markInput();
    state.lastDialChangeAt = Date.now();
    const clamped = Math.max(0, Math.min(1, newZ));
    const zFrom = state.z;
    if (state.sequence && state.frontier &&
        window.Frontier.zToK(clamped, state.sequence.length) === window.Frontier.zToK(zFrom, state.sequence.length)) {
      state.z = clamped;
      updateReadout();
      return;
    }
    if (!state.anchorNodeId) setAnchor(findCentreNodeId());

    let beforeY = forcedBeforeY;
    if (beforeY == null) {
      const anchorEl = $content.querySelector(`[data-node-id="${state.anchorNodeId}"]`);
      beforeY = anchorEl ? pinY(state.anchorNodeId, anchorEl.getBoundingClientRect(), state.anchorOffset) : null;
    }

    state.z = clamped;
    const { frontier, prose } = window.Frontier.frontierAtZ(state.tree, state.sequence, state.z);
    state.frontier = frontier;
    state.prose = prose;

    const GESTURES = ["zkey", "ctrlwheel", "key", "jump"];
    const bigJump = Math.abs(clamped - zFrom) > 0.15 && !GESTURES.includes(inputType);
    render({
      columnCrossfade: bigJump,
      onRendered: () => {
        const offset = state.anchorOffset != null ? state.anchorOffset : 0;
        const replacement = window.Frontier.findFrontierNodeAtOffset(state.tree, state.frontier, offset);
        if (replacement) {
          state.anchorNodeId = replacement;
          if (state.pinActive) markPinned(replacement);
          const afterRect = lastRenderRects.get(replacement);
          if (afterRect && beforeY != null) {
            const delta = pinY(replacement, afterRect, offset) - beforeY;
            const deficit = -(window.scrollY + delta);
            if (deficit > 0) {
              topSpacerPx += deficit;
              $topSpacer.style.height = `${topSpacerPx}px`;
              window.scrollTo(0, 0);
            } else {
              window.scrollBy(0, delta);
            }
          }
        }
      },
    });

    updateReadout();
    savePositionDebounced();
    dismissHint();
    hideHighlightToolbar();
    if (state.tree) {
      logEvent("dial", {
        tree_id: state.tree.id,
        z_from: zFrom,
        z_to: clamped,
        input: inputType || "indicator",
        anchor_node_id: state.anchorNodeId,
      });
    }
  }

  // Zoom pin. A gesture pins the passage under the pointer by its top edge
  // (its subheading): that edge holds its screen position for the whole
  // gesture, and whichever block contains the pinned source position after
  // each step takes its place, outlined so you can see what's pinned. A
  // summary therefore unfolds downward from its own heading, and zooming
  // out folds back up into the heading that contains it. If that heading
  // is already scrolled off the top, pin the exact spot under the pointer
  // instead so the line being read doesn't move.
  function contentTopY() {
    const hb = el("app-header").getBoundingClientRect().bottom;
    const nb = $sectionNav.getBoundingClientRect();
    // On narrow screens the nav is a sticky pill row under the header.
    const navIsRow = nb.width > window.innerWidth * 0.6 && nb.height > 0 && nb.top <= hb + 1;
    return (navIsRow ? nb.bottom : hb) + 8;
  }

  // Spatial view hooks (web/map.js). Frontier passages whose blocks are on
  // screen, in reading order, below the header/nav.
  function visibleFrontierIds() {
    const top = contentTopY();
    const bottom = window.innerHeight;
    const ids = [];
    for (const n of $content.querySelectorAll("[data-node-id]")) {
      const r = n.getBoundingClientRect();
      if (r.height > 0 && r.bottom > top && r.top < bottom) ids.push(n.dataset.nodeId);
    }
    return ids;
  }

  // Run fn (which reflows the page, e.g. opening the map) and scroll so the
  // anchor passage keeps its screen y. Same deficit handling as setZ.
  function keepReadingPosition(fn) {
    const top = contentTopY();
    const bottom = window.innerHeight;
    let elAnchor = state.anchorNodeId && $content.querySelector(`[data-node-id="${state.anchorNodeId}"]`);
    if (elAnchor) {
      const r = elAnchor.getBoundingClientRect();
      if (!(r.bottom > top && r.top < bottom)) elAnchor = null;
    }
    if (!elAnchor) {
      for (const n of $content.querySelectorAll("[data-node-id]")) {
        const r = n.getBoundingClientRect();
        if (r.bottom > top && r.top < bottom) {
          elAnchor = n;
          break;
        }
      }
    }
    const before = elAnchor ? elAnchor.getBoundingClientRect().top : null;
    state.lastDialChangeAt = Date.now(); // the scroll below is not a re-anchor
    fn();
    if (!elAnchor || !elAnchor.isConnected || before == null) return;
    const delta = elAnchor.getBoundingClientRect().top - before;
    if (Math.abs(delta) < 0.25) return;
    const deficit = -(window.scrollY + delta);
    if (deficit > 0) {
      topSpacerPx += deficit;
      $topSpacer.style.height = `${topSpacerPx}px`;
      window.scrollTo(0, 0);
    } else {
      window.scrollBy(0, delta);
    }
  }

  function beginPointerGesture(px, py) {
    let x = px;
    let y = py;
    if (x == null || y == null) {
      x = lastMouse.x;
      y = lastMouse.y;
    }
    let anchorId;
    let anchorY;
    if (isPointOverContent(x, y)) {
      anchorId = nodeAtScreenPoint(x, y) || findCentreNodeId();
      anchorY = y;
    } else {
      anchorId = findCentreNodeId();
      anchorY = window.innerHeight / 2;
    }
    if (anchorId && (anchorId !== state.anchorNodeId || anchorId !== state.sequenceAnchor)) setAnchor(anchorId);
    const elAnchor = anchorId && $content.querySelector(`[data-node-id="${anchorId}"]`);
    if (!elAnchor) return anchorY;
    const rect = elAnchor.getBoundingClientRect();
    const node = state.tree.nodes[anchorId];
    showPin(anchorId);
    if (rect.top >= contentTopY()) {
      state.pinMode = "top";
      // Just inside the block, so a boundary shared with the previous
      // sibling never resolves to that sibling.
      state.anchorOffset = node.source_span[0] + 0.5;
      return rect.top;
    }
    state.pinMode = "point";
    state.anchorOffset = offsetAtY(anchorId, rect, anchorY);
    return anchorY;
  }

  function pinY(nodeId, rect, offset) {
    return state.pinMode === "top" ? rect.top : yOfOffset(nodeId, rect, offset);
  }

  // Pin outline: shown from gesture start until it ends (Z released, wheel
  // burst over, or shortly after a single key/button step).
  let pinTimer = null;
  function showPin(nodeId) {
    clearTimeout(pinTimer);
    state.pinActive = true;
    markPinned(nodeId);
  }
  function markPinned(nodeId) {
    $content.querySelectorAll(".node.pinned").forEach((n) => n.classList.remove("pinned"));
    const elNode = nodeId && $content.querySelector(`[data-node-id="${nodeId}"]`);
    if (elNode) elNode.classList.add("pinned");
  }
  function endPin(delayMs) {
    clearTimeout(pinTimer);
    pinTimer = setTimeout(() => {
      state.pinActive = false;
      $content.querySelectorAll(".node.pinned").forEach((n) => n.classList.remove("pinned"));
    }, delayMs || 0);
  }

  function offsetAtY(nodeId, rect, y) {
    const [s0, s1] = state.tree.nodes[nodeId].source_span;
    const frac = rect.height > 0 ? Math.min(1, Math.max(0, (y - rect.top) / rect.height)) : 0.5;
    return s0 + frac * (s1 - s0);
  }
  function yOfOffset(nodeId, rect, offset) {
    const [s0, s1] = state.tree.nodes[nodeId].source_span;
    const frac = s1 > s0 ? Math.min(1, Math.max(0, (offset - s0) / (s1 - s0))) : 0.5;
    return rect.top + frac * rect.height;
  }

  let lockedPendingSteps = 0;
  let lockedInput = null;
  let lockedY = null;
  let lockedRaf = false;
  function queueLockedSteps(n, inputType, fixedY) {
    lockedPendingSteps += n;
    lockedInput = inputType;
    lockedY = fixedY;
    if (lockedRaf) return;
    lockedRaf = true;
    requestAnimationFrame(() => {
      lockedRaf = false;
      const n2 = lockedPendingSteps;
      lockedPendingSteps = 0;
      if (n2 === 0 || !state.tree) return;
      const total = Math.max(1, state.sequence.length);
      setZ(state.z + n2 / total, lockedInput, lockedY);
    });
  }

  function stepOnce(deltaSteps, inputType) {
    if (!state.tree || deltaSteps === 0) return;
    const anchorY = beginPointerGesture(lastMouse.x, lastMouse.y);
    const total = Math.max(1, state.sequence.length);
    setZ(state.z + deltaSteps / total, inputType, anchorY);
    endPin(900);
    recordHistory("zoom");
  }

  // The pill's Less/More buttons step at the viewport-centre anchor,
  // regardless of where the pointer happens to be.
  function stepAtViewportCentre(deltaSteps) {
    if (!state.tree) return;
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const anchorY = beginPointerGesture(cx, cy);
    const total = Math.max(1, state.sequence.length);
    setZ(state.z + deltaSteps / total, "key", anchorY);
    endPin(900);
    recordHistory("zoom");
  }
  el("zoom-less").addEventListener("click", () => stepAtViewportCentre(-1));
  el("zoom-more").addEventListener("click", () => stepAtViewportCentre(1));

  // ---- Keyboard: arrow keys / Home / End on the focused dial ----
  $dial.addEventListener("keydown", (e) => {
    switch (e.key) {
      case "ArrowRight":
        e.preventDefault();
        stepOnce(e.shiftKey ? 5 : 1, "key");
        break;
      case "ArrowLeft":
        e.preventDefault();
        stepOnce(e.shiftKey ? -5 : -1, "key");
        break;
      case "Home":
        e.preventDefault();
        setZ(0, "key");
        break;
      case "End":
        e.preventDefault();
        setZ(1, "key");
        break;
    }
  });

  // ---- Keyboard: =/- as a global expand/collapse-one-step alternative ----
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active")) return;
    // Ctrl/Cmd with +/-/0 is the browser's own page zoom; leave it alone.
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    if (e.key === "=" || e.key === "+") {
      e.preventDefault();
      stepOnce(1, "key");
    } else if (e.key === "-" || e.key === "_") {
      e.preventDefault();
      stepOnce(-1, "key");
    }
  });

  // ---- Gesture 1: Z zoom. Hold Z and move the mouse horizontally, or tap Z
  // for a sticky zoom mode driven by the mouse, a two-finger scroll or swipe.
  // (On Linux the trackpad is ignored while a letter key is held, so "hold Z
  // and move" cannot work there; a quick tap keeps the mode on instead.) ----
  const Z_STEP_PX = 24;
  const Z_TAP_MS = 250; // released sooner than this: sticky mode
  const Z_IDLE_MS = 1500; // sticky mode ends after this long with no zoom input
  const Z_WHEEL_PX_PER_STEP = 40;
  let zHeld = false;
  let zSticky = false;
  let zDownAt = 0;
  let zStartX = null;
  let zAppliedSteps = 0;
  let zGestureY = null;
  let zWheelAccum = 0;
  let zIdleTimer = null;
  const $zoomMode = el("zoom-mode");

  function zoomModeTouch() {
    if (!zSticky) return;
    clearTimeout(zIdleTimer);
    zIdleTimer = setTimeout(endZGesture, Z_IDLE_MS);
  }
  function zMoveHandler(e) {
    if ((!zHeld && !zSticky) || zStartX == null) return;
    const totalDeltaX = e.clientX - zStartX;
    const targetSteps = Math.trunc(totalDeltaX / Z_STEP_PX);
    const diff = targetSteps - zAppliedSteps;
    if (diff !== 0) {
      zAppliedSteps = targetSteps;
      queueLockedSteps(diff, "zkey", zGestureY);
      zoomModeTouch();
    }
  }
  // Sticky mode: two-finger scroll (wheel without Ctrl, either axis). Up or
  // right expands, down or left collapses. Ctrl+wheel (pinch) is Gesture 2.
  function zWheelHandler(e) {
    if (!zSticky || e.ctrlKey) return;
    e.preventDefault();
    const dominantX = Math.abs(e.deltaX) > Math.abs(e.deltaY);
    const raw = dominantX ? e.deltaX : -e.deltaY; // up / right positive
    const unit = e.deltaMode === 1 ? 3 : e.deltaMode === 2 ? 1 / 3 : Z_WHEEL_PX_PER_STEP;
    zWheelAccum += raw / unit;
    const steps = Math.trunc(zWheelAccum);
    if (steps !== 0) {
      zWheelAccum -= steps;
      queueLockedSteps(steps, "zkey", zGestureY);
    }
    zoomModeTouch();
  }
  function zPointerDown() {
    if (zSticky) endZGesture();
  }
  function zEscape(e) {
    if (zSticky && e.key === "Escape") endZGesture();
  }
  function endZGesture() {
    if (!zHeld && !zSticky) return;
    zHeld = false;
    zSticky = false;
    zStartX = null;
    zAppliedSteps = 0;
    zWheelAccum = 0;
    zGestureY = null;
    clearTimeout(zIdleTimer);
    endPin(350);
    recordHistory("zoom");
    document.body.classList.remove("zoom-drag-active");
    if ($zoomMode) $zoomMode.hidden = true;
    window.removeEventListener("mousemove", zMoveHandler);
    window.removeEventListener("wheel", zWheelHandler, { passive: false });
    window.removeEventListener("pointerdown", zPointerDown, true);
    window.removeEventListener("keydown", zEscape, true);
  }
  function beginStickyZ() {
    zHeld = false;
    zSticky = true;
    zWheelAccum = 0;
    if ($zoomMode) $zoomMode.hidden = false;
    window.addEventListener("wheel", zWheelHandler, { passive: false });
    window.addEventListener("pointerdown", zPointerDown, true);
    window.addEventListener("keydown", zEscape, true);
    zoomModeTouch();
  }
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active")) return;
    if (e.key !== "z" && e.key !== "Z") return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    if (zSticky) {
      // another Z tap leaves the mode
      if (!e.repeat) endZGesture();
      return;
    }
    if (e.repeat || zHeld) return;
    zHeld = true;
    zDownAt = performance.now();
    zStartX = lastMouse.x;
    zAppliedSteps = 0;
    zGestureY = beginPointerGesture(lastMouse.x, lastMouse.y);
    document.body.classList.add("zoom-drag-active");
    window.addEventListener("mousemove", zMoveHandler);
  });
  document.addEventListener("keyup", (e) => {
    if (e.key !== "z" && e.key !== "Z") return;
    if (zHeld && performance.now() - zDownAt < Z_TAP_MS) beginStickyZ();
    else if (zHeld) endZGesture();
  });
  window.addEventListener("blur", endZGesture);

  // ---- Gesture 2: Ctrl+wheel and trackpad pinch (arrives as ctrl+wheel) ----
  let wheelAccum = 0;
  let wheelBurstActive = false;
  let wheelGestureY = null;
  let wheelBurstTimer = null;
  window.addEventListener(
    "wheel",
    (e) => {
      if (!$app.classList.contains("active") || !e.ctrlKey) return;
      e.preventDefault();
      if (!wheelBurstActive) {
        wheelGestureY = beginPointerGesture(e.clientX, e.clientY);
        wheelBurstActive = true;
      }
      clearTimeout(wheelBurstTimer);
      wheelBurstTimer = setTimeout(() => {
        wheelBurstActive = false;
        endPin(350);
        recordHistory("zoom");
      }, 250);

      const magnitude = Math.abs(e.deltaY);
      const looksLikePinch = magnitude > 0 && (magnitude < 4 || !Number.isInteger(e.deltaY));
      const divisor = looksLikePinch ? 6 : 100;
      wheelAccum += -e.deltaY / divisor;
      const steps = Math.trunc(wheelAccum);
      if (steps !== 0) {
        wheelAccum -= steps;
        queueLockedSteps(steps, "ctrlwheel", wheelGestureY);
      }
    },
    { passive: false }
  );

  // ---------------------------------------------------------------------
  // One-time hint
  // ---------------------------------------------------------------------
  const HINT_KEY = "riemann:hint-seen";
  let hintTimer = null;
  function hintSeen() {
    try {
      return localStorage.getItem(HINT_KEY) === "1";
    } catch (e) {
      return true;
    }
  }
  function markHintSeen() {
    try {
      localStorage.setItem(HINT_KEY, "1");
    } catch (e) {}
  }
  function maybeShowHint() {
    if (!$zoomHint || hintSeen()) return;
    markHintSeen();
    // Touch screens have no Z key or wheel: point at the buttons instead.
    if (window.matchMedia && window.matchMedia("(hover: none)").matches) {
      $zoomHint.textContent = "Tap More + for more detail and \u2212 Less for less.";
    }
    $zoomHint.hidden = false;
    requestAnimationFrame(() => $zoomHint.classList.add("visible"));
    hintTimer = setTimeout(dismissHint, 8000);
  }
  function dismissHint() {
    if (!$zoomHint || $zoomHint.hidden) return;
    clearTimeout(hintTimer);
    hintTimer = null;
    $zoomHint.classList.remove("visible");
    $zoomHint.hidden = true;
  }

  // ---------------------------------------------------------------------
  // Minimal chrome toggle
  // ---------------------------------------------------------------------
  function toggleMinimalChrome() {
    state.minimalChrome = !state.minimalChrome;
    document.body.classList.toggle("minimal-chrome", state.minimalChrome);
  }
  el("minimal-toggle").addEventListener("click", toggleMinimalChrome);
  document.addEventListener("keydown", (e) => {
    if (e.key === "m" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      toggleMinimalChrome();
    }
  });

  // ---------------------------------------------------------------------
  // Click-to-jump to source (the ¶ label on summaries)
  // ---------------------------------------------------------------------
  function jumpToLeaf(leafId) {
    logEvent("jump_source", { tree_id: state.tree.id, leaf_id: leafId });
    jumpToNode(leafId);
  }

  // Jump to a node (a section from the nav or "Up next", or a source
  // paragraph from a ¶ link): open just enough for it to be on the page,
  // never folding anything already open, then scroll it to the top of the
  // reading area and flash its outline so it's obvious where you landed.
  function jumpToNode(nodeId) {
    const tree = state.tree;
    if (!tree || !tree.nodes[nodeId]) return;
    setAnchor(nodeId);

    const total = Math.max(1, state.sequence.length);
    const neededK = window.Frontier.kToReveal(tree, state.sequence, nodeId);
    if (neededK > window.Frontier.zToK(state.z, total)) setZ(neededK / total, "jump");

    const isSection = sectionsOf(tree).includes(nodeId);
    const target =
      (isSection && $content.querySelector(`.section-block[data-section-id="${nodeId}"]`)) ||
      $content.querySelector(`[data-node-id="${nodeId}"]`) ||
      firstRenderedDescendant(nodeId);
    if (!target) return;

    state.lastDialChangeAt = Date.now() + 600; // don't let the scroll re-anchor mid-jump
    const top = window.scrollY + target.getBoundingClientRect().top - contentTopY() - 8;
    window.scrollTo({ top: Math.max(0, top), behavior: REDUCED_MOTION ? "auto" : "smooth" });

    const block = target.matches("[data-node-id]") ? target : target.querySelector("[data-node-id]");
    if (block) {
      showPin(block.dataset.nodeId);
      endPin(1200);
    }
    updateNavCurrent();
    updateRail();
    recordHistory("jump");
  }

  function firstRenderedDescendant(nodeId) {
    const [s0, s1] = state.tree.nodes[nodeId].source_span;
    for (const elNode of $content.querySelectorAll("[data-node-id]")) {
      const n = state.tree.nodes[elNode.dataset.nodeId];
      if (n && n.source_span[0] >= s0 && n.source_span[0] < s1) return elNode;
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Zoom history: Alt+Left goes back to the previous zoom level AND position (the page
  // as it was: what is open and in which form, the anchor passage and where it sat on
  // screen); Alt+Right goes forward. An entry is taken at the end of each zoom gesture,
  // section jump, search jump and map jump; entries within about a second merge. After
  // a big jump (3 or more zoom steps, or another section) a "Back" button shows for 6 s.
  // This is in-memory per open document; the browser's own history (the #/t/<id> hash)
  // is not touched, and Alt+Left never reaches the browser's Back while a document is open.
  // ---------------------------------------------------------------------
  const HIST_COALESCE_MS = 1000;
  const HIST_SETTLE_MS = 650; // let a smooth scroll finish before the position is taken
  const HIST_BIG_STEPS = 3;
  const HIST_BACK_MS = 6000;
  const hist = { entries: [], idx: -1, timer: null, lastAt: 0, backTimer: null, restoring: false, kind: null };
  const $histBack = el("hist-back");

  function histSnapshot() {
    const tree = state.tree;
    const total = Math.max(1, state.sequence.length);
    const offset = state.anchorOffset;
    const onPage = offset != null ? window.Frontier.findFrontierNodeAtOffset(tree, state.frontier, offset) : null;
    const elA = onPage && $content.querySelector(`[data-node-id="${onPage}"]`);
    return {
      z: state.z,
      k: window.Frontier.zToK(state.z, total),
      frontier: state.frontier.slice(),
      prose: Array.from(state.prose),
      anchorId: state.anchorNodeId,
      anchorOffset: offset,
      pageAnchor: onPage || null,
      anchorTop: elA ? elA.getBoundingClientRect().top : null,
      scrollY: window.scrollY,
      section: state.anchorNodeId ? sectionAncestor(tree, state.anchorNodeId) : null,
    };
  }

  function sameHistPage(a, b) {
    return a.frontier.length === b.frontier.length && a.frontier.every((x, i) => x === b.frontier[i]) &&
      a.prose.length === b.prose.length && a.prose.every((x) => b.prose.includes(x));
  }

  function hideHistBack() {
    clearTimeout(hist.backTimer);
    $histBack.hidden = true;
  }

  function showHistBack() {
    const pill = document.querySelector(".zoom-pill");
    if (pill) {
      const r = pill.getBoundingClientRect();
      $histBack.style.top = `${Math.round(r.bottom + 8)}px`;
      $histBack.style.right = `${Math.max(8, Math.round(window.innerWidth - r.right))}px`;
    }
    $histBack.hidden = false;
    clearTimeout(hist.backTimer);
    hist.backTimer = setTimeout(hideHistBack, HIST_BACK_MS);
  }

  function histTake() {
    hist.timer = null;
    if (!state.tree || hist.restoring) return;
    const snap = histSnapshot();
    const prev = hist.entries[hist.idx];
    const now = Date.now();
    if (prev && sameHistPage(prev, snap) && prev.section === snap.section) {
      // nothing zoomed or jumped: just remember where we are scrolled
      prev.anchorTop = snap.anchorTop;
      prev.scrollY = snap.scrollY;
      prev.anchorId = snap.anchorId;
      prev.anchorOffset = snap.anchorOffset;
      return;
    }
    const big = !!prev && (Math.abs(snap.k - prev.k) >= HIST_BIG_STEPS || (snap.section && prev.section && snap.section !== prev.section));
    if (prev && !prev.base && now - hist.lastAt < HIST_COALESCE_MS && hist.idx === hist.entries.length - 1) {
      // within about a second of the last entry: that entry becomes this state
      const keepBig = prev.big;
      hist.entries[hist.idx] = Object.assign(snap, { big: keepBig || big });
    } else {
      hist.entries.length = hist.idx + 1; // a new branch drops the forward entries
      hist.entries.push(Object.assign(snap, { big }));
      hist.idx = hist.entries.length - 1;
    }
    hist.lastAt = now;
    if (hist.idx > 0 && hist.entries[hist.idx].big) showHistBack();
  }

  // Called at the end of a zoom gesture, section jump, search jump or map jump.
  function recordHistory(kind) {
    if (!state.tree || hist.restoring) return;
    hist.kind = kind || hist.kind;
    clearTimeout(hist.timer);
    hist.timer = setTimeout(histTake, HIST_SETTLE_MS);
  }

  function flushHistory() {
    if (hist.timer) {
      clearTimeout(hist.timer);
      histTake();
    }
  }

  function histReset() {
    clearTimeout(hist.timer);
    hist.timer = null;
    hist.entries = [];
    hist.idx = -1;
    hist.lastAt = 0;
    hideHistBack();
    if (state.tree) {
      hist.entries.push(Object.assign(histSnapshot(), { big: false, base: true }));
      hist.idx = 0;
    }
  }

  function histRestore(e) {
    const tree = state.tree;
    hist.restoring = true;
    try {
      state.frontier = e.frontier.filter((id) => tree.nodes[id]);
      state.prose = new Set(e.prose.filter((id) => tree.nodes[id]));
      const anchor = e.anchorId && tree.nodes[e.anchorId] ? e.anchorId : tree.root;
      state.anchorNodeId = anchor;
      state.anchorOffset = e.anchorOffset;
      state.pinMode = "point";
      state.sequence = sequenceKeepingPage(anchor);
      state.sequenceAnchor = anchor;
      resetTopSpacer();
      render({});
      updateReadout();
      const target = (e.pageAnchor && $content.querySelector(`[data-node-id="${e.pageAnchor}"]`)) || null;
      state.lastDialChangeAt = Date.now() + 600;
      if (target && e.anchorTop != null) {
        const want = window.scrollY + target.getBoundingClientRect().top - e.anchorTop;
        if (want < 0) {
          topSpacerPx += -want;
          $topSpacer.style.height = `${topSpacerPx}px`;
          window.scrollTo(0, 0);
        } else {
          window.scrollTo(0, want);
        }
      } else {
        window.scrollTo(0, e.scrollY || 0);
      }
      updateNavCurrent();
      updateRail();
      savePositionDebounced();
    } finally {
      hist.restoring = false;
    }
  }

  function histGo(dir, via) {
    if (!state.tree) return;
    flushHistory();
    const to = hist.idx + dir;
    if (to < 0 || to >= hist.entries.length) return;
    // where we are right now goes back into the entry we are leaving, so coming back returns here
    const cur = hist.entries[hist.idx];
    const snap = histSnapshot();
    cur.anchorTop = snap.anchorTop;
    cur.scrollY = snap.scrollY;
    cur.anchorId = snap.anchorId;
    cur.anchorOffset = snap.anchorOffset;
    hist.idx = to;
    hideHistBack();
    histRestore(hist.entries[to]);
    logEvent("history", { tree_id: state.tree.id, dir: dir < 0 ? "back" : "forward", via: via || "key" });
  }

  $histBack.addEventListener("click", () => histGo(-1, "button"));
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active") || !e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    // The browser's own Back / Forward would leave the document: keep them for the zoom history.
    e.preventDefault();
    histGo(e.key === "ArrowLeft" ? -1 : 1, "key");
  });

  // ---------------------------------------------------------------------
  // In-document search: "/" or Ctrl+F while a document is open.
  // It looks through the whole document (every node's title, key points and text,
  // the source leaves, and the overview card), not only what is expanded. A match
  // that is not on the page yet opens just enough (the shallowest form that
  // contains it, via the same kToReveal path as a jump); matches on the page are
  // marked, the current one more strongly. Only the query's length is logged.
  // ---------------------------------------------------------------------
  const search = { open: false, query: "", hits: [], cur: -1, index: null, timer: null, opener: null };
  const $searchBar = el("search-bar");
  const $searchInput = el("search-input");
  const $searchCount = el("search-count");
  const $searchBtn = el("search-btn");
  const SEARCH_MIN = 2;
  const SEARCH_MARK_CAP = 400;
  const BLOCK_SEL = "p,li,h1,h2,h3,h4,h5,h6,tr,blockquote,pre,dt,dd,div,section,ul,ol,table";

  function lowerSafe(s) {
    const l = s.toLowerCase();
    if (l.length === s.length) return l;
    return Array.from(s, (c) => {
      const x = c.toLowerCase();
      return x.length === c.length ? x : c;
    }).join("");
  }

  // The text of an element as one string, with a newline between blocks, plus
  // where each text node starts in it. Used both to count matches (on parsed
  // markup) and to mark them (on the live page), so the two always agree.
  function textSegments(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const segs = [];
    let virt = "";
    let lastBlock = null;
    let n;
    while ((n = walker.nextNode())) {
      const b = n.parentElement && n.parentElement.closest(BLOCK_SEL);
      if (segs.length && b !== lastBlock) virt += "\n";
      lastBlock = b;
      segs.push({ node: n, start: virt.length });
      virt += n.nodeValue;
    }
    return { virt, segs };
  }

  function findAll(lower, q) {
    const out = [];
    if (!q) return out;
    let i = 0;
    while ((i = lower.indexOf(q, i)) !== -1) {
      out.push(i);
      i += q.length;
    }
    return out;
  }

  function inertBody(html) {
    return new DOMParser().parseFromString(`<body>${html}</body>`, "text/html").body;
  }

  // One entry per searchable field, in reading order: the overview card first, then each node
  // (title, key points, text) top-down. The root's own summary is the gist and the card.
  function buildSearchIndex() {
    const tree = state.tree;
    const entries = [];
    const add = (nodeId, field, html) => {
      const { virt } = textSegments(inertBody(html));
      entries.push({ nodeId, field, lower: lowerSafe(virt) });
    };
    const ovHTML = overviewHTML();
    if (ovHTML) add(null, "overview", ovHTML);
    (function walk(id) {
      const n = tree.nodes[id];
      if (!n) return;
      const isRoot = id === tree.root;
      if (!(isRoot && !n.is_leaf)) {
        if (n.title) add(id, "title", escapeHtml(n.title));
        const points = n.key_points && n.key_points.length ? n.key_points : n.hook ? [n.hook] : [];
        if (!n.is_leaf && points.length) add(id, "point", `<ul>${points.map((p) => `<li>${renderInline(p)}</li>`).join("")}</ul>`);
        if (n.text) add(id, "text", renderMarkdown(n.text));
      }
      for (const c of n.children || []) walk(c);
    })(tree.root);
    return { treeId: tree.id, overview: tree.overview || null, entries };
  }

  function searchIndex() {
    const ix = search.index;
    if (!ix || ix.treeId !== state.tree.id || ix.overview !== (state.tree.overview || null)) search.index = buildSearchIndex();
    return search.index;
  }

  function wrapVirtRange(segs, from, to) {
    let a = null;
    let b = null;
    for (const sg of segs) {
      const len = sg.node.nodeValue.length;
      if (!a && from >= sg.start && from < sg.start + len) a = sg;
      if (to > sg.start && to <= sg.start + len) b = sg;
    }
    if (!a || !b) return;
    const range = document.createRange();
    range.setStart(a.node, from - a.start);
    range.setEnd(b.node, to - b.start);
    const span = document.createElement("span");
    span.className = "search-hit";
    try {
      range.surroundContents(span);
    } catch (e) {
      span.appendChild(range.extractContents());
      range.insertNode(span);
    }
  }

  function clearSearchMarks() {
    for (const s of $content.querySelectorAll(".search-hit")) {
      const p = s.parentNode;
      if (!p) continue;
      while (s.firstChild) p.insertBefore(s.firstChild, s);
      p.removeChild(s);
      p.normalize();
    }
  }

  // The element that holds a given field of a node on the page.
  function searchContainer(h) {
    if (h.field === "overview") return $content.querySelector(".overview-card");
    const N = h.nodeId;
    const block = $content.querySelector(`[data-node-id="${N}"]`);
    if (h.field === "title") {
      return (block && block.querySelector(".node-title")) || $content.querySelector(`.section-block[data-section-id="${N}"] .section-header h1`);
    }
    if (h.field === "point") return block && block.querySelector(".skim-points");
    if (block) return block.querySelector(".node-body");
    return state.tree.nodes[N] && N === state.tree.root ? $content.querySelector(".root-hero .node-body") : null;
  }

  function applySearchMarks() {
    clearSearchMarks();
    const q = lowerSafe(search.query);
    if (!search.open || q.length < SEARCH_MIN) return;
    let budget = SEARCH_MARK_CAP;
    const roots = $content.querySelectorAll(".overview-card, .section-header h1, .node-title, .skim-points, .node-body");
    for (const root of roots) {
      if (budget <= 0) break;
      const { virt, segs } = textSegments(root);
      const pos = findAll(lowerSafe(virt), q).slice(0, budget);
      budget -= pos.length;
      for (let i = pos.length - 1; i >= 0; i--) wrapVirtRange(segs, pos[i], pos[i] + q.length);
    }
    markCurrentHit();
  }

  function currentHitSpan() {
    const h = search.hits[search.cur];
    if (!h) return null;
    const c = searchContainer(h);
    return c ? c.querySelectorAll(".search-hit")[h.occ] || null : null;
  }

  function markCurrentHit() {
    $content.querySelectorAll(".search-current").forEach((s) => {
      s.classList.remove("search-current");
      s.removeAttribute("aria-current");
    });
    const span = currentHitSpan();
    if (span) {
      span.classList.add("search-current");
      span.setAttribute("aria-current", "true");
    }
    return span;
  }

  function updateSearchCount() {
    const n = search.hits.length;
    let text = "";
    if (search.query.trim().length >= SEARCH_MIN) text = n ? `${search.cur + 1} of ${n}` : "No matches";
    else if (search.query.trim()) text = "Type 2 or more letters";
    $searchCount.textContent = text;
  }

  function runSearch() {
    const q = lowerSafe(search.query.trim().replace(/\s+/g, " "));
    search.hits = [];
    search.cur = -1;
    if (q.length >= SEARCH_MIN && state.tree) {
      for (const e of searchIndex().entries) {
        findAll(e.lower, q).forEach((_, occ) => search.hits.push({ nodeId: e.nodeId, field: e.field, occ }));
      }
      logEvent("search", { tree_id: state.tree.id, query_length: q.length, matches: search.hits.length });
    }
    search.query = search.query.trim().replace(/\s+/g, " ");
    updateSearchCount();
    if (search.hits.length) goToHit(0);
    else applySearchMarks();
  }

  // Open just enough for the hit's field to be on the page, never more.
  function revealHit(h) {
    const tree = state.tree;
    const F = window.Frontier;
    if (h.field === "overview") {
      window.scrollTo({ top: 0, behavior: REDUCED_MOTION ? "auto" : "smooth" });
      return;
    }
    const N = h.nodeId;
    const node = tree.nodes[N];
    const needProse = h.field === "text" && !node.is_leaf;
    const sufficient = () => state.frontier.includes(N) && (!needProse || state.prose.has(N));
    if (sufficient()) return;
    setAnchor(N);
    const total = () => Math.max(1, state.sequence.length);
    const curK = () => F.zToK(state.z, total());
    // Smallest k on a sequence where N is on the page (in prose form when its text is wanted).
    const targetK = (seq) => {
      const kr = F.kToReveal(tree, seq, N);
      if (!needProse) return kr;
      const idx = seq.indexOf(F.PROSE + N);
      if (idx < 0) return kr;
      const want = Math.max(kr, idx + 1);
      return F.frontierAtK(tree, seq, want).includes(N) ? want : kr;
    };
    const kr = F.kToReveal(tree, state.sequence, N);
    if (kr <= curK() && !state.frontier.includes(N)) {
      // N has already been opened into its parts: re-compose the page around it so it shows whole.
      const seq = F.buildExpansionSequence(tree, N);
      const zFrom = state.z;
      resetTopSpacer();
      state.sequence = seq;
      state.sequenceAnchor = N;
      state.z = targetK(seq) / Math.max(1, seq.length);
      const r = F.frontierAtZ(tree, seq, state.z);
      state.frontier = r.frontier;
      state.prose = r.prose;
      render({});
      updateReadout();
      savePositionDebounced();
      logEvent("dial", { tree_id: tree.id, z_from: zFrom, z_to: state.z, input: "jump", anchor_node_id: N });
      return;
    }
    const k = targetK(state.sequence);
    if (k > curK()) setZ(k / total(), "jump");
  }

  function goToHit(i) {
    const n = search.hits.length;
    if (!n || !state.tree) return;
    search.cur = ((i % n) + n) % n;
    const h = search.hits[search.cur];
    revealHit(h);
    applySearchMarks();
    updateSearchCount();
    state.lastDialChangeAt = Date.now() + 600; // the scroll below is not a re-anchor
    const span = currentHitSpan();
    if (span) span.scrollIntoView({ block: "center", behavior: REDUCED_MOTION ? "auto" : "smooth" });
    else if (h.nodeId && state.tree.nodes[h.nodeId]) jumpToNode(h.nodeId);
    recordHistory("search");
  }

  function openSearch() {
    if (!state.tree || !$app.classList.contains("active")) return;
    if (!search.open) search.opener = document.activeElement;
    search.open = true;
    $searchBar.hidden = false;
    $searchBtn.setAttribute("aria-pressed", "true");
    const hb = el("app-header").getBoundingClientRect().bottom;
    $searchBar.style.top = `${Math.max(8, hb + 8)}px`;
    $searchInput.focus();
    $searchInput.select();
  }

  function closeSearch() {
    if (!search.open) return;
    search.open = false;
    clearTimeout(search.timer);
    $searchBar.hidden = true;
    $searchBtn.setAttribute("aria-pressed", "false");
    clearSearchMarks();
    search.hits = [];
    search.cur = -1;
    search.query = "";
    $searchInput.value = "";
    $searchCount.textContent = "";
    const back = search.opener;
    search.opener = null;
    if (back && back.isConnected && back !== document.body && back.focus) back.focus({ preventScroll: true });
    else $searchBtn.focus({ preventScroll: true });
  }

  $searchBtn.addEventListener("click", () => (search.open ? closeSearch() : openSearch()));
  el("search-close").addEventListener("click", closeSearch);
  el("search-next").addEventListener("click", () => goToHit(search.cur + 1));
  el("search-prev").addEventListener("click", () => goToHit(search.cur - 1));
  $searchInput.addEventListener("input", () => {
    search.query = $searchInput.value;
    clearTimeout(search.timer);
    search.timer = setTimeout(() => {
      search.timer = null;
      runSearch();
    }, 160);
  });
  $searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeSearch();
    } else if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (search.timer) {
        clearTimeout(search.timer);
        search.timer = null;
        search.query = $searchInput.value;
        runSearch();
        if (e.key === "Enter" && !e.shiftKey) return; // the new search already went to the first match
      }
      goToHit(search.cur + (e.key === "ArrowUp" || (e.key === "Enter" && e.shiftKey) ? -1 : 1));
    }
  });
  document.addEventListener("keydown", (e) => {
    if (!$app.classList.contains("active")) return;
    const t = e.target;
    const tag = ((t && t.tagName) || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable);
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "f" || e.key === "F")) {
      // Ctrl+F again inside the search box is the browser's own find.
      if (search.open && document.activeElement === $searchInput) return;
      e.preventDefault();
      openSearch();
    } else if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !typing) {
      e.preventDefault();
      openSearch();
    }
  });
  window.addEventListener("resize", () => {
    if (search.open) $searchBar.style.top = `${Math.max(8, el("app-header").getBoundingClientRect().bottom + 8)}px`;
  });

  // ---------------------------------------------------------------------
  // Not helpful link
  // ---------------------------------------------------------------------
  el("not-helpful").addEventListener("click", () => {
    if (!state.tree) return;
    logEvent("not_helpful", { tree_id: state.tree.id, z: state.z });
    flushEvents(false);
    el("not-helpful").textContent = "noted";
    setTimeout(() => (el("not-helpful").textContent = "not helpful"), 2000);
  });

  // ---------------------------------------------------------------------
  // Tree loading
  // ---------------------------------------------------------------------
  function initialZForTree(tree, targetMinutes) {
    const target = targetMinutes || 2;
    const totalMinutes = tree.source_words / WPM;
    if (totalMinutes <= target) return 1.0;
    const sequence = window.Frontier.buildExpansionSequence(tree, tree.root);
    const total = Math.max(1, sequence.length);
    let bestK = 0;
    let bestDiff = Infinity;
    for (let k = 0; k <= sequence.length; k++) {
      const frontier = window.Frontier.frontierAtK(tree, sequence, k);
      const words = frontierWords(tree, frontier, window.Frontier.proseAtK(sequence, k));
      const minutes = words / WPM;
      const diff = Math.abs(minutes - target);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestK = k;
      }
    }
    return bestK / total;
  }

  // Check-in adjustment -------------------------------------------------
  function applyAdjustment(adj) {
    state.adjust = { label: adj.label, minutes: adj.minutes, mapWasOpen: false };
    if (adj.minutes < 2 && window.RiemannMap && window.RiemannMap.isOpen()) {
      state.adjust.mapWasOpen = true;
      window.RiemannMap.close({ persist: false, restoreFocus: false });
    }
  }

  function updateAdjustNote() {
    const $note = el("adjust-note");
    const a = state.adjust;
    $note.hidden = !a;
    if (a) el("adjust-text").textContent = `Adjusted for: ${a.label}`;
  }

  el("adjust-undo").addEventListener("click", () => {
    const a = state.adjust;
    if (!a || !state.tree) return;
    state.adjust = null;
    updateAdjustNote();
    setZ(initialZForTree(state.tree, 2), "adjust-undo");
    if (a.mapWasOpen && window.RiemannMap) window.RiemannMap.open({ persist: false });
    logEvent("checkin_adjust_undo", { tree_id: state.tree.id });
  });

  // Trees built before the overview card existed get it from one call
  // (POST /api/tree/{id}/overview), once per tree per session; failures are
  // silent and the reader simply has no card. The card lands above the
  // content, so the page is re-rendered with the reading position held.
  const overviewTried = new Set();
  function ensureOverview(tree) {
    if (IS_FIXTURE || tree.overview || tree.status !== "done" || overviewTried.has(tree.id)) return;
    const rootNode = tree.nodes[tree.root];
    if (!rootNode || rootNode.is_leaf) return;
    overviewTried.add(tree.id);
    fetch(`/api/tree/${encodeURIComponent(tree.id)}/overview`, { method: "POST" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || !data.overview || !state.tree || state.tree.id !== tree.id) return;
        tree.overview = data.overview;
        keepReadingPosition(() => render({}));
      })
      .catch(() => {});
  }

  function openTree(tree, opts) {
    closeSearch();
    resetTopSpacer();
    opts = opts || {};
    state.tree = tree;
    state.leafIndex = computeLeafIndex(tree);
    state.highlights = loadHighlights(tree.id);
    state.lastRailSection = undefined;
    $startScreen.style.display = "none";
    $app.classList.add("active");
    buildNav();

    const saved = !opts.forceFresh ? loadPosition(tree.id) : null;
    const anchorId = (saved && saved.anchor_node_id && tree.nodes[saved.anchor_node_id]) ? saved.anchor_node_id : tree.root;
    state.sequence = window.Frontier.buildExpansionSequence(tree, anchorId);
    state.sequenceAnchor = anchorId;
    state.anchorNodeId = anchorId;
    state.anchorOffset = saved ? saved.anchor_offset : null;

    // A fresh open (not a resume) may start shallower or deeper depending on
    // the optional check-in. Presentation only: the tree itself is untouched.
    state.adjust = null;
    let z;
    if (saved) {
      z = saved.z;
    } else {
      const adj = checkinAdjustment();
      z = initialZForTree(tree, adj ? adj.minutes : 2);
      if (adj) applyAdjustment(adj);
    }
    updateAdjustNote();
    state.z = 0;
    const { frontier, prose } = window.Frontier.frontierAtZ(tree, state.sequence, z);
    state.frontier = frontier;
    state.prose = prose;
    state.z = z;
    render({});
    updateReadout();

    // The anchor may still be the root (not itself in the frontier) after a
    // fresh open with no saved position — resolve it to whatever's actually
    // in view so the nav/rail reflect a real current section immediately.
    if (!state.frontier.includes(state.anchorNodeId)) {
      const initialAnchor = findCentreNodeId() || state.frontier[0];
      if (initialAnchor && initialAnchor !== state.anchorNodeId) {
        state.anchorNodeId = initialAnchor;
        const n = tree.nodes[initialAnchor];
        state.anchorOffset = n ? (n.source_span[0] + n.source_span[1]) / 2 : state.anchorOffset;
        updateNavCurrent();
        updateRail();
      }
    }

    histReset();
    logEvent("open", { tree_id: tree.id, resumed: !!saved });
    flushEvents(false);
    ensureOverview(tree);

    if (saved) showResumeCard(anchorId);
    maybeShowHint();
    if (window.RiemannMap) window.RiemannMap.update();

    // The screen just changed under a keyboard or screen-reader user (the
    // button they pressed is now hidden): say what opened and park focus on the
    // header, so Tab continues into its controls rather than starting from nothing.
    scheduleAnnounce(`Opened ${tree.title || "document"}. ${$dial.getAttribute("aria-valuetext") || ""}`.trim());
    focusQuietly(el("title-block"));
  }

  window.addEventListener(
    "scroll",
    debounce(() => {
      if (!state.tree || !$app.classList.contains("active")) return;
      if (Date.now() - state.lastDialChangeAt < 400) return;
      const centreId = findCentreNodeId();
      if (centreId && centreId !== state.anchorNodeId) setAnchor(centreId);
      updateReadout();
    }, 150)
  );

  function showResumeCard(anchorId) {
    const node = state.tree.nodes[anchorId];
    $resumeCardText.textContent = `Back where you left off: ${firstClause(node ? nodeTitle(node) || node.text : "")}`;
    $resumeCard.classList.add("visible");
    const timer = setTimeout(() => $resumeCard.classList.remove("visible"), 4000);
    el("resume-card-dismiss").onclick = () => {
      clearTimeout(timer);
      $resumeCard.classList.remove("visible");
    };
  }

  // A build in progress shows the loading screen, driven by the build's
  // SSE stream (the server replays history to late subscribers, so nothing
  // is missed). The reader opens only once the tree is complete: the
  // frontier, nav and rail all assume a finished tree.
  const $loading = el("loading-screen");

  function setLoadingStep(step) {
    const order = ["read", "gist", "layers"];
    const idx = order.indexOf(step);
    $loading.querySelectorAll("#loading-steps li").forEach((li) => {
      const i = order.indexOf(li.dataset.step);
      li.classList.toggle("done", i < idx);
      li.classList.toggle("active", i === idx);
    });
  }

  function stopLoading() {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = null;
    clearInterval(state.loadingTimer);
    state.loadingTimer = null;
  }

  function showStartScreen() {
    stopLoading();
    if (state.tree && $app.classList.contains("active")) {
      savePosition();
      logEvent("close", { tree_id: state.tree.id });
      flushEvents(false);
    }
    closeSearch();
    clearTimeout(hist.timer);
    hideHistBack();
    state.tree = null;
    state.dwellNode = null;
    state.dwellStart = 0;
    clearGhosts();
    hideHighlightToolbar();
    if (state.paletteOpen) {
      state.paletteOpen = false;
      renderPaletteOpenState();
    }
    resetTopSpacer();
    if (window.RiemannMap) window.RiemannMap.update();
    $loading.hidden = true;
    $app.classList.remove("active");
    $startScreen.style.display = "";
    document.title = "Riemann";
    window.scrollTo(0, 0);
    loadRecent();
  }

  function showLoading(treeId, title) {
    stopLoading();
    $startScreen.style.display = "none";
    $app.classList.remove("active");
    $loading.hidden = false;
    $loading.setAttribute("aria-busy", "true");
    el("loading-doc").textContent = title || "";
    el("loading-heading").textContent = "Building your gist";
    focusQuietly(el("loading-heading"));
    el("loading-gist").hidden = true;
    el("loading-error").hidden = true;
    setLoadingStep("read");

    const startedAt = Date.now();
    const $elapsed = el("loading-elapsed");
    const tick = () => { $elapsed.textContent = `${Math.round((Date.now() - startedAt) / 1000)} s`; };
    tick();
    state.loadingTimer = setInterval(tick, 1000);

    let summaries = 0;
    let finished = false;
    const layersText = $loading.querySelector('[data-step="layers"] .step-text');
    layersText.textContent = "Summarising, layer by layer";

    const es = new EventSource(`/api/tree/${treeId}/events`);
    state.eventSource = es;
    es.addEventListener("leaves", (e) => {
      const n = (JSON.parse(e.data).nodes || []).length;
      $loading.querySelector('[data-step="read"] .step-text').textContent =
        `Read the text: ${n} passage${n === 1 ? "" : "s"}`;
      setLoadingStep("gist");
    });
    es.addEventListener("provisional_root", (e) => {
      const node = JSON.parse(e.data).node;
      if (node && node.text) {
        el("loading-gist-text").textContent = node.text;
        el("loading-gist").hidden = false;
      }
      setLoadingStep("layers");
    });
    es.addEventListener("level", (e) => {
      summaries += (JSON.parse(e.data).nodes || []).length;
      layersText.textContent = `Summarising, layer by layer: ${summaries} written`;
      setLoadingStep("layers");
    });
    es.addEventListener("done", (e) => {
      finished = true;
      const tree = JSON.parse(e.data).tree;
      stopLoading();
      $loading.hidden = true;
      $loading.setAttribute("aria-busy", "false");
      if (tree) openTree(tree, { forceFresh: true });
    });
    es.addEventListener("error", (e) => {
      if (finished) return;
      // A named "error" event from the server carries data; a bare
      // connection error doesn't (EventSource would retry, but a dropped
      // stream here means the server went away).
      let msg = "Lost the connection to the Riemann server. Is it still running?";
      if (e.data) {
        try { msg = JSON.parse(e.data).message || msg; } catch (_) {}
      }
      stopLoading();
      $loading.setAttribute("aria-busy", "false");
      el("loading-heading").textContent = "The build stopped";
      el("loading-error-text").textContent = msg;
      el("loading-error").hidden = false;
      $loading.querySelectorAll("#loading-steps li.active").forEach((li) => li.classList.remove("active"));
    });
  }

  el("loading-back").addEventListener("click", () => goHome());
  el("loading-retry").addEventListener("click", async () => {
    const m = location.hash.match(TREE_HASH);
    if (!m) return;
    const btn = el("loading-retry");
    btn.disabled = true;
    try {
      const resp = await fetch(`/api/tree/${m[1]}/retry`, { method: "POST" });
      if (!resp.ok) throw new Error("retry refused");
      const tree = await (await fetch(`/api/tree/${m[1]}`)).json();
      if (tree.status === "done") openTree(tree);
      else showLoading(m[1], tree.title);
    } catch (err) {
      console.error(err);
      el("loading-error-text").textContent = "Could not restart the build. Go back and build it again.";
    } finally {
      btn.disabled = false;
    }
  });

  // ---------------------------------------------------------------------
  // Routing: #/t/<tree id> is a document, anything else is the home page.
  // The browser's Back button and the header's home button both land home.
  // ---------------------------------------------------------------------
  const TREE_HASH = /^#\/t\/([0-9a-f]+)$/;

  function goHome() {
    // pushState (not location.hash = "") so the URL has no stray "#"; Back
    // still returns to the document because that fires hashchange.
    if (location.hash) history.pushState(null, "", location.pathname + location.search);
    showStartScreen();
    focusQuietly(document.querySelector(".home-hero h1"));
  }

  function goToTree(treeId) {
    const hash = `#/t/${treeId}`;
    if (location.hash === hash) route();
    else location.hash = hash;
  }

  async function route() {
    const m = location.hash.match(TREE_HASH);
    if (!m) {
      showStartScreen();
      return;
    }
    if (state.tree && state.tree.id === m[1] && $app.classList.contains("active")) return;
    try {
      await openTreeById(m[1]);
    } catch (err) {
      console.error(err);
      history.replaceState(null, "", location.pathname + location.search);
      showStartScreen();
      showStartError(err.message || "Could not open that document.");
    }
  }

  window.addEventListener("hashchange", route);

  async function openTreeById(treeId) {
    const resp = await fetch(`/api/tree/${treeId}`);
    if (!resp.ok) throw new Error("Could not find that document. It may have been built by an older version.");
    const tree = await resp.json();
    document.title = `${tree.title || "Document"} · Riemann`;
    if (tree.status === "done") openTree(tree);
    else showLoading(tree.id, tree.title);
  }

  // ---------------------------------------------------------------------
  // Home: composer (paste / file / link), model picker, recent documents
  // ---------------------------------------------------------------------
  const $pasteText = el("paste-text");
  const $urlInput = el("url-input");
  const $fileInput = el("file-input");
  const $buildBtn = el("build-btn");
  const $modelSelect = el("model-select");
  const $composer = el("composer");
  let activeTab = "paste";
  let chosenFile = null;

  function showStartError(msg) {
    const $err = el("paste-error");
    $err.textContent = msg;
    $err.hidden = false;
  }

  function clearStartError() {
    el("paste-error").hidden = true;
  }

  function selectTab(name, focus) {
    activeTab = name;
    for (const tab of document.querySelectorAll(".composer-tab")) {
      const on = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      el(tab.getAttribute("aria-controls")).hidden = !on;
      if (on && focus) tab.focus();
    }
    clearStartError();
  }

  el("composer").querySelector(".composer-tabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".composer-tab");
    if (tab) selectTab(tab.dataset.tab);
  });
  el("composer").querySelector(".composer-tabs").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const order = ["paste", "file", "url"];
    const i = order.indexOf(activeTab) + (e.key === "ArrowRight" ? 1 : -1);
    selectTab(order[(i + order.length) % order.length], true);
    e.preventDefault();
  });

  function updatePasteCount() {
    const words = countWords($pasteText.value.trim());
    el("paste-count").textContent = words ? `${words.toLocaleString()} words · ~${Math.max(1, Math.round(words / WPM))} min to read in full` : "";
  }
  $pasteText.addEventListener("input", () => {
    updatePasteCount();
    clearStartError();
  });

  function setFile(file) {
    chosenFile = file || null;
    el("dropzone").classList.toggle("has-file", !!chosenFile);
    el("dropzone-title").textContent = chosenFile ? chosenFile.name : "Drop a file here, or click to choose";
    clearStartError();
  }
  $fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));

  // Dropping a file anywhere on the composer switches to the File tab.
  $composer.addEventListener("dragover", (e) => {
    if (!e.dataTransfer || !Array.from(e.dataTransfer.types || []).includes("Files")) return;
    e.preventDefault();
    $composer.classList.add("drag-over");
  });
  $composer.addEventListener("dragleave", (e) => {
    if (!$composer.contains(e.relatedTarget)) $composer.classList.remove("drag-over");
  });
  $composer.addEventListener("drop", (e) => {
    $composer.classList.remove("drag-over");
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (!file) return;
    e.preventDefault();
    selectTab("file");
    setFile(file);
  });

  // Model picker ------------------------------------------------------
  const MODEL_KEY = "riemann:model";
  const RECOMMENDED = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001", "gemini-3.8-flash-high"];
  const MODEL_NOTES = {
    "claude-sonnet-5-5": "Balanced quality and speed.",
    "claude-opus-5-5": "Strongest summaries, slower.",
    "claude-haiku-4-5-20251001": "Fastest, lighter summaries.",
    "gemini-3.8-flash-high": "Fast, and uses Gemini quota instead of Claude.",
  };
  const PROVIDER_NAMES = { anthropic: "Anthropic", openai: "OpenAI", xai: "xAI", antigravity: "Antigravity" };
  let defaultModel = "claude-sonnet-5-5";

  function modelLabel(id) {
    const parts = id.split("-").filter((p) => !/^\d{8}$/.test(p));
    const out = [];
    for (const p of parts) {
      const prev = out[out.length - 1];
      if (/^\d$/.test(p) && prev && /^\d+(\.\d+)?$/.test(prev) && !prev.includes(".")) out[out.length - 1] = `${prev}.${p}`;
      else out.push(p);
    }
    return out
      .map((p) => (["gpt", "oss"].includes(p) ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)))
      .join(" ");
  }

  function loadModelChoice() {
    try {
      return localStorage.getItem(MODEL_KEY);
    } catch (e) {
      return null;
    }
  }

  function currentModel() {
    return $modelSelect.value || defaultModel;
  }

  function updateModelNote() {
    const id = currentModel();
    const note = MODEL_NOTES[id] || "";
    el("model-note").textContent = id === defaultModel ? (note ? `${note} This is the default.` : "The default.") : note;
  }

  $modelSelect.addEventListener("change", () => {
    try {
      localStorage.setItem(MODEL_KEY, $modelSelect.value);
    } catch (e) {}
    updateModelNote();
  });

  async function loadModels() {
    let models = [];
    try {
      const resp = await fetch("/api/models");
      if (resp.ok) {
        const data = await resp.json();
        defaultModel = data.default || defaultModel;
        models = data.models || [];
      }
    } catch (e) {}
    const ids = new Set(models.map((m) => m.id));
    ids.add(defaultModel);
    const opt = (id) => `<option value="${escapeHtml(id)}">${escapeHtml(modelLabel(id))}${id === defaultModel ? " (default)" : ""}</option>`;
    const rec = [defaultModel, ...RECOMMENDED.filter((id) => id !== defaultModel && ids.has(id))];
    const groups = {};
    for (const m of models) {
      if (rec.includes(m.id)) continue;
      (groups[m.provider] = groups[m.provider] || []).push(m.id);
    }
    let html = `<optgroup label="Recommended">${rec.map(opt).join("")}</optgroup>`;
    for (const provider of Object.keys(groups).sort()) {
      const list = groups[provider].sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
      html += `<optgroup label="${escapeHtml(PROVIDER_NAMES[provider] || provider || "Other")}">${list.map(opt).join("")}</optgroup>`;
    }
    $modelSelect.innerHTML = html;
    const saved = loadModelChoice();
    $modelSelect.value = saved && ids.has(saved) ? saved : defaultModel;
    updateModelNote();
  }

  // Goal chips ("What's this for?") ---------------------------------------
  const OBJ_KEY = "riemann:objective";
  const OBJECTIVES = window.Objective.OBJECTIVES;
  let manualObjective = null; // set when Sam taps a chip this visit
  let suggestedObjective = null;
  let rememberedObjective = null;
  try {
    const r = localStorage.getItem(OBJ_KEY);
    if (OBJECTIVES.some((o) => o.key === r)) rememberedObjective = r;
  } catch (e) {}

  function objectiveLabel(key) {
    const o = OBJECTIVES.find((x) => x.key === key);
    return o ? o.label : null;
  }

  // Manual tap wins, then a fresh suggestion, then the last manual choice.
  function currentObjective() {
    return manualObjective || suggestedObjective || rememberedObjective || null;
  }

  function renderGoalChips() {
    const cur = currentObjective();
    const fromSuggestion = !manualObjective && cur && cur === suggestedObjective;
    el("goal-chips").innerHTML = OBJECTIVES.map((o) => {
      const on = o.key === cur;
      return `<button type="button" role="radio" class="goal-chip${on ? " on" : ""}" data-obj="${o.key}" aria-checked="${on}" tabindex="${on || (!cur && o === OBJECTIVES[0]) ? 0 : -1}">${escapeHtml(o.label)}${on && fromSuggestion ? '<span class="goal-suggested"> (suggested)</span>' : ""}</button>`;
    }).join("");
  }

  el("goal-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".goal-chip");
    if (!chip) return;
    manualObjective = chip.dataset.obj;
    rememberedObjective = manualObjective;
    try {
      localStorage.setItem(OBJ_KEY, manualObjective);
    } catch (err) {}
    renderGoalChips();
    el("goal-chips").querySelector(".goal-chip.on").focus();
  });
  el("goal-chips").addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    const chips = Array.from(el("goal-chips").querySelectorAll(".goal-chip"));
    const i = chips.indexOf(document.activeElement);
    if (i < 0) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
    chips[(i + step + chips.length) % chips.length].click();
    e.preventDefault();
  });

  let suggestToken = 0;
  async function refreshSuggestion() {
    const token = ++suggestToken;
    let title = "";
    let text = "";
    let format = activeTab;
    if (activeTab === "paste") {
      text = $pasteText.value.slice(0, 2000);
      title = (text.split("\n").find((l) => l.trim()) || "").replace(/^#+\s*/, "").slice(0, 200);
    } else if (activeTab === "url") {
      title = $urlInput.value.trim();
    } else if (chosenFile) {
      title = chosenFile.name;
      if (/\.(md|txt)$/i.test(chosenFile.name) || /^text\//.test(chosenFile.type)) {
        try {
          text = await chosenFile.slice(0, 4000).text();
        } catch (e) {}
      }
    }
    if (token !== suggestToken) return;
    suggestedObjective = window.Objective.suggestObjective({ title, format, text });
    renderGoalChips();
  }
  const refreshSuggestionSoon = debounce(refreshSuggestion, 250);
  $pasteText.addEventListener("input", refreshSuggestionSoon);
  $urlInput.addEventListener("input", refreshSuggestionSoon);
  $fileInput.addEventListener("change", refreshSuggestion);
  el("composer").querySelector(".composer-tabs").addEventListener("click", refreshSuggestionSoon);
  renderGoalChips();

  // Check-in ("How are you right now?") -----------------------------------
  // Optional and local. Stored in localStorage with a timestamp, stale after
  // 4 hours, logged as a `checkin` event. It only shifts presentation (start
  // depth, whether the Map opens) and never touches the summaries.
  const CHECKIN_KEY = "riemann:checkin";
  const CHECKIN_TTL_MS = 4 * 3600 * 1000;
  const CHECKIN_GROUPS = [
    { key: "capacity", label: "Energy", options: [["low", "Low"], ["okay", "Okay"], ["good", "Good"]] },
    { key: "mood", label: "Mood", options: [["flat", "Flat"], ["anxious", "Anxious"], ["fine", "Fine"], ["good", "Good"]] },
    { key: "sleep", label: "Sleep last night", options: [["lt5", "<5h"], ["5to7", "5–7h"], ["7plus", "7h+"]] },
    { key: "caffeine", label: "Caffeine", options: [["none", "None"], ["some", "Some"], ["lots", "Lots"]] },
    { key: "meds", label: "Meds", options: [["not_today", "Not today"], ["kicking_in", "Kicking in"], ["working", "Working"], ["wearing_off", "Wearing off"], ["na", "N/A"]] },
  ];

  function loadCheckin() {
    try {
      const raw = JSON.parse(localStorage.getItem(CHECKIN_KEY) || "null");
      if (!raw || typeof raw.ts !== "number" || Date.now() - raw.ts > CHECKIN_TTL_MS) return null;
      return raw;
    } catch (e) {
      return null;
    }
  }

  function saveCheckin(c) {
    try {
      if (c) localStorage.setItem(CHECKIN_KEY, JSON.stringify(c));
      else localStorage.removeItem(CHECKIN_KEY);
    } catch (e) {}
  }

  function checkinAnswered(c) {
    return c ? CHECKIN_GROUPS.filter((g) => c[g.key]).length : 0;
  }

  // Which presentation shift (if any) the current check-in calls for.
  function checkinAdjustment() {
    const c = loadCheckin();
    if (!c) return null;
    if (c.capacity === "low") return { minutes: 1, label: "low energy" };
    if (c.meds === "wearing_off") return { minutes: 1, label: "meds wearing off" };
    if (c.sleep === "lt5") return { minutes: 1, label: "short sleep" };
    if (c.capacity === "good") return { minutes: 3, label: "good energy" };
    return null;
  }

  function renderCheckin() {
    const c = loadCheckin() || {};
    el("checkin-groups").innerHTML = CHECKIN_GROUPS.map(
      (g) => `<div class="checkin-group" role="radiogroup" aria-label="${escapeHtml(g.label)}">
        <span class="checkin-label">${escapeHtml(g.label)}</span>
        <div class="checkin-opts">${g.options
          .map(([v, l]) => `<button type="button" role="radio" class="goal-chip checkin-chip${c[g.key] === v ? " on" : ""}" data-group="${g.key}" data-val="${v}" aria-checked="${c[g.key] === v}">${escapeHtml(l)}</button>`)
          .join("")}</div>
      </div>`
    ).join("");
    const n = checkinAnswered(c);
    el("checkin-state").textContent = n ? "noted" : "optional";
    el("checkin-clear").hidden = !n;
  }

  el("checkin-groups").addEventListener("click", (e) => {
    const chip = e.target.closest(".checkin-chip");
    if (!chip) return;
    const c = loadCheckin() || {};
    const g = chip.dataset.group;
    if (c[g] === chip.dataset.val) delete c[g]; // tap again to unset
    else c[g] = chip.dataset.val;
    c.ts = Date.now();
    saveCheckin(checkinAnswered(c) ? c : null);
    const { ts, ...answers } = c;
    logEvent("checkin", answers);
    flushEvents(false);
    renderCheckin();
    const again = el("checkin-groups").querySelector(`[data-group="${g}"][data-val="${chip.dataset.val}"]`);
    if (again) again.focus();
  });
  el("checkin-clear").addEventListener("click", () => {
    saveCheckin(null);
    logEvent("checkin", { cleared: true });
    renderCheckin();
  });
  renderCheckin();

  // Build ---------------------------------------------------------------
  async function build() {
    clearStartError();
    let body;
    let multipart = false;
    const model = currentModel();
    const objective = currentObjective();
    if (objective) rememberedObjective = objective;
    if (activeTab === "paste") {
      const text = $pasteText.value.trim();
      if (!text) return showStartError("Paste some text first.");
      body = { text, model, objective };
    } else if (activeTab === "url") {
      const url = $urlInput.value.trim();
      if (!url) return showStartError("Enter a link first.");
      body = { url, model, objective };
    } else {
      if (!chosenFile) return showStartError("Choose a file first.");
      body = new FormData();
      body.append("file", chosenFile);
      body.append("model", model);
      if (objective) body.append("objective", objective);
      multipart = true;
    }

    const label = $buildBtn.textContent;
    $buildBtn.disabled = true;
    $buildBtn.textContent = "Starting…";
    try {
      const resp = await fetch("/api/abstract", multipart ? { method: "POST", body } : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        let detail = "";
        try {
          detail = (await resp.json()).detail || "";
        } catch (_) {}
        throw new Error(detail || "Could not build that. Try again.");
      }
      const data = await resp.json();
      goToTree(data.tree_id);
    } catch (err) {
      console.error(err);
      showStartError(err.message || "Could not build that. Try again.");
    } finally {
      $buildBtn.disabled = false;
      $buildBtn.textContent = label;
    }
  }

  $buildBtn.addEventListener("click", build);
  $urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") build();
  });
  $startScreen.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      build();
    }
  });

  // Recent documents ----------------------------------------------------
  function timeAgo(seconds) {
    const diff = Math.max(0, Date.now() / 1000 - seconds);
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
    const days = Math.round(diff / 86400);
    return days === 1 ? "yesterday" : `${days} days ago`;
  }

  async function loadRecent() {
    if (IS_FIXTURE) return;
    try {
      const resp = await fetch("/api/recent");
      if (!resp.ok) return;
      const items = await resp.json();
      if (!items || items.length === 0) {
        el("recent-block").hidden = true;
        return;
      }
      el("recent-list").innerHTML = items
        .map((it, i) => {
          const meta = [
            objectiveLabel(it.objective),
            `${(it.words || 0).toLocaleString()} words`,
            `${Math.max(1, Math.round((it.words || 0) / WPM))} min read`,
            it.model ? modelLabel(it.model) : null,
            timeAgo(it.updated),
          ].filter(Boolean);
          return `<li><a class="recent-card" href="#/t/${escapeHtml(it.id)}" style="--card-hue: var(--sec-${(i % 5) + 1})">
            <span class="recent-title">${escapeHtml(it.title || "Untitled")}</span>
            <span class="recent-meta">${meta.map((m) => `<span>${escapeHtml(m)}</span>`).join("")}</span>
          </a></li>`;
        })
        .join("");
      el("recent-block").hidden = false;
    } catch (e) {}
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  // Right-to-left text (Arabic, Hebrew): give every text block dir="auto" so
  // its base direction and alignment follow its own first strong character.
  // A no-op for left-to-right text. Applied by an observer so it covers every
  // render of the reader, rail, section nav and map without touching each.
  const BIDI_SELECTOR = [
    ".ov-title", ".ov-what", ".ov-item dd", ".ov-item dt > span", ".section-hook", ".section-header h1", ".node-title",
    ".node-body p", ".node-body li", ".node-body h1", ".node-body h2", ".node-body h3", ".node-body h4", ".node-body td",
    ".node-body th", ".node-body blockquote", ".key-points li", ".fact-big", ".fact-detail", ".up-next-title", ".up-next-hook",
    ".nav-title", "#rail li", ".root-hero h1", ".root-hero p", ".map-title", "#doc-title", "#doc-hook",
  ].join(",");
  function autoDir(root) {
    if (root.nodeType !== 1) return;
    if (root.matches(BIDI_SELECTOR) && !root.hasAttribute("dir")) root.setAttribute("dir", "auto");
    root.querySelectorAll(BIDI_SELECTOR).forEach((e) => {
      if (!e.hasAttribute("dir")) e.setAttribute("dir", "auto");
    });
  }
  function watchBidi() {
    const obs = new MutationObserver((muts) => {
      for (const m of muts) m.addedNodes.forEach(autoDir);
    });
    for (const id of ["content", "rail", "section-nav", "map-world", "app-header"]) {
      const node = document.getElementById(id);
      if (node) {
        autoDir(node);
        obs.observe(node, { childList: true, subtree: true });
      }
    }
  }

  async function boot() {
    watchBidi();
    if (window.RiemannCols) window.RiemannCols.init({ keepReadingPosition });
    if (window.RiemannMap) {
      window.RiemannMap.init({
        getTree: () => state.tree,
        getFrontier: () => state.frontier,
        getProse: () => state.prose,
        sectionsOf,
        sectionAncestor,
        nodeTitle,
        nodeProvenance,
        jumpToNode,
        logEvent,
        contentTopY,
        visibleFrontierIds,
        keepReadingPosition,
      });
    }
    state.palette = loadPalette();
    applyPaletteToCSS();
    state.reading = loadReading();
    applyReadingToCSS();
    renderReadingControls();
    if (IS_FIXTURE) {
      const resp = await fetch("dev-fixture.json");
      const tree = await resp.json();
      openTree(tree);
      return;
    }
    loadModels();
    route();
  }

  boot();
})();
