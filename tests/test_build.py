import pytest

from riemann.abstraction.build import (
    GIST_WORDS,
    HOOK_MAX_WORDS,
    KEY_POINT_MAX_WORDS,
    KEY_POINTS_MAX_ITEMS,
    TITLE_MAX_WORDS,
    _clean_child_short_titles,
    _clean_child_titles,
    _clean_short_title,
    _clean_hook,
    _clean_key_points,
    _clean_title,
    _validate_key_fact,
    compute_sections,
    start_build,
)
from riemann.abstraction.chunk import word_count
from riemann.abstraction.model import Node, Tree
from riemann.abstraction.summarise import FakeSummariser


def _paragraph(n_words: int, seed: int = 0) -> str:
    return " ".join(f"w{seed}_{i}" for i in range(n_words))


def _doc(total_words: int, sections: int = 4) -> str:
    per_section = max(10, total_words // sections)
    parts = []
    for s in range(sections):
        parts.append(f"# Section {s}")
        parts.append("")
        parts.append(_paragraph(per_section, seed=s))
        parts.append("")
    return "\n".join(parts)


async def _build(text: str, tree_id: str = "t"):
    builder = start_build(tree_id, "Title", text, FakeSummariser())
    await builder.task
    return builder.tree


@pytest.mark.parametrize(
    "words,max_expected",
    [
        (150, 2),
        (1500, 5),
        (20000, 7),
    ],
)
async def test_depth_adapts_to_source_size(words, max_expected):
    text = _doc(words, sections=max(1, words // 400))
    tree = await _build(text, tree_id=f"depth-{words}")
    assert tree.status == "done"
    assert tree.max_depth <= max_expected


async def test_root_is_short():
    text = _doc(1500)
    tree = await _build(text, tree_id="root-short")
    root = tree.nodes[tree.root]
    assert word_count(root.text) <= round(GIST_WORDS * 1.35) + 1


async def test_cites_subset_of_leaves_under_node():
    text = _doc(2000)
    tree = await _build(text, tree_id="cites")
    leaf_ids = {n.id for n in tree.nodes.values() if n.is_leaf}

    def leaves_under(node_id):
        node = tree.nodes[node_id]
        if node.is_leaf:
            return {node_id}
        out = set()
        for c in node.children:
            out |= leaves_under(c)
        return out

    for node in tree.nodes.values():
        if node.is_leaf:
            continue
        under = leaves_under(node.id)
        assert under <= leaf_ids
        assert set(node.cites) <= under


async def test_source_spans_nest_within_parent():
    text = _doc(1500)
    tree = await _build(text, tree_id="spans")
    for node in tree.nodes.values():
        for child_id in node.children:
            child = tree.nodes[child_id]
            assert node.source_span[0] <= child.source_span[0]
            assert child.source_span[1] <= node.source_span[1]


async def test_tree_is_ragged_for_uneven_sections():
    # One tiny section (single short leaf, collapses/carries up) next to a
    # much longer one should produce leaves at different depths.
    text = (
        "# Tiny\n\nJust a few words here.\n\n"
        "# Big\n\n" + _paragraph(2000, seed=9) + "\n"
    )
    tree = await _build(text, tree_id="ragged")
    leaf_depths = {n.depth for n in tree.nodes.values() if n.is_leaf}
    assert len(leaf_depths) > 1


async def test_provisional_root_before_any_level_event():
    text = _doc(1500)
    builder_tree_id = "event-order"
    from riemann.abstraction.build import start_build as sb

    builder = sb(builder_tree_id, "Title", text, FakeSummariser())
    await builder.task
    names = [name for name, _ in builder.history]
    assert "leaves" in names
    assert "provisional_root" in names
    assert "done" in names
    prov_index = names.index("provisional_root")
    level_indices = [i for i, n in enumerate(names) if n == "level"]
    assert all(prov_index < i for i in level_indices)
    # leaves must come before provisional_root
    assert names.index("leaves") < prov_index


async def test_tiny_doc_gives_single_leaf_root_no_summary():
    text = "A very small document with barely any words in it at all."
    tree = await _build(text, tree_id="tiny")
    assert len(tree.nodes) == 1
    assert tree.nodes[tree.root].is_leaf is True
    assert tree.max_depth == 0


def _mk_node(id_, depth, children=(), is_leaf=False, text="x", **kw) -> Node:
    return Node(
        id=id_,
        depth=depth,
        text=text,
        words=word_count(text),
        children=list(children),
        is_leaf=is_leaf,
        source_span=(0, 1),
        **kw,
    )


def _mk_tree(nodes: dict, root: str) -> Tree:
    return Tree(
        id="t",
        title="T",
        source_text="src",
        source_words=1,
        root=root,
        nodes=nodes,
        max_depth=max(n.depth for n in nodes.values()),
        status="done",
    )


# --- sections computation ---------------------------------------------


def test_sections_first_branching_depth():
    # root (depth 0) -> two section nodes (depth 1) -> leaves (depth 2)
    leaf_a = _mk_node("leaf_a", 2, is_leaf=True)
    leaf_b = _mk_node("leaf_b", 2, is_leaf=True)
    leaf_c = _mk_node("leaf_c", 2, is_leaf=True)
    sec1 = _mk_node("sec1", 1, children=["leaf_a"])
    sec2 = _mk_node("sec2", 1, children=["leaf_b", "leaf_c"])
    root = _mk_node("root", 0, children=["sec1", "sec2"])
    tree = _mk_tree({"root": root, "sec1": sec1, "sec2": sec2, "leaf_a": leaf_a, "leaf_b": leaf_b, "leaf_c": leaf_c}, "root")
    assert compute_sections(tree) == ["sec1", "sec2"]


def test_sections_empty_for_chained_root():
    # root -> mid -> leaf, single child at every depth: no depth ever has >=2 nodes.
    leaf = _mk_node("leaf", 2, is_leaf=True)
    mid = _mk_node("mid", 1, children=["leaf"])
    root = _mk_node("root", 0, children=["mid"])
    tree = _mk_tree({"root": root, "mid": mid, "leaf": leaf}, "root")
    assert compute_sections(tree) == []


def test_sections_empty_for_single_leaf():
    leaf = _mk_node("leaf", 0, is_leaf=True)
    tree = _mk_tree({"leaf": leaf}, "leaf")
    assert compute_sections(tree) == []


async def test_sections_populated_on_real_build():
    text = _doc(1500)
    tree = await _build(text, tree_id="sections-real")
    assert tree.status == "done"
    if len(tree.nodes) > 1:
        assert isinstance(tree.sections, list)
        for node_id in tree.sections:
            assert node_id in tree.nodes


# --- title/hook/key_points propagate through a real build --------------


async def test_titles_and_hooks_populated_by_fake_summariser():
    text = _doc(1500)
    tree = await _build(text, tree_id="titles")
    internal = [n for n in tree.nodes.values() if not n.is_leaf]
    assert internal
    assert any(n.title for n in internal)
    assert any(n.hook for n in internal)
    leaves = [n for n in tree.nodes.values() if n.is_leaf]
    if len(tree.nodes) > 1:
        assert any(n.title for n in leaves)


# --- key_fact deterministic validation ----------------------------------


def test_key_fact_kept_when_number_in_cited_leaf_text():
    nodes = {"leaf1": _mk_node("leaf1", 1, is_leaf=True, text="Usage grew from hundreds to over 2 billion users by 1995.")}
    raw = {"big": "2 billion users", "detail": "up from hundreds in 1995", "cites": ["leaf1"]}
    fact = _validate_key_fact(raw, nodes, ["leaf1"])
    assert fact is not None
    assert fact.big == "2 billion users"
    assert fact.cites == ["leaf1"]


def test_key_fact_dropped_when_number_not_in_cited_leaf_text():
    nodes = {"leaf1": _mk_node("leaf1", 1, is_leaf=True, text="Usage grew steadily over the decade.")}
    raw = {"big": "2 billion users", "detail": "a huge jump", "cites": ["leaf1"]}
    fact = _validate_key_fact(raw, nodes, ["leaf1"])
    assert fact is None


def test_key_fact_none_passthrough():
    assert _validate_key_fact(None, {}, []) is None


# --- word-limit enforcement ----------------------------------------------


def test_title_truncated_not_retried():
    long_title = " ".join(f"word{i}" for i in range(20))
    cleaned = _clean_title(long_title)
    assert cleaned is not None
    assert len(cleaned.split()) == TITLE_MAX_WORDS


def test_hook_truncated_to_limit():
    long_hook = " ".join(f"word{i}" for i in range(40))
    cleaned = _clean_hook(long_hook)
    assert cleaned is not None
    assert len(cleaned.split()) == HOOK_MAX_WORDS


def test_key_points_truncated_items_and_count():
    points = [" ".join(f"w{i}" for i in range(30)) for _ in range(10)]
    cleaned = _clean_key_points(points)
    assert len(cleaned) == KEY_POINTS_MAX_ITEMS
    assert all(len(p.split()) == KEY_POINT_MAX_WORDS for p in cleaned)


def test_child_titles_keys_must_be_real_child_ids():
    raw = {"child_a": "A Real Child", "not_a_child": "Should Be Dropped"}
    cleaned = _clean_child_titles(raw, ["child_a", "child_b"])
    assert cleaned == {"child_a": "A Real Child"}


def test_short_title_limits_drop_not_truncate():
    assert _clean_short_title("Time windows") == "Time windows"
    assert _clean_short_title("one two three four") is None
    assert _clean_short_title("Extraordinarily-long-single-word") is None
    assert _clean_short_title("  ") is None
    assert _clean_short_title(None) is None
    cleaned = _clean_child_short_titles({"a": "Fine", "zz": "Ghost", "b": "far too many words here"}, ["a", "b"])
    assert cleaned == {"a": "Fine"}


async def test_short_titles_populated_and_valid():
    tree = await _build(_doc(1500), tree_id="shorttitles")
    with_short = [n for n in tree.nodes.values() if n.short_title]
    assert with_short
    for n in with_short:
        assert len(n.short_title.split()) <= 3 and len(n.short_title) <= 24


# --- old-schema JSON still loads ------------------------------------------


def test_old_schema_json_still_loads():
    # A tree dumped by the pre-v2 schema: no sections/title/hook/etc fields.
    old_json = """
    {
        "id": "old1",
        "title": "Old Tree",
        "source_text": "hello world",
        "source_words": 2,
        "root": "n1",
        "nodes": {
            "n1": {
                "id": "n1",
                "depth": 0,
                "text": "hello world",
                "words": 2,
                "children": [],
                "parent": null,
                "is_leaf": true,
                "source_span": [0, 11],
                "cites": [],
                "importance": 1.0,
                "atomic": false
            }
        },
        "max_depth": 0,
        "status": "done",
        "provisional_root": false
    }
    """
    tree = Tree.model_validate_json(old_json)
    assert tree.sections == []
    node = tree.nodes["n1"]
    assert node.title is None
    assert node.hook is None
    assert node.key_points == []
    assert node.key_fact is None
    assert node.steps == []
