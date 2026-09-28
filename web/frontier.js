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
//     priority: (1) nearest to the anchor node, (2) higher importance,
//     (3) shallower depth. A node only becomes a candidate once its
//     parent has already been expanded (or it is the root), which is
//     what keeps the sequence topologically valid.
//   - z maps to k = round(z * total_expansions); Frontier(k) = the set of
//     nodes visible when the first k entries of the sequence are expanded.
// -----------------------------------------------------------------------

/**
 * Build the expansion sequence for a tree, anchored at a given node.
 * Recompute this whenever the anchor changes (e.g. after a scroll).
 *
 * @param {object} tree - Tree JSON per the shared schema (nodes: {id: Node}).
 * @param {string} anchorNodeId - id of the node currently at viewport centre.
 * @returns {string[]} ordered list of internal node ids to expand, in order.
 */
function buildExpansionSequence(tree, anchorNodeId) {
  const nodes = tree.nodes;
  const anchor = nodes[anchorNodeId] || nodes[tree.root];
  const anchorMid = (anchor.source_span[0] + anchor.source_span[1]) / 2;

  const distanceOf = (node) => {
    const mid = (node.source_span[0] + node.source_span[1]) / 2;
    return Math.abs(mid - anchorMid);
  };

  const sequence = [];
  // Candidates: internal nodes whose parent has already been expanded
  // (or the root, which is always an initial candidate if it's internal).
  const candidates = [];

  const root = nodes[tree.root];
  if (root && !root.is_leaf) candidates.push(tree.root);

  while (candidates.length > 0) {
    // Pick the best candidate: nearest to anchor, then higher importance,
    // then shallower depth. Linear scan is fine at tree sizes seen here.
    let bestIdx = 0;
    for (let i = 1; i < candidates.length; i++) {
      const a = nodes[candidates[i]];
      const b = nodes[candidates[bestIdx]];
      const da = distanceOf(a);
      const db = distanceOf(b);
      if (da !== db) {
        if (da < db) bestIdx = i;
        continue;
      }
      if (a.importance !== b.importance) {
        if (a.importance > b.importance) bestIdx = i;
        continue;
      }
      if (a.depth < b.depth) bestIdx = i;
    }

    const id = candidates.splice(bestIdx, 1)[0];
    sequence.push(id);

    const node = nodes[id];
    for (const childId of node.children) {
      const child = nodes[childId];
      if (child && !child.is_leaf) candidates.push(childId);
    }
  }

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
  const expanded = new Set(sequence.slice(0, Math.max(0, k)));
  const nodes = tree.nodes;
  const result = [];

  const visit = (id) => {
    if (expanded.has(id)) {
      const node = nodes[id];
      for (const childId of node.children) visit(childId);
    } else {
      result.push(id);
    }
  };

  visit(tree.root);
  return result;
}

/**
 * Convenience: frontier directly from z.
 */
function frontierAtZ(tree, sequence, z) {
  const k = zToK(z, sequence.length);
  return { frontier: frontierAtK(tree, sequence, k), k };
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
  findFrontierNodeAtOffset,
};
