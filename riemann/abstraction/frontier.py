"""Reference implementation of the continuous-zoom expansion sequence.

This is the contract the frontend mirrors in JavaScript (see
docs/v1-build-spec.md, "Continuous zoom"). Keep the algorithm here exactly
in sync with that spec -- these docstrings are the spec for the JS port.

Core ideas
----------
- The **frontier** is the set of rendered node ids, in document order,
  such that no rendered node is an ancestor of another rendered node.
  It always starts as ``{root}`` (frontier(0) == [root]).
- The **expansion sequence** is one ordered list of *internal* node ids:
  ``sequence[i]`` is the i-th node to expand (replace with its children)
  as the dial turns up. It is computed greedily: at each step, among the
  internal nodes currently in the frontier, pick the one with the best
  priority, expand it (remove it from the frontier, add its children),
  and repeat until the frontier is all leaves.
- This makes the sequence **topologically valid by construction**: a node
  can only be expanded once it is in the frontier, which requires its
  parent to have been expanded first (or the node is the root).
- ``k = round(z * total_expansions)`` where ``total_expansions ==
  len(sequence)``. ``frontier(k)`` replays the first ``k`` entries of the
  sequence onto ``{root}``. ``frontier(0) == [root]``,
  ``frontier(total_expansions)`` is exactly the leaves.
- The sequence is **monotonic**: frontier(k) is always reachable from
  frontier(k-1) by exactly one expansion (one node removed, its children
  added), so growing k only ever expands, never collapses, a node.

Priority (nearest-first, then importance, then depth)
-------------------------------------------------------
For each internal node currently in the frontier, compute:

1. **distance from the anchored node**, in tree hops: ``depth(node) +
   depth(anchor) - 2 * depth(lca(node, anchor))``. This is recomputed
   whenever the anchor changes (e.g. after a scroll) -- the anchor is a
   parameter to this function, not baked into a single global sequence.
2. **higher importance** wins ties (importance is 0..1, relative to
   siblings; descending order).
3. **shallower depth** wins remaining ties (ascending ``Node.depth``).
4. node id, for full determinism in tests.

The node with the lowest ``(distance, -importance, depth, id)`` tuple is
expanded next.
"""

from __future__ import annotations

from riemann.abstraction.model import Tree


def _ancestor_depths(tree: Tree, node_id: str) -> dict[str, int]:
    """id -> depth for node_id and all its ancestors, root included."""
    out: dict[str, int] = {}
    cur: str | None = node_id
    while cur is not None:
        out[cur] = tree.nodes[cur].depth
        cur = tree.nodes[cur].parent
    return out


def hop_distance(tree: Tree, a: str, b: str) -> int:
    """Tree-hop distance between two nodes, via their lowest common ancestor."""
    if a == b:
        return 0
    a_ancestors = _ancestor_depths(tree, a)
    cur: str | None = b
    while cur is not None and cur not in a_ancestors:
        cur = tree.nodes[cur].parent
    if cur is None:
        # Disconnected (shouldn't happen in a well-formed tree); treat as far.
        return len(tree.nodes)
    lca_depth = tree.nodes[cur].depth
    return (tree.nodes[a].depth - lca_depth) + (tree.nodes[b].depth - lca_depth)


def _mid(node) -> float:
    return (node.source_span[0] + node.source_span[1]) / 2


def _priority_key(tree: Tree, node_id: str, anchor_id: str):
    """Nearest to the anchor by document offset (source-span midpoints), then
    higher importance, then shallower depth, then id. Must match
    buildExpansionSequence in web/frontier.js exactly."""
    node = tree.nodes[node_id]
    distance = abs(_mid(node) - _mid(tree.nodes[anchor_id]))
    return (distance, -node.importance, node.depth, node_id)


def expansion_sequence(
    tree: Tree,
    anchor_id: str | None = None,
    start_frontier: set[str] | None = None,
    keep_expanded: set[str] | None = None,
) -> list[str]:
    """Compute the full ordered expansion sequence from a starting frontier.

    anchor_id: node to prioritise expansions near. Defaults to the root
    (i.e. no particular anchor -- ties broken purely by importance/depth).
    start_frontier: the frontier to start expanding from. Defaults to
    ``{tree.root}``, i.e. the sequence for a fresh dial at z=0.
    keep_expanded: nodes that are expanded right now. They go first (still
    parents-first, nearest-first among themselves), so re-anchoring keeps
    the page exactly as it is: frontier_at(seq, len(keep_expanded)) is the
    current frontier, and the next step in either direction changes one
    node. Must be closed under ancestors (any valid frontier's expanded set
    is).
    """
    anchor = anchor_id or tree.root
    frontier = set(start_frontier) if start_frontier is not None else {tree.root}
    keep = keep_expanded or set()
    sequence: list[str] = []

    while True:
        candidates = [nid for nid in frontier if not tree.nodes[nid].is_leaf]
        if not candidates:
            break
        best = min(
            candidates,
            key=lambda nid: (0 if nid in keep else 1,) + _priority_key(tree, nid, anchor),
        )
        sequence.append(best)
        frontier.discard(best)
        frontier.update(tree.nodes[best].children)

    return sequence


def frontier_at(tree: Tree, sequence: list[str], k: int) -> list[str]:
    """Replay the first k expansions of `sequence` onto {root}, returning
    the resulting frontier in document order (by source_span start)."""
    frontier = {tree.root}
    for node_id in sequence[:k]:
        frontier.discard(node_id)
        frontier.update(tree.nodes[node_id].children)
    return sorted(frontier, key=lambda nid: tree.nodes[nid].source_span[0])


def k_for_z(z: float, total_expansions: int) -> int:
    """Map a dial position z in [0, 1] to a number of expansions k."""
    z = max(0.0, min(1.0, z))
    return round(z * total_expansions)


def find_anchor_replacement(tree: Tree, frontier: list[str], offset: int) -> str:
    """Find the frontier node that should keep the anchor after an expansion.

    Given the *new* frontier (after expanding/collapsing) and the source
    char offset of the old anchor's viewport-centre point, return the
    frontier node whose source_span contains that offset (the tightest
    such match, i.e. the child rather than a wider ancestor if both
    somehow qualify). If no frontier node's span contains the offset
    (shouldn't normally happen since spans cover the source), fall back to
    the frontier node whose span midpoint is nearest.
    """
    containing = [
        nid
        for nid in frontier
        if tree.nodes[nid].source_span[0] <= offset < tree.nodes[nid].source_span[1]
    ]
    if containing:
        return min(
            containing,
            key=lambda nid: tree.nodes[nid].source_span[1] - tree.nodes[nid].source_span[0],
        )
    return min(
        frontier,
        key=lambda nid: abs(
            (tree.nodes[nid].source_span[0] + tree.nodes[nid].source_span[1]) / 2 - offset
        ),
    )
