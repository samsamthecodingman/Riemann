// frontier.js
// -----------------------------------------------------------------------
// The continuous-zoom expansion algorithm. This module is a JS mirror of
// the Python reference implementation `riemann/abstraction/frontier.py`
// (see docs/v1-build-spec.md, "Continuous zoom (frontend)"). If that
// Python file exists and diverges from this one, this file is wrong —
// fix it to match, not the other way around.
//
// Concepts:
//   - z in [0,1]: 0 = root gist only, 1 = every leaf (full source).
//   - "expansion sequence": one precomputed, topologically valid order in
//     which internal (non-leaf) nodes get expanded, built greedily by
//     priority: (1) nearest to the anchor by document offset (source-span
//     midpoints), (2) higher importance, (3) shallower depth, (4) id. A node only becomes a candidate once its
//     parent has already been expanded (or it is the root), which is
//     what keeps the sequence topologically valid.
//   - z maps to k = round(z * total_expansions); Frontier(k) = the set of
//     nodes visible when the first k entries of the sequence are expanded.
// -----------------------------------------------------------------------

// Sequence token prefix: "~<id>" switches node <id> from its skim form
// (title + key points) to its prose summary; a plain "<id>" expands it into
// its children. Mirrors PROSE in riemann/abstraction/frontier.py.
const PROSE = "~";

function tokenNode(token) {
  return token.charAt(0) === PROSE ? token.slice(1) : token;
}

// The zoom-step rule (mirrors GAIN_FRACTION / GAIN_WORDS in frontier.py):
// every step adds at least min(15% of the visible words, 25 words); steps
// that don't are merged into the next one.
const GAIN_FRACTION = 0.15;
const GAIN_WORDS = 25;

function countWords(text) {
  return ((text || "").match(/\S+/g) || []).length;
}

function firstClause(text) {
  const m = (text || "").match(/^[^.!?\n]{1,80}/);
  return (m ? m[0] : text || "").trim();
}

function hasSkim(node) {
  return (node.key_points && node.key_points.length > 0) || !!node.hook;
}

function isSkimNode(tree, node, prose) {
  return !node.is_leaf && node.id !== tree.root && !prose.has(node.id) && hasSkim(node);
}

function skimWordsOf(node) {
  const points = node.key_points && node.key_points.length ? node.key_points : [node.hook];
  return countWords(node.title || firstClause(node.text)) + points.reduce((sum, p) => sum + countWords(p), 0);
}

/**
 * Words on the page for a frontier and prose set, as app.js renders it: a
 * lone root is its hook line; a skim node is its title plus key points;
 * anything else is the node's own text. Mirrors visible_words in frontier.py.
 */
function visibleWords(tree, frontier, prose) {
  if (frontier.length === 1 && frontier[0] === tree.root) {
    const root = tree.nodes[tree.root];
    return countWords(root.hook || root.text);
  }
  let total = 0;
  for (const id of frontier) {
    const node = tree.nodes[id];
    total += isSkimNode(tree, node, prose) ? skimWordsOf(node) : node.words;
  }
  return total;
}

/**
 * Apply one token to a page state ({expanded:Set, prose:Set}). A token for
 * node N also opens every ancestor of N, which is what lets a merged step
 * drop the tokens it makes redundant.
 */
function applyToken(tree, state, token) {
  const nid = tokenNode(token);
  let p = tree.nodes[nid].parent;
  while (p != null) {
    state.expanded.add(p);
    p = tree.nodes[p].parent;
  }
  if (token.charAt(0) === PROSE) state.prose.add(nid);
  else state.expanded.add(nid);
}

function cloneState(st) {
  return { expanded: new Set(st.expanded), prose: new Set(st.prose) };
}

function frontierOfExpanded(tree, expanded) {
  const out = [];
  const visit = (id) => {
    if (expanded.has(id)) {
      for (const c of tree.nodes[id].children) visit(c);
    } else {
      out.push(id);
    }
  };
  visit(tree.root);
  return out;
}

function sameFrontier(a, b) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

function samePage(tree, a, b) {
  const fa = frontierOfExpanded(tree, a.expanded);
  const fb = frontierOfExpanded(tree, b.expanded);
  if (!sameFrontier(fa, fb)) return false;
  const inF = new Set(fa);
  const pa = [...a.prose].filter((n) => inF.has(n)).sort();
  const pb = [...b.prose].filter((n) => inF.has(n)).sort();
  return sameFrontier(pa, pb);
}

/**
 * Build the zoom sequence for a tree, anchored at a given node.
 * Recompute this whenever the anchor changes (e.g. after a scroll).
 * Mirrors expansion_sequence in riemann/abstraction/frontier.py exactly; read
 * its docstring for the rule (steps that add too little are merged into the
 * next one; applying a token opens its node's ancestors).
 *
 * @param {object} tree - Tree JSON per the shared schema (nodes: {id: Node}).
 * @param {string} anchorNodeId - id of the node currently at viewport centre.
 * @param {Set<string>} [keepExpanded] - tokens applied right now (expanded
 *   ids and "~id" prose tokens). They go first, one plain step each, so
 *   re-anchoring keeps the page exactly as it is.
 * @returns {string[]} ordered list of tokens.
 */
function buildExpansionSequence(tree, anchorNodeId, keepExpanded) {
  const nodes = tree.nodes;
  const anchor = nodes[anchorNodeId] || nodes[tree.root];
  const anchorMid = (anchor.source_span[0] + anchor.source_span[1]) / 2;

  const distanceOf = (node) => {
    const mid = (node.source_span[0] + node.source_span[1]) / 2;
    return Math.abs(mid - anchorMid);
  };

  // -1 / 0 / 1: token order by (distance, -importance, depth, node id, prose before expand).
  const compare = (ta, tb) => {
    const a = nodes[tokenNode(ta)];
    const b = nodes[tokenNode(tb)];
    const da = distanceOf(a);
    const db = distanceOf(b);
    if (da !== db) return da < db ? -1 : 1;
    if (a.importance !== b.importance) return a.importance > b.importance ? -1 : 1;
    if (a.depth !== b.depth) return a.depth < b.depth ? -1 : 1;
    if (a.id !== b.id) return a.id < b.id ? -1 : 1;
    const ka = ta.charAt(0) === PROSE ? 0 : 1;
    const kb = tb.charAt(0) === PROSE ? 0 : 1;
    return ka === kb ? 0 : ka < kb ? -1 : 1;
  };
  const best = (list) => list.reduce((m, t) => (compare(t, m) < 0 ? t : m), list[0]);

  const st = { expanded: new Set(), prose: new Set() };
  const sequence = [];
  const internalFrontier = () =>
    frontierOfExpanded(tree, st.expanded).filter((id) => !nodes[id].is_leaf);
  const words = () => visibleWords(tree, frontierOfExpanded(tree, st.expanded), st.prose);

  // 1. The page as it is now, one plain step per applied token.
  const remaining = new Set(keepExpanded || []);
  while (remaining.size) {
    const front = new Set(internalFrontier());
    const avail = [...remaining].filter((t) => front.has(tokenNode(t)) && !(t.charAt(0) === PROSE && tokenNode(t) === tree.root));
    if (!avail.length) break;
    const pick = best(avail);
    remaining.delete(pick);
    sequence.push(pick);
    applyToken(tree, st, pick);
  }

  // 2. Everything else, merging steps that add too little.
  let committed = cloneState(st);
  let v0 = words();
  let pending = [];
  for (;;) {
    let cands = internalFrontier().map((id) => (id === tree.root || st.prose.has(id) ? id : PROSE + id));
    if (pending.length) {
      const allowed = cands.filter((t) => {
        const direct = cloneState(committed);
        applyToken(tree, direct, t);
        const chained = cloneState(st);
        applyToken(tree, chained, t);
        return samePage(tree, direct, chained);
      });
      if (!allowed.length) {
        sequence.push(pending[pending.length - 1]);
        committed = cloneState(st);
        v0 = words();
        pending = [];
        continue;
      }
      cands = allowed;
    }
    if (!cands.length) break;
    const pick = best(cands);
    applyToken(tree, st, pick);
    pending.push(pick);
    const v1 = words();
    // A pass-through level (one child) never counts as content: not its
    // prose, not its expansion, and not a page that newly shows one.
    const was = new Set(frontierOfExpanded(tree, committed.expanded));
    const single =
      nodes[tokenNode(pick)].children.length === 1 ||
      frontierOfExpanded(tree, st.expanded).some((n) => !was.has(n) && !nodes[n].is_leaf && nodes[n].children.length === 1);
    const need = Math.max(1, Math.min(GAIN_FRACTION * v0, GAIN_WORDS));
    if (!single && v1 - v0 >= need) {
      sequence.push(pick);
      committed = cloneState(st);
      v0 = v1;
      pending = [];
    }
  }
  if (pending.length) sequence.push(pending[pending.length - 1]);
  return sequence;
}

/**
 * Map a dial position z (0..1) to k, the number of expansions applied.
 * @param {number} z
 * @param {number} totalExpansions
 * @returns {number} k
 */
function zToK(z, totalExpansions) {
  const clamped = Math.max(0, Math.min(1, z));
  return Math.round(clamped * totalExpansions);
}

/**
 * Compute the frontier (rendered node ids, in document order) for a given
 * k against a precomputed expansion sequence.
 *
 * @param {object} tree
 * @param {string[]} sequence - result of buildExpansionSequence
 * @param {number} k
 * @returns {string[]} node ids in document order; no rendered node is an
 *   ancestor of another.
 */
function frontierAtK(tree, sequence, k) {
  const st = { expanded: new Set(), prose: new Set() };
  for (const t of sequence.slice(0, Math.max(0, k))) applyToken(tree, st, t);
  return frontierOfExpanded(tree, st.expanded);
}

/**
 * Smallest k at which `nodeId` is on the page (or inside a node that is):
 * every ancestor of it has been opened. Used to jump to a node.
 */
function kToReveal(tree, sequence, nodeId) {
  const need = [];
  for (let p = tree.nodes[nodeId].parent; p != null; p = tree.nodes[p].parent) need.push(p);
  const st = { expanded: new Set(), prose: new Set() };
  const done = () => need.every((p) => st.expanded.has(p));
  if (done()) return 0;
  for (let k = 0; k < sequence.length; k++) {
    applyToken(tree, st, sequence[k]);
    if (done()) return k + 1;
  }
  return sequence.length;
}

/**
 * Convenience: frontier directly from z.
 */
function frontierAtZ(tree, sequence, z) {
  const k = zToK(z, sequence.length);
  return { frontier: frontierAtK(tree, sequence, k), prose: proseAtK(sequence, k), k };
}

/**
 * Node ids shown as their prose summary after the first k steps; every
 * other internal node on the page is shown in skim form (title + key points).
 * @param {string[]} sequence
 * @param {number} k
 * @returns {Set<string>}
 */
function proseAtK(sequence, k) {
  const out = new Set();
  for (const t of sequence.slice(0, Math.max(0, k))) if (t.charAt(0) === PROSE) out.add(tokenNode(t));
  return out;
}

/**
 * Given a set of currently-expanded node ids (from a previous k), find the
 * node in the new frontier that "replaces" a given node id: the frontier
 * node whose source_span contains the given char offset, else the nearest
 * ancestor present in the frontier. Used for anchoring across zoom changes.
 *
 * @param {object} tree
 * @param {string[]} frontier - node ids currently rendered, in document order
 * @param {number} offset - a char offset into tree.source_text
 * @returns {string|null}
 */
function findFrontierNodeAtOffset(tree, frontier, offset) {
  for (const id of frontier) {
    const node = tree.nodes[id];
    if (node.source_span[0] <= offset && offset <= node.source_span[1]) {
      return id;
    }
  }
  // Fallback: nearest by distance to span midpoint.
  let best = null;
  let bestDist = Infinity;
  for (const id of frontier) {
    const node = tree.nodes[id];
    const mid = (node.source_span[0] + node.source_span[1]) / 2;
    const d = Math.abs(mid - offset);
    if (d < bestDist) {
      bestDist = d;
      best = id;
    }
  }
  return best;
}

// Exposed as a plain global (no build step / module system in this project).
window.Frontier = {
  buildExpansionSequence,
  zToK,
  frontierAtK,
  frontierAtZ,
  proseAtK,
  kToReveal,
  visibleWords,
  findFrontierNodeAtOffset,
  PROSE,
};
