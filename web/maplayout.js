// maplayout.js
// -----------------------------------------------------------------------
// Pure layout for the spatial view (docs/spatial-view-spec.md, "Layout").
// No DOM, no randomness, and no dependence on the reader's frontier: the
// same tree and the same W x H always give the same rectangles, so a
// passage keeps its place on the map however far the reader is zoomed.
//
// The map is an ordered "strip" treemap (Bederson): items stay in document
// order and are packed into strips (rows when the container is at least as
// wide as it is tall, otherwise columns). An item joins the current strip
// while that keeps the strip's average aspect ratio closer to 1.
//
// Runs in the browser (window.MapLayout) and under Node (tests eval it with
// a stub `window`, like frontier.js).
// -----------------------------------------------------------------------
(function () {
  "use strict";

  const PAD = 12; // outer padding of the whole map
  const TOP_GAP = 8; // gap between sections
  const INNER = 10; // inset of an internal node's content rectangle
  const CHILD_GAP = 6; // gap between a node's children
  const MIN_CONTENT = 24; // below this the children get no rectangles
  const FLOOR = 0.06; // a part weighs at least 6% of its parent's total

  const wordsCache = new WeakMap();

  function firstClause(text) {
    const m = (text || "").match(/^[^.!?\n]{1,80}/);
    return (m ? m[0] : text || "").trim();
  }

  function defaultTitle(node) {
    return (node && (node.title || firstClause(node.text))) || "";
  }

  // Source length of a node: the sum of `words` over its leaves, or its
  // source_span length / 6 when that isn't available.
  function wordsInSource(tree) {
    let memo = wordsCache.get(tree.nodes);
    if (memo) return memo;
    memo = new Map();
    const nodes = tree.nodes;
    const visit = (id) => {
      if (memo.has(id)) return memo.get(id);
      const n = nodes[id];
      let w = 0;
      if (n) {
        if (n.is_leaf || !n.children || !n.children.length) w = n.words || 0;
        else for (const c of n.children) w += visit(c);
        if (!(w > 0) && n.source_span) w = Math.max(0, (n.source_span[1] - n.source_span[0]) / 6);
      }
      memo.set(id, w);
      return w;
    };
    for (const id of Object.keys(nodes)) visit(id);
    wordsCache.set(tree.nodes, memo);
    return memo;
  }

  // ---- key titles (compact density) ------------------------------------
  const LEAD_FILLER = new Set(["how", "why", "what", "when", "the", "a", "an"]);
  const TRAIL_STOP = new Set(["and", "or", "of", "to", "for", "in", "on", "with", "by", "at", "the", "a", "an", "as", "is", "are", "vs", "from"]);
  const isAnd = (w) => /^(and|&|or)$/i.test(w || "");

  // A short label for a node: its short_title if it has one, else the first
  // few meaningful words of the title (no leading articles or filler, never
  // splitting a "Noun and Noun" pair when it fits in 5 words, never ending on
  // a dangling stop word). Pure and deterministic.
  function keyTitle(node, fullTitle) {
    if (node && node.short_title) return node.short_title;
    const title = (fullTitle != null ? fullTitle : defaultTitle(node)).replace(/\s+/g, " ").trim();
    let words = title.split(" ").filter(Boolean);
    while (words.length > 1 && LEAD_FILLER.has(words[0].toLowerCase().replace(/[^a-z]/g, ""))) words.shift();
    if (words.length <= 4) return finishKey(words, title);
    let cut = 4;
    if (isAnd(words[cut - 1])) cut = 5; // "Noun and" + Noun
    else if (isAnd(words[cut]) && words.length > cut + 1) cut = 3; // Noun | and Noun: pair would need 6
    const out = words.slice(0, cut);
    return finishKey(out, title);
  }

  function finishKey(words, fallback) {
    const out = words.slice();
    while (out.length > 1 && TRAIL_STOP.has(out[out.length - 1].toLowerCase().replace(/[^a-z&]/g, ""))) out.pop();
    let t = out.join(" ").replace(/[\s,;:\-\u2013\u2014.?!]+$/, "");
    if (!t) t = fallback;
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  function titleLines(text, width, fontPx) {
    const perLine = Math.max(1, (width - 28) / (fontPx * 0.62));
    return Math.max(1, Math.ceil((text || "").length / Math.max(1, perLine)));
  }

  // Ordered strip layout of `weights` into (x, y, w, h) with `gap` between
  // cells (and none around the outside). To get exact outer margins the
  // container is grown by gap/2 all round and every cell shrinks by gap/2.
  function strips(weights, x, y, w, h, gap) {
    const n = weights.length;
    const out = new Array(n);
    const X = x - gap / 2;
    const Y = y - gap / 2;
    const Wd = w + gap;
    const Hd = h + gap;
    const rows = Wd >= Hd;
    let rx = X;
    let ry = Y;
    let rw = Wd;
    let rh = Hd;
    let R = 0;
    for (const v of weights) R += v;
    const sumRange = (a, b) => {
      let s = 0;
      for (let k = a; k < b; k++) s += weights[k];
      return s;
    };
    const avgAspect = (a, b) => {
      const S = sumRange(a, b);
      const thick = Math.max(1e-6, ((rows ? rh : rw) * S) / R);
      const len = rows ? rw : rh;
      let t = 0;
      for (let k = a; k < b; k++) {
        const l = Math.max(1e-6, (len * weights[k]) / S);
        t += Math.max(l / thick, thick / l);
      }
      return t / (b - a);
    };
    let i = 0;
    while (i < n) {
      let j = i + 1;
      let cur = avgAspect(i, j);
      while (j < n) {
        const next = avgAspect(i, j + 1);
        if (next <= cur) {
          cur = next;
          j++;
        } else break;
      }
      const S = sumRange(i, j);
      const thick = (rows ? rh : rw) * (S / R);
      const len = rows ? rw : rh;
      let pos = rows ? rx : ry;
      for (let k = i; k < j; k++) {
        const l = (len * weights[k]) / S;
        out[k] = rows ? { x: pos, y: ry, w: l, h: thick } : { x: rx, y: pos, w: thick, h: l };
        pos += l;
      }
      if (rows) {
        ry += thick;
        rh -= thick;
      } else {
        rx += thick;
        rw -= thick;
      }
      R -= S;
      i = j;
    }
    const g = gap / 2;
    return out.map((r) => ({ x: r.x + g, y: r.y + g, w: Math.max(0, r.w - gap), h: Math.max(0, r.h - gap) }));
  }

  function weightsFor(ids, words) {
    let total = 0;
    for (const id of ids) total += words.get(id) || 0;
    const floor = FLOOR * total;
    return ids.map((id) => Math.max(words.get(id) || 0, floor, 1e-3));
  }

  /**
   * @param {object} tree - Tree JSON (nodes, root, sections).
   * @param {number} W - map width in px.
   * @param {number} H - map height in px.
   * @param {object} [opts] - { titleOf(node) -> string, density: "compact"|"full" }
   *   Compact reserves a smaller header (numeral + at most 2 title lines, no
   *   meta line) and sizes it from the key title.
   * @returns {Map<string, {x:number,y:number,w:number,h:number,headerH:number,side:boolean}>}
   */
  function layout(tree, W, H, opts) {
    opts = opts || {};
    const titleOf = opts.titleOf || defaultTitle;
    const compact = opts.density === "compact";
    const nodes = tree.nodes;
    const words = wordsInSource(tree);
    const out = new Map();

    let top = tree.sections && tree.sections.length ? tree.sections.slice() : null;
    if (!top) {
      const root = nodes[tree.root];
      top = root && root.children && root.children.length ? root.children.slice() : [tree.root];
    }
    top = top.filter((id) => nodes[id]);

    function place(id, x, y, w, h, level) {
      const n = nodes[id];
      const rect = { x, y, w, h, headerH: 0, side: false };
      out.set(id, rect);
      if (!n || n.is_leaf || !n.children || !n.children.length) return;
      const kids = n.children.filter((c) => nodes[c]);
      if (!kids.length) return;
      // Wide rectangle: header on the left. (Deviation from the spec: not when
      // that would leave a header narrower than ~84px, where titles cannot fit.)
      const side = w > 1.8 * h && w >= 240;
      const hw = side ? Math.min(200, 0.35 * w) : w;
      let headerH;
      if (compact) {
        // numeral 22 + key title (<= 2 lines at the top level, 1 below); no meta.
        const lines = Math.min(level === 0 ? 2 : 1, titleLines(keyTitle(n, titleOf(n)), hw, level === 0 ? 14 : 13));
        headerH = level === 0 ? 8 + 22 + 4 + lines * 17 + 8 : 8 + 17 + 8;
      } else {
        const lines = titleLines(titleOf(n), hw, level === 0 ? 15 : 13);
        headerH = level === 0 ? 12 + 36 + 6 + lines * 19.5 + 6 + 17 + 10 : 8 + lines * 17 + 8;
      }
      rect.headerH = headerH;
      rect.side = side;
      let cx, cy, cw, ch;
      if (side) {
        cx = x + hw;
        cy = y + INNER;
        cw = w - hw - INNER;
        ch = h - 2 * INNER;
      } else {
        cx = x + INNER;
        cy = y + headerH;
        cw = w - 2 * INNER;
        ch = h - headerH - INNER;
      }
      if (cw < MIN_CONTENT || ch < MIN_CONTENT) return; // too small: draws solid
      const cells = strips(weightsFor(kids, words), cx, cy, cw, ch, CHILD_GAP);
      kids.forEach((kid, i) => place(kid, cells[i].x, cells[i].y, cells[i].w, cells[i].h, level + 1));
    }

    if (!top.length) return out;
    const cells = strips(weightsFor(top, words), PAD, PAD, Math.max(0, W - 2 * PAD), Math.max(0, H - 2 * PAD), TOP_GAP);
    top.forEach((id, i) => place(id, cells[i].x, cells[i].y, cells[i].w, cells[i].h, 0));
    return out;
  }

  window.MapLayout = { layout, wordsInSource, strips, keyTitle };
})();
