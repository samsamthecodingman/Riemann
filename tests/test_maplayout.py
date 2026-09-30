"""web/maplayout.js is the pure layout behind the spatial view. Run it under
Node against the dev fixture (and a synthetic ragged tree) and check its
contract: deterministic, nested, non-overlapping, reading order, sized by
source length."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "web" / "dev-fixture.json"
LAYOUT_JS = ROOT / "web" / "maplayout.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

NODE_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const tree = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const sizes = JSON.parse(process.argv[3]);
const density = process.argv[4] || undefined;
const out = sizes.map(([W, H]) => {
  const m = window.MapLayout.layout(tree, W, H, { density });
  return Object.fromEntries(m);
});
const words = window.MapLayout.wordsInSource(tree);
process.stdout.write(JSON.stringify({ layouts: out, words: Object.fromEntries(words) }));
"""

EPS = 0.01


def run_layout(tree_path: Path, sizes, density=None):
    res = subprocess.run(
        ["node", "-e", NODE_SCRIPT, str(LAYOUT_JS), str(tree_path), json.dumps(sizes)] + ([density] if density else []),
        capture_output=True, text=True, check=True,
    )
    return json.loads(res.stdout)


def synthetic_tree(path: Path) -> dict:
    """A ragged 3-level tree: 5 sections of very different length, one of
    them a bare leaf, one deep, some with tiny parts."""
    nodes = {}

    def leaf(i, words):
        nodes[i] = dict(id=i, depth=3, text=f"leaf {i}", words=words, children=[], parent=None, is_leaf=True,
                        source_span=[0, words * 6], title=f"Leaf {i}")

    def internal(i, kids, title):
        nodes[i] = dict(id=i, depth=2, text=title, words=20, children=kids, parent=None, is_leaf=False,
                        source_span=[0, 100], title=title)
        for k in kids:
            nodes[k]["parent"] = i

    for i, w in enumerate([300, 40, 25, 500, 90, 60, 700, 30, 30, 30, 220, 15]):
        leaf(f"l{i}", w)
    internal("a", ["l0", "l1", "l2"], "Alpha section on something fairly long to wrap a bit")
    internal("b", ["l3"], "Beta")
    internal("c1", ["l4", "l5"], "Gamma part one")
    internal("c", ["c1", "l6"], "Gamma")
    internal("d", ["l7", "l8", "l9"], "Delta")
    nodes["e"] = dict(nodes["l10"], id="e")
    internal("root", ["a", "b", "c", "d", "e"], "Root")
    nodes["l10"]["parent"] = None
    del nodes["l10"]
    nodes["e"]["parent"] = "root"
    nodes["l11"]["parent"] = None
    tree = dict(id="syn", title="syn", source_text="", source_words=2000, root="root", nodes=nodes,
                sections=["a", "b", "c", "d", "e"])
    del tree["nodes"]["l11"]
    path.write_text(json.dumps(tree))
    return tree


@pytest.fixture(scope="module")
def trees(tmp_path_factory):
    syn_path = tmp_path_factory.mktemp("maplayout") / "syn.json"
    syn = synthetic_tree(syn_path)
    return [(json.loads(FIXTURE.read_text()), FIXTURE), (syn, syn_path)]


SIZES = [[580, 688], [1160, 1376], [3480, 4128], [900, 300], [300, 900]]


def contains(outer, inner):
    return (inner["x"] >= outer["x"] - EPS and inner["y"] >= outer["y"] - EPS
            and inner["x"] + inner["w"] <= outer["x"] + outer["w"] + EPS
            and inner["y"] + inner["h"] <= outer["y"] + outer["h"] + EPS)


def overlaps(a, b):
    return (a["x"] < b["x"] + b["w"] - EPS and b["x"] < a["x"] + a["w"] - EPS
            and a["y"] < b["y"] + b["h"] - EPS and b["y"] < a["y"] + a["h"] - EPS)


def test_deterministic(trees):
    for tree, path in trees:
        a = run_layout(path, SIZES)
        b = run_layout(path, SIZES)
        assert a == b


def test_every_node_from_the_sections_down_is_placed_or_hidden_by_a_small_parent(trees):
    for tree, path in trees:
        layouts = run_layout(path, [[580, 688]])["layouts"][0]
        for sec in tree["sections"]:
            assert sec in layouts
        # bigger canvas places at least as many nodes, and at a huge one every node
        big = run_layout(path, [[6000, 7000]])["layouts"][0]
        below = set()

        def walk(i):
            below.add(i)
            for c in tree["nodes"][i]["children"]:
                walk(c)

        for sec in tree["sections"]:
            walk(sec)
        assert below <= set(big)
        assert len(big) >= len(layouts)


def test_children_inside_parent_and_siblings_do_not_overlap(trees):
    for tree, path in trees:
        for layouts in run_layout(path, SIZES)["layouts"]:
            secs = [layouts[s] for s in tree["sections"] if s in layouts]
            for i, a in enumerate(secs):
                for b in secs[i + 1:]:
                    assert not overlaps(a, b)
            for nid, r in layouts.items():
                kids = [layouts[c] for c in tree["nodes"][nid]["children"] if c in layouts]
                for i, k in enumerate(kids):
                    assert contains(r, k), f"{nid} child escapes"
                    assert k["y"] >= r["y"] + (0 if r["side"] else r["headerH"]) - EPS
                    if r["side"]:
                        assert k["x"] >= r["x"] + min(200, 0.35 * r["w"]) - EPS
                    for other in kids[i + 1:]:
                        assert not overlaps(k, other)


def test_reading_order_is_row_major_within_strips(trees):
    for tree, path in trees:
        for layouts in run_layout(path, SIZES)["layouts"]:
            groups = [[s for s in tree["sections"] if s in layouts]]
            for nid, r in layouts.items():
                kids = [c for c in tree["nodes"][nid]["children"] if c in layouts]
                if kids:
                    groups.append(kids)
            for ids in groups:
                cells = [layouts[i] for i in ids]
                if len(cells) < 2:
                    continue
                # orientation follows the container; recover it from the first strip
                rows = len({round(c["y"], 1) for c in cells}) < len(cells) or cells[0]["y"] == cells[1]["y"]
                cols = len({round(c["x"], 1) for c in cells}) < len(cells) or cells[0]["x"] == cells[1]["x"]
                for a, b in zip(cells, cells[1:]):
                    if rows and not cols:
                        assert b["y"] >= a["y"] + a["h"] - 6.5 or (b["y"] - a["y"] < 1 and b["x"] >= a["x"] + a["w"] - 1)
                    elif cols and not rows:
                        assert b["x"] >= a["x"] + a["w"] - 6.5 or (b["x"] - a["x"] < 1 and b["y"] >= a["y"] + a["h"] - 1)
                    else:
                        # single strip either way, or a mixed grid: strips advance monotonically
                        assert (b["y"] >= a["y"] - 1 and b["x"] >= a["x"] - 1) or b["y"] >= a["y"] + a["h"] - 6.5 or b["x"] >= a["x"] + a["w"] - 6.5


def test_sizes_roughly_proportional_to_weight(trees):
    for tree, path in trees:
        res = run_layout(path, [[3480, 4128]])
        layouts, words = res["layouts"][0], res["words"]
        groups = [[s for s in tree["sections"] if s in layouts]]
        for nid in layouts:
            kids = [c for c in tree["nodes"][nid]["children"] if c in layouts]
            if kids:
                groups.append(kids)
        for ids in groups:
            total = sum(words[i] for i in ids)
            # only parts above the 6% floor follow their weight; the floor lifts the rest
            big = [i for i in ids if words[i] >= 0.09 * total]
            if len(big) < 2:
                continue
            dens = [layouts[i]["w"] * layouts[i]["h"] / words[i] for i in big]
            mean = sum(dens) / len(dens)
            for d in dens:
                assert abs(d - mean) / mean < 0.4, (ids, dens)


def test_tiny_containers_leave_children_unplaced(trees):
    tree, path = trees[0]
    layouts = run_layout(path, [[60, 60]])["layouts"][0]
    for sec in tree["sections"]:
        r = layouts[sec]
        assert r["headerH"] > 0 or tree["nodes"][sec]["is_leaf"]
        assert all(c not in layouts for c in tree["nodes"][sec]["children"])


def test_compact_density_is_deterministic_and_nested(trees):
    for tree, path in trees:
        a = run_layout(path, SIZES, "compact")
        assert a == run_layout(path, SIZES, "compact")
        for layouts in a["layouts"]:
            for nid, r in layouts.items():
                kids = [layouts[c] for c in tree["nodes"][nid]["children"] if c in layouts]
                for i, k in enumerate(kids):
                    assert contains(r, k)
                    for other in kids[i + 1:]:
                        assert not overlaps(k, other)


def test_compact_section_header_reserves_numeral_and_at_most_two_lines(trees):
    for tree, path in trees:
        layouts = run_layout(path, [[1160, 1376], [300, 900]], "compact")["layouts"]
        for lay in layouts:
            for sec in tree["sections"]:
                r = lay[sec]
                if not r["headerH"]:
                    continue
                one = 8 + 22 + 4 + 17 + 8
                two = 8 + 22 + 4 + 2 * 17 + 8
                assert one - 0.01 <= r["headerH"] <= two + 0.01, (sec, r["headerH"])


def test_compact_headers_are_smaller_than_full(trees):
    tree, path = trees[0]
    full = run_layout(path, [[1160, 1376]])["layouts"][0]
    compact = run_layout(path, [[1160, 1376]], "compact")["layouts"][0]
    for sec in tree["sections"]:
        assert compact[sec]["headerH"] < full[sec]["headerH"]


KEY_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const titles = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(titles.map((t) => window.MapLayout.keyTitle({ title: t }, t))));
"""


def test_key_title_heuristic_and_short_title_preference():
    titles = [
        "How attention works in the ADHD brain today",
        "Why the delay aversion shapes design",
        "Fidgeting, COGA guidance and thin HCI evidence",
        "Medication windows",
        "The cost of context switching between tasks",
        "Weak constructs and strong claims in research",
    ]
    res = subprocess.run(["node", "-e", KEY_SCRIPT, str(LAYOUT_JS), json.dumps(titles)],
                         capture_output=True, text=True, check=True)
    keys = json.loads(res.stdout)
    assert keys[0] == "Attention works"
    assert keys[1] == "Delay aversion shapes design"
    for k, t in zip(keys, titles):
        assert 0 < len(k.split()) <= 5
        assert k.split()[-1].lower() not in {"and", "of", "the", "to", "in", "for"}
        assert not k.lower().startswith(("how ", "why ", "the "))
    assert keys[3] == "Medication windows"
    # a "Noun and Noun" pair is kept whole when it fits in 5 words
    assert keys[2] == "Fidgeting, COGA guidance and thin"
    assert keys[5] == "Weak constructs and strong"


def test_key_title_prefers_short_title():
    script = KEY_SCRIPT.replace("{ title: t }", "{ title: t, short_title: 'Delay aversion' }")
    res = subprocess.run(["node", "-e", script, str(LAYOUT_JS), json.dumps(["Some very long title that goes on"])],
                         capture_output=True, text=True, check=True)
    assert json.loads(res.stdout) == ["Delay aversion"]
