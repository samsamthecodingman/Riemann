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


# --- single-child chains ---------------------------------------------------


def test_collapse_single_child_chain_keeps_root_summary():
    from riemann.abstraction.build import collapse_single_child_chains

    # root -> d1 -> d2 -> (s1, s2 -> leaf only)
    nodes = {
        "root": _mk_node("root", 0, children=["d1"]),
        "d1": _mk_node("d1", 1, children=["d2"]),
        "d2": _mk_node("d2", 2, children=["s1", "s2"]),
        "s1": _mk_node("s1", 3, children=["l1", "l2"]),
        "s2": _mk_node("s2", 3, children=["l3"]),
        "l1": _mk_node("l1", 4, is_leaf=True),
        "l2": _mk_node("l2", 4, is_leaf=True),
        "l3": _mk_node("l3", 4, is_leaf=True),
    }
    for nid, n in nodes.items():
        n.parent = None
    for nid, n in nodes.items():
        for c in n.children:
            nodes[c].parent = nid
    nodes["root"].text = "the root summary"
    collapse_single_child_chains(nodes, "root")
    assert nodes["root"].children == ["s1", "l3"]  # s2 (one leaf child) is replaced by the leaf
    assert nodes["root"].text == "the root summary"
    assert set(nodes) == {"root", "s1", "l1", "l2", "l3"}
    assert nodes["l3"].parent == "root" and nodes["s1"].parent == "root"


@pytest.mark.parametrize("words", [400, 1500, 6000, 20000])
async def test_no_single_child_chains_and_sections_split(words):
    tree = await _build(_doc(words), tree_id=f"chain-{words}")
    for n in tree.nodes.values():
        if not n.is_leaf:
            assert len(n.children) >= 2, f"{n.id} has {len(n.children)} child(ren)"
    assert len(tree.sections) >= 2
    assert set(tree.sections) == set(tree.nodes[tree.root].children)


# --- overview ------------------------------------------------------------------


async def test_overview_built_and_validated_with_fake_summariser():
    tree = await _build(_doc(1500), tree_id="overview-fake")
    ov = tree.overview
    assert ov is not None
    assert ov.doc_title == "Title" and ov.doc_kind and ov.what_it_is.startswith("This is")
    assert 3 <= len(ov.essentials) <= 7
    leaf_ids = {i for i, n in tree.nodes.items() if n.is_leaf}
    for e in ov.essentials:
        assert e.label and e.value and set(e.cites) <= leaf_ids


async def test_overview_uses_goal_specific_essentials():
    builder = start_build("overview-exec", "Brief", _doc(1500), FakeSummariser(), objective="execute")
    await builder.task
    ov = builder.tree.overview
    assert [e.label for e in ov.essentials] == ["Due", "Deliverables", "What you need to do"]  # act-first order
    assert ov.doc_kind == "Assignment brief"


def _overview_tree():
    leaf1 = _mk_node("l1", 1, is_leaf=True)
    leaf1.text = "Due Friday 5 pm. The report is worth 25% of the unit."
    leaf2 = _mk_node("l2", 1, is_leaf=True)
    leaf2.text = "Nothing else."
    root = _mk_node("root", 0, children=["l1", "l2"])
    t = _mk_tree({"root": root, "l1": leaf1, "l2": leaf2}, "root")
    t.source_text = leaf1.text + "\n\n" + leaf2.text
    return t


def test_overview_drops_bad_items_and_invented_numbers():
    from riemann.abstraction.build import _clean_overview

    tree = _overview_tree()
    raw = {
        "doc_title": "ABC101 Report brief",
        "doc_kind": "Assignment brief",
        "what_it_is": "This is the brief for a report worth 99% of the unit.",  # 99 not in the source
        "essentials": [
            {"label": "Due", "value": "Friday 5 pm", "cites": ["l1"]},
            {"label": "Weight", "value": "25% of the unit", "cites": ["l1"]},
            {"label": "Pages", "value": "10 pages", "cites": ["l2"]},  # 10 not in cited leaf
            {"label": "Submit how", "value": "not stated", "cites": []},
            {"label": "Due", "value": "again", "cites": ["l1"]},  # duplicate label
            {"label": "Bogus cite", "value": "see the brief", "cites": ["nope"]},
            {"label": "", "value": "no label"},
            "not a dict",
        ],
    }
    ov = _clean_overview(raw, tree)
    assert ov.what_it_is == "This is an assignment brief."
    assert [e.label for e in ov.essentials] == ["Due", "Weight", "Submit how", "Bogus cite"]
    assert ov.essentials[3].cites == []  # unknown leaf ids are dropped
    assert _clean_overview({"doc_title": "", "doc_kind": "x"}, tree) is None
    assert _clean_overview("nope", tree) is None


def test_essential_value_is_capped_by_validator_not_clamped():
    from riemann.abstraction.build import ESSENTIAL_VALUE_MAX_WORDS, _clean_essentials

    long_value = " ".join(["word"] * 80)
    out = _clean_essentials([{"label": "Due", "value": long_value, "cites": []}], {}, set())
    assert len(out) == 1
    assert len(out[0].value.split()) == ESSENTIAL_VALUE_MAX_WORDS == 30


def test_over_long_titles_do_not_end_on_a_dangling_word_or_number():
    from riemann.abstraction.build import _truncate_title

    assert _truncate_title("Submit as one PDF by 5 pm, 14 November 2025") == "Submit as one PDF by 5 pm"
    assert _truncate_title("Marks are split across the five criteria and the of") == "Marks are split across the five criteria"
    assert _truncate_title("Short title here") == "Short title here"
    assert _truncate_title("one two three four five six seven eight nine") == "one two three four five six seven eight"


def test_numbers_must_match_whole_numbers_not_substrings():
    from riemann.abstraction.build import _number_in_source as ok

    src = "worth 25% of the mark; due in 2025; scores of 10.5 and 1,000 words".lower()
    assert ok("25", src) and ok("2025", src) and ok("10.5", src) and ok("1000", src) and ok("1,000", src)
    assert not ok("5", src)  # inside 25 and 2025
    assert not ok("20", src)  # inside 2025
    assert not ok("0.5", src)  # inside 10.5
    assert not ok("100", src)  # inside 1,000
    assert ok("2025.", src)  # sentence punctuation is ignored
    assert ok("billion", "about a billion people") and not ok("million", "millions of people")


def test_a_small_number_may_be_a_word_in_the_source_but_not_a_different_number():
    from riemann.abstraction.build import _number_in_source as ok

    assert ok("3", "three offices took part") and ok("12", "twelve pages") and ok("40", "forty marks") and ok("0", "zero errors")
    assert not ok("13", "twelve pages") and not ok("4", "three offices") and not ok("21", "twenty one") and not ok("30", "thirteen")
    assert not ok("3", "the threefold increase")  # a word, not part of one


def test_essential_with_a_number_only_inside_a_longer_number_is_dropped():
    from riemann.abstraction.build import _clean_essentials
    from riemann.abstraction.model import Node

    leaf = Node(id="l1", depth=0, text="This task is worth 25% of your final mark.", source_span=(0, 40), is_leaf=True, words=9)
    out = _clean_essentials(
        [{"label": "Weight", "value": "5% of your mark", "cites": ["l1"]}, {"label": "Weight2", "value": "25% of your mark", "cites": ["l1"]}],
        {"l1": leaf},
        {"l1"},
    )
    assert [e.label for e in out] == ["Weight2"]


def test_a_lone_title_heading_does_not_hide_the_section_boundaries():
    from riemann.abstraction.build import section_boundary_keys

    title = ("Meeting",)
    paths = [title, title + ("1. Data",), title + ("1. Data",), title + ("2. Budget",), title + ("2. Budget", "Quotes"), title + ("Actions",)]
    keys = section_boundary_keys(paths)
    assert keys[0] == title  # the preamble before the first section
    assert keys[1] == keys[2] == title + ("1. Data",)
    assert keys[3] == keys[4] == title + ("2. Budget",)  # a ### inside a section is not a boundary
    assert keys[5] == title + ("Actions",)
    assert len({keys[0], keys[1], keys[3], keys[5]}) == 4


def test_section_boundary_keys_keep_the_old_behaviour_without_a_shared_title():
    from riemann.abstraction.build import section_boundary_keys

    paths = [(), ("A",), ("A", "x"), ("B",), ("B", "y")]
    assert section_boundary_keys(paths) == [None, ("A",), ("A",), ("B",), ("B",)]
    assert section_boundary_keys([("Only",), ("Only",)]) == [("Only",), ("Only",)]
    assert section_boundary_keys([]) == []


async def test_title_plus_h2_sections_become_separate_sections_in_a_built_tree():
    text = "# Notes\n\n" + "\n\n".join(f"## Topic {i}\n\n" + ("Words about topic %d go here. " % i) * 30 for i in range(4))
    builder = start_build("h2doc", "Notes", text, FakeSummariser())
    await builder.task
    tree = builder.tree
    assert len(tree.sections) >= 4, len(tree.sections)


# --- pass-through levels in trees read from the cache ----------------------------


def _chain_tree():
    from tests.test_frontier import _skim_tree

    return _skim_tree(True)  # root -> A -> B -> two sections of three paragraphs


def test_a_cached_tree_with_a_pass_through_chain_is_collapsed_when_read(tmp_path, monkeypatch):
    """A tree from before chains were collapsed (or backfilled from one into the current
    namespace, which is how Sam's brief kept its three-level chain under schema7) opens
    without the chain, depths and sections following from the new shape. The file is untouched."""
    from riemann.abstraction import cache

    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    tree = _chain_tree()
    assert [tree.nodes[n].depth for n in ("root", "A", "B", "S1")] == [0, 1, 2, 3]
    cache.save_tree(tree)
    on_disk = cache.path_for(tree.id).read_text(encoding="utf-8")

    loaded = cache.load_tree(tree.id)
    assert loaded.nodes[loaded.root].children == ["S1", "S2"]
    assert set(loaded.nodes) == {"root", "S1", "S2", "S1a", "S1b", "S1c", "S2a", "S2b", "S2c"}
    assert loaded.nodes["S1"].parent == "root" and loaded.nodes["S1"].depth == 1 and loaded.nodes["S1a"].depth == 2
    assert loaded.max_depth == 2
    assert loaded.sections == ["S1", "S2"]
    assert loaded.nodes["root"].text == tree.nodes["root"].text  # the root keeps its own summary
    for n in loaded.nodes.values():
        if not n.is_leaf:
            assert len(n.children) >= 2
    assert cache.path_for(tree.id).read_text(encoding="utf-8") == on_disk
    # a tree that has no chain comes back exactly as saved
    again = cache.load_tree(tree.id)
    assert again.model_dump() == loaded.model_dump()


def test_the_api_serves_a_chained_tree_collapsed_and_it_still_zooms(tmp_path, monkeypatch):
    import asyncio

    from httpx import ASGITransport, AsyncClient

    import riemann.server as server
    from riemann.abstraction import cache
    from riemann.abstraction.frontier import expansion_sequence, frontier_at
    from riemann.abstraction.model import Tree

    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    cache.save_tree(_chain_tree())

    async def go():
        async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
            return (await c.get("/api/tree/t")).json()

    body = asyncio.run(go())
    tree = Tree.model_validate(body)
    assert tree.nodes[tree.root].children == ["S1", "S2"]
    seq = expansion_sequence(tree)
    assert sorted(frontier_at(tree, seq, len(seq))) == sorted(n for n, v in tree.nodes.items() if v.is_leaf)


def test_remove_pass_through_levels_takes_the_chain_below_the_root():
    """The levels a lone node gets from being summarised again and again (root over one node over
    one node) go, and the root keeps its own summary."""
    from riemann.abstraction.build import has_pass_through_level, remove_pass_through_levels

    tree = _chain_tree()
    assert has_pass_through_level(tree)
    remove_pass_through_levels(tree)
    assert not has_pass_through_level(tree)
    assert tree.nodes[tree.root].children == ["S1", "S2"]
