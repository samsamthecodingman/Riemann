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

import re

from riemann.abstraction.model import Tree


def _mid(node) -> float:
    return (node.source_span[0] + node.source_span[1]) / 2


def _priority_key(tree: Tree, node_id: str, anchor_id: str):
    """Nearest to the anchor by document offset (source-span midpoints), then
    higher importance, then shallower depth, then id. Must match
    buildExpansionSequence in web/frontier.js exactly."""
    node = tree.nodes[node_id]
    distance = abs(_mid(node) - _mid(tree.nodes[anchor_id]))
    return (distance, -node.importance, node.depth, node_id)


PROSE = "~"
"""Sequence token prefix: ``"~<id>"`` switches node <id> from its skim form
(title + key points) to its prose summary. A plain ``"<id>"`` expands it
into its children."""

GAIN_FRACTION = 0.15
GAIN_WORDS = 25
"""The zoom-step rule: every step must add at least min(15% of the words on
the page, 25 words) of visible text. Steps that don't are merged into the
next one, so a single step does both (see ``expansion_sequence``)."""


def _token_node(token: str) -> str:
    return token[1:] if token.startswith(PROSE) else token


def _apply(tree: Tree, expanded: set[str], prose: set[str], token: str) -> None:
    """Apply one token to a page state. Applying a token for node N also
    opens every ancestor of N (a token can only be reached through them), which
    is what lets a merged step drop the tokens it makes redundant."""
    nid = _token_node(token)
    p = tree.nodes[nid].parent
    while p is not None:
        expanded.add(p)
        p = tree.nodes[p].parent
    if token.startswith(PROSE):
        prose.add(nid)
    else:
        expanded.add(nid)


def _frontier_of(tree: Tree, expanded: set[str]) -> list[str]:
    out: list[str] = []

    def visit(nid: str) -> None:
        if nid in expanded:
            for c in tree.nodes[nid].children:
                visit(c)
        else:
            out.append(nid)

    visit(tree.root)
    return out


def _count(text: str | None) -> int:
    return len((text or "").split())


def _first_clause(text: str) -> str:
    m = re.match(r"^[^.!?\n]{1,80}", text or "")
    return (m.group(0) if m else (text or "")).strip()


def _has_skim(node) -> bool:
    return bool(node.key_points) or bool(node.hook)


def _is_skim(tree: Tree, node, prose: set[str]) -> bool:
    return (not node.is_leaf) and node.id != tree.root and node.id not in prose and _has_skim(node)


def _skim_words(node) -> int:
    points = node.key_points if node.key_points else [node.hook]
    return _count(node.title or _first_clause(node.text)) + sum(_count(p) for p in points)


def visible_words(tree: Tree, frontier: list[str], prose: set[str]) -> int:
    """Words on the page for a frontier and prose set, as web/app.js renders
    it: a lone root is its hook line; a skim node is its title plus its key
    points; anything else is the node's own text."""
    if len(frontier) == 1 and frontier[0] == tree.root:
        root = tree.nodes[tree.root]
        return _count(root.hook or root.text)
    total = 0
    for nid in frontier:
        node = tree.nodes[nid]
        total += _skim_words(node) if _is_skim(tree, node, prose) else node.words
    return total


def _same_page(tree: Tree, a: tuple[set[str], set[str]], b: tuple[set[str], set[str]]) -> bool:
    fa, fb = _frontier_of(tree, a[0]), _frontier_of(tree, b[0])
    return fa == fb and {n for n in a[1] if n in set(fa)} == {n for n in b[1] if n in set(fb)}


def expansion_sequence(
    tree: Tree,
    anchor_id: str | None = None,
    start_frontier: set[str] | None = None,
    keep_expanded: set[str] | None = None,
) -> list[str]:
    """Compute the full ordered zoom sequence from a starting frontier.

    Every internal node except the root passes through three forms as the
    dial turns up: **skim** (its title and key points, how it first appears
    when its parent opens), then **prose** (its summary paragraph, token
    ``"~id"``), then **expanded** (replaced by its children, token ``"id"``).
    The root has no skim form (at k=0 it is the hero line) and goes straight
    to expanded; leaves are verbatim source and have no tokens.

    **Every step must add visible content.** A candidate step is applied
    tentatively; unless it adds at least min(15% of the current visible words,
    25 words) it is not emitted. Instead the *next* step must build on it (a
    token that, applied alone, reaches the same page as the tentative steps
    plus itself), and only that later token is emitted, so one step does
    both. A node with a single child never counts as adding content (not its
    prose, not its expansion, not a page that newly shows one), so
    single-child chains are always merged through. If nothing can
    continue the chain, the tentative step is emitted on its own.

    Because a merged step's token stands for the dropped ones, applying a
    token for node N also opens every ancestor of N (see ``_apply``);
    ``frontier_at`` and ``prose_at`` replay that.

    anchor_id: node to prioritise steps near. Defaults to the root.
    start_frontier: the frontier to start from. Defaults to ``{tree.root}``.
    keep_expanded: tokens already applied right now (the expanded ids, plus
    ``"~id"`` for passages currently shown as prose). They go first, one
    plain step each (never merged), so re-anchoring keeps the page exactly as
    it is: frontier_at/prose_at(seq, len(keep_expanded)) is the current page.
    Must be closed under ancestors (any real page's applied set is).
    """
    anchor = anchor_id or tree.root
    keep = set(keep_expanded or ())
    expanded: set[str] = set()
    prose: set[str] = set()
    for nid in (set(start_frontier) if start_frontier is not None else {tree.root}):
        p = tree.nodes[nid].parent
        while p is not None:
            expanded.add(p)
            p = tree.nodes[p].parent
    sequence: list[str] = []

    def key(token: str):
        return _priority_key(tree, _token_node(token), anchor) + (0 if token.startswith(PROSE) else 1,)

    def internal_frontier() -> list[str]:
        return [n for n in _frontier_of(tree, expanded) if not tree.nodes[n].is_leaf]

    # 1. The page as it is now, one plain step per applied token.
    remaining = set(keep)
    while remaining:
        front = set(internal_frontier())
        avail = [
            t for t in remaining
            if _token_node(t) in front and (t == _token_node(t) or _token_node(t) != tree.root)
        ]
        if not avail:
            break
        best = min(avail, key=key)
        remaining.discard(best)
        sequence.append(best)
        _apply(tree, expanded, prose, best)

    # 2. Everything else, merging steps that add too little.
    committed = (set(expanded), set(prose))
    v0 = visible_words(tree, _frontier_of(tree, expanded), prose)
    pending: list[str] = []
    while True:
        cands = []
        for nid in internal_frontier():
            cands.append(nid if nid == tree.root or nid in prose else PROSE + nid)
        if pending:
            work = (set(expanded), set(prose))
            allowed = []
            for t in cands:
                direct = (set(committed[0]), set(committed[1]))
                _apply(tree, direct[0], direct[1], t)
                chained = (set(work[0]), set(work[1]))
                _apply(tree, chained[0], chained[1], t)
                if _same_page(tree, direct, chained):
                    allowed.append(t)
            if not allowed:
                # Nothing can continue the tentative steps: emit the last one alone.
                sequence.append(pending[-1])
                committed = (set(expanded), set(prose))
                v0 = visible_words(tree, _frontier_of(tree, expanded), prose)
                pending = []
                continue
            cands = allowed
        if not cands:
            break
        best = min(cands, key=key)
        _apply(tree, expanded, prose, best)
        pending.append(best)
        v1 = visible_words(tree, _frontier_of(tree, expanded), prose)
        # A pass-through level (one child) never counts as content: not its
        # prose, not its expansion, and not a page that newly shows one.
        was = set(_frontier_of(tree, committed[0]))
        single = len(tree.nodes[_token_node(best)].children) == 1 or any(
            len(tree.nodes[n].children) == 1
            for n in _frontier_of(tree, expanded)
            if n not in was and not tree.nodes[n].is_leaf
        )
        need = max(1.0, min(GAIN_FRACTION * v0, GAIN_WORDS))
        if not single and v1 - v0 >= need:
            sequence.append(best)
            committed = (set(expanded), set(prose))
            v0 = v1
            pending = []
    if pending:
        sequence.append(pending[-1])
    return sequence


def _replay(tree: Tree, sequence: list[str], k: int) -> tuple[set[str], set[str]]:
    expanded: set[str] = set()
    prose: set[str] = set()
    for token in sequence[:k]:
        _apply(tree, expanded, prose, token)
    return expanded, prose


def frontier_at(tree: Tree, sequence: list[str], k: int) -> list[str]:
    """Replay the first k steps of `sequence` onto {root}, returning the
    resulting frontier in document order (by source_span start). Prose
    tokens don't change the frontier (beyond opening their ancestors), only
    how a node is shown."""
    expanded, _ = _replay(tree, sequence, k)
    return sorted(_frontier_of(tree, expanded), key=lambda nid: tree.nodes[nid].source_span[0])


def prose_at(sequence: list[str], k: int) -> set[str]:
    """Node ids shown as their prose summary after the first k steps (every
    other internal node on the page is shown in skim form)."""
    return {_token_node(t) for t in sequence[:k] if t.startswith(PROSE)}


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
