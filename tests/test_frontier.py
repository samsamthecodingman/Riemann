import pytest

from riemann.abstraction.frontier import (
    expansion_sequence,
    find_anchor_replacement,
    frontier_at,
    k_for_z,
)
from riemann.abstraction.model import Node, Tree


def _make_tree() -> Tree:
    # root -> a, b
    # a -> a1, a2 (leaves)
    # b -> b1, b2 (leaves)
    nodes = {
        "root": Node(id="root", depth=0, text="root", words=1, children=["a", "b"], parent=None, is_leaf=False, source_span=(0, 40), importance=1.0),
        "a": Node(id="a", depth=1, text="a", words=1, children=["a1", "a2"], parent="root", is_leaf=False, source_span=(0, 20), importance=0.9),
        "b": Node(id="b", depth=1, text="b", words=1, children=["b1", "b2"], parent="root", is_leaf=False, source_span=(20, 40), importance=0.3),
        "a1": Node(id="a1", depth=2, text="a1", words=1, children=[], parent="a", is_leaf=True, source_span=(0, 10), importance=0.5),
        "a2": Node(id="a2", depth=2, text="a2", words=1, children=[], parent="a", is_leaf=True, source_span=(10, 20), importance=0.5),
        "b1": Node(id="b1", depth=2, text="b1", words=1, children=[], parent="b", is_leaf=True, source_span=(20, 30), importance=0.5),
        "b2": Node(id="b2", depth=2, text="b2", words=1, children=[], parent="b", is_leaf=True, source_span=(30, 40), importance=0.5),
    }
    return Tree(
        id="test",
        title="Test",
        source_text="x" * 40,
        source_words=8,
        root="root",
        nodes=nodes,
        max_depth=2,
        status="done",
    )


def test_k0_gives_root():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    assert frontier_at(tree, seq, 0) == ["root"]


def test_k_total_gives_exactly_leaves():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    total = len(seq)
    leaves = {n.id for n in tree.nodes.values() if n.is_leaf}
    assert set(frontier_at(tree, seq, total)) == leaves


def test_sequence_is_topologically_valid():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    # a node can only be expanded once its parent is in the frontier,
    # i.e. once the parent has itself already been expanded (or is root).
    expanded_so_far: set[str] = set()
    for node_id in seq:
        node = tree.nodes[node_id]
        assert node_id == tree.root or node.parent in expanded_so_far
        expanded_so_far.add(node_id)


def test_frontier_is_monotonic():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    prev = frontier_at(tree, seq, 0)
    for k in range(1, len(seq) + 1):
        cur = frontier_at(tree, seq, k)
        # every previous frontier node is either still present, or was
        # replaced by exactly its children (never removed with nothing
        # taking its place, never collapsed back to an ancestor)
        removed = set(prev) - set(cur)
        assert len(removed) <= 1
        if removed:
            removed_id = next(iter(removed))
            assert set(tree.nodes[removed_id].children) <= set(cur)
        prev = cur


def test_k_for_z_bounds():
    assert k_for_z(0.0, 10) == 0
    assert k_for_z(1.0, 10) == 10
    assert k_for_z(0.5, 10) == 5


def test_anchor_prioritises_nearby_nodes():
    tree = _make_tree()
    # Anchor on a1: "a" branch nodes should expand before "b" branch nodes
    # when both are candidates in the frontier simultaneously.
    seq = expansion_sequence(tree, anchor_id="a1")
    assert seq[0] == "root"
    assert seq[1] == "a"  # nearer to a1 than b is


def test_find_anchor_replacement_contains_old_offset():
    tree = _make_tree()
    frontier = ["a1", "a2", "b"]  # "a" was expanded, "b" was not
    replacement = find_anchor_replacement(tree, frontier, offset=15)
    assert tree.nodes[replacement].source_span[0] <= 15 < tree.nodes[replacement].source_span[1]
    assert replacement == "a2"
