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


def test_sequence_tokens_are_reachable_and_unique():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    assert len(seq) == len(set(seq))
    for token in seq:
        assert (token[1:] if token.startswith("~") else token) in tree.nodes
        assert not tree.nodes[token.lstrip("~")].is_leaf


def test_frontier_is_monotonic():
    tree = _make_tree()
    seq = expansion_sequence(tree)
    prev = frontier_at(tree, seq, 0)
    for k in range(1, len(seq) + 1):
        cur = frontier_at(tree, seq, k)
        # every previous frontier node is either still present, or was
        # replaced by exactly its children (never removed with nothing
        # taking its place, never collapsed back to an ancestor)
        # (a merged step may open several levels at once, so "replaced by
        # descendants" rather than "by exactly its children")
        for nid in set(prev) - set(cur):
            assert set(_descendants(tree, nid)) & set(cur)
        prev = cur


def _descendants(tree, nid):
    for c in tree.nodes[nid].children:
        yield c
        yield from _descendants(tree, c)


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
    # nearer to a1 than b is, so a opens first (its prose step adds nothing
    # visible here -- no bullets -- so it is merged into the expansion)
    assert seq.index("a") < seq.index("b")


def test_find_anchor_replacement_contains_old_offset():
    tree = _make_tree()
    frontier = ["a1", "a2", "b"]  # "a" was expanded, "b" was not
    replacement = find_anchor_replacement(tree, frontier, offset=15)
    assert tree.nodes[replacement].source_span[0] <= 15 < tree.nodes[replacement].source_span[1]
    assert replacement == "a2"


def _skim_tree(chain: bool) -> Tree:
    """A document shaped like the one that prompted the visible-growth rule:
    root -> A (one child) -> B -> two sections with paragraphs (chain=True), or
    the same content with the single-child levels collapsed (chain=False)."""
    def words(n, tag):
        return " ".join(f"{tag}{i}" for i in range(n))

    nodes: dict[str, Node] = {}

    def add(nid, parent, depth, n_words, children, span, leaf=False, skim=True):
        nodes[nid] = Node(
            id=nid, depth=depth, text=words(n_words, nid), words=n_words, children=children,
            parent=parent, is_leaf=leaf, source_span=span, importance=0.5,
            title=None if leaf else f"Title of {nid}",
            key_points=[] if leaf or not skim else [words(10, nid + "k"), words(10, nid + "m")],
            hook=None if leaf else words(8, nid + "h"),
        )

    if chain:
        add("root", None, 0, 20, ["A"], (0, 400))
        add("A", "root", 1, 44, ["B"], (0, 400))
        add("B", "A", 2, 119, ["S1", "S2"], (0, 400))
        sec_parent, sec_depth = "B", 3
    else:
        add("root", None, 0, 20, ["S1", "S2"], (0, 400))
        sec_parent, sec_depth = "root", 1
    for i, sid in enumerate(("S1", "S2")):
        lo = i * 200
        add(sid, sec_parent, sec_depth, 90, [sid + "a", sid + "b", sid + "c"], (lo, lo + 200))
        for j, suffix in enumerate("abc"):
            add(sid + suffix, sid, sec_depth + 1, 70, [], (lo + j * 60, lo + j * 60 + 60), leaf=True)
    return Tree(id="t", title="T", source_text="x" * 400, source_words=420, root="root",
                nodes=nodes, max_depth=4, status="done")


def _page_words(tree, seq, k):
    from riemann.abstraction.frontier import prose_at, visible_words
    return visible_words(tree, frontier_at(tree, seq, k), prose_at(seq, k))


@pytest.mark.parametrize("chain", [True, False])
def test_every_step_adds_visible_words(chain):
    """The zoom-step rule: each step adds at least min(15%, 25 words) of
    visible text, so a step never just rewords the page. (Only the last step
    of a sequence may fall short, if nothing was left to merge it with.)"""
    from riemann.abstraction.frontier import GAIN_FRACTION, GAIN_WORDS

    tree = _skim_tree(chain)
    for anchor in ("root", "S1", "S2b") if not chain else ("root", "B", "S1a"):
        seq = expansion_sequence(tree, anchor)
        counts = [_page_words(tree, seq, k) for k in range(len(seq) + 1)]
        assert counts == sorted(set(counts)), f"visible words not strictly increasing: {counts}"
        for before, after in zip(counts, counts[1:]):
            assert after - before >= min(GAIN_FRACTION * before, GAIN_WORDS) - 1e-9


def test_single_child_chain_is_merged_through():
    tree = _skim_tree(chain=True)
    seq = expansion_sequence(tree)
    # root and A are single-child levels: no step may show A, so the first
    # step lands on B, the first level that actually splits.
    assert frontier_at(tree, seq, 1) == ["B"]
    for k in range(len(seq) + 1):
        assert not {"root", "A"} & set(frontier_at(tree, seq, k)) or k == 0
    assert set(frontier_at(tree, seq, len(seq))) == {n for n in tree.nodes if tree.nodes[n].is_leaf}


def test_fixture_visible_words_strictly_increase():
    import json
    from pathlib import Path

    tree = Tree.model_validate(json.loads((Path(__file__).resolve().parent.parent / "web" / "dev-fixture.json").read_text()))
    for anchor in tree.nodes:
        seq = expansion_sequence(tree, anchor)
        counts = [_page_words(tree, seq, k) for k in range(len(seq) + 1)]
        assert counts == sorted(set(counts)), f"anchor {anchor}: {counts}"


def test_new_internal_children_start_as_skim():
    from riemann.abstraction.frontier import prose_at

    tree = _make_tree()
    seq = expansion_sequence(tree)
    k = seq.index(tree.root) + 1
    internal_children = [c for c in tree.nodes[tree.root].children if not tree.nodes[c].is_leaf]
    assert internal_children
    assert not (set(internal_children) & prose_at(seq, k))
