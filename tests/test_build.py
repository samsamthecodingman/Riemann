import pytest

from riemann.abstraction.build import GIST_WORDS, start_build
from riemann.abstraction.chunk import word_count
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
