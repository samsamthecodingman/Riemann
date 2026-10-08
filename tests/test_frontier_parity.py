"""The dial's expansion order is computed in the browser (web/frontier.js) and
mirrored in Python (riemann/abstraction/frontier.py) for tests. This runs the
real JS under Node against the dev fixture and checks both agree for every
possible anchor, so the two implementations can't drift apart silently."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from riemann.abstraction.frontier import expansion_sequence
from riemann.abstraction.model import Tree

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "web" / "dev-fixture.json"

NODE_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const tree = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const id of Object.keys(tree.nodes)) out[id] = window.Frontier.buildExpansionSequence(tree, id);
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_and_python_expansion_orders_match():
    raw = json.loads(FIXTURE.read_text())
    tree = Tree.model_validate(raw)
    js = json.loads(subprocess.run(
        ["node", "-e", NODE_SCRIPT, str(ROOT / "web" / "frontier.js"), str(FIXTURE)],
        capture_output=True, text=True, check=True,
    ).stdout)
    for anchor in tree.nodes:
        assert js[anchor] == expansion_sequence(tree, anchor), f"order differs for anchor {anchor}"


KEEP_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const tree = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const cases = JSON.parse(process.argv[3]);
const out = cases.map(([anchor, keep]) => window.Frontier.buildExpansionSequence(tree, anchor, new Set(keep)));
process.stdout.write(JSON.stringify(out));
"""


def _keep_for(tree, frontier, prose):
    """The keep set web/app.js builds for a page: every expanded ancestor of
    the frontier, plus "~id" for each internal passage shown as prose."""
    keep = set()
    on_page = set(frontier)
    for nid in frontier:
        p = tree.nodes[nid].parent
        while p is not None and p not in keep:
            keep.add(p)
            p = tree.nodes[p].parent
    keep |= {"~" + n for n in prose if n in on_page and n != tree.root and not tree.nodes[n].is_leaf}
    return keep


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_reanchoring_keeps_the_current_page_and_matches_js():
    """Re-anchoring mid-zoom must not reshuffle the page: with the page's
    applied tokens kept first, the page is unchanged at k == len(keep), and
    JS must agree with Python."""
    from riemann.abstraction.frontier import frontier_at, prose_at

    tree = Tree.model_validate(json.loads(FIXTURE.read_text()))
    ids = sorted(tree.nodes)
    cases = []
    for old_anchor in ids[::3]:
        old_seq = expansion_sequence(tree, old_anchor)
        for k in range(0, len(old_seq) + 1):
            frontier = frontier_at(tree, old_seq, k)
            prose = prose_at(old_seq, k)
            keep = _keep_for(tree, frontier, prose)
            on_page = set(frontier)
            for new_anchor in ids[1::4]:
                seq = expansion_sequence(tree, new_anchor, keep_expanded=keep)
                assert frontier_at(tree, seq, len(keep)) == frontier
                assert {n for n in prose_at(seq, len(keep)) if n in on_page} == {n for n in prose if n in on_page}
                cases.append((new_anchor, sorted(keep), seq))

    js = json.loads(subprocess.run(
        ["node", "-e", KEEP_SCRIPT, str(ROOT / "web" / "frontier.js"), str(FIXTURE),
         json.dumps([[a, k] for a, k, _ in cases])],
        capture_output=True, text=True, check=True,
    ).stdout)
    for (anchor, keep, py_seq), js_seq in zip(cases, js):
        assert js_seq == py_seq, f"order differs for anchor {anchor}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("chain", [True, False])
def test_js_matches_python_on_merged_steps(tmp_path, chain):
    """The merge rule (single-child chains, steps that add too little) must agree
    between the two implementations on a tree shaped like the one that prompted it."""
    from tests.test_frontier import _skim_tree

    tree = _skim_tree(chain)
    path = tmp_path / "tree.json"
    path.write_text(tree.model_dump_json())
    js = json.loads(subprocess.run(
        ["node", "-e", NODE_SCRIPT, str(ROOT / "web" / "frontier.js"), str(path)],
        capture_output=True, text=True, check=True,
    ).stdout)
    for anchor in tree.nodes:
        assert js[anchor] == expansion_sequence(tree, anchor), f"order differs for anchor {anchor}"


WORDS_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const texts = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(texts.map(t => [window.Frontier.countWords(t), window.Frontier.firstClause(t)])));
"""

WORD_CASES = [
    "", "one two  three\nfour", "a - b | c", "今天天气很好。", "これは日本語です", "カタカナ", "你好，世界！", "「你好」",
    "안녕하세요 세계", "저는 학생입니다.", "Riemann 是一个阅读工具 for Sam", "GPT-4 发布了", "他说「好。」然后走了。",
    "𠀀𠀁 extension B", "ｶﾀｶﾅ half width", "々 and 〆 and 〇", "mixed。English。 sentence", "\n\n今天\n天气\n",
    "Plain prose. Two sentences here.", "日本語の文章です。次の文です！最後？",
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_and_python_count_words_and_first_clause_alike(tmp_path):
    from riemann.abstraction.chunk import word_count
    from riemann.abstraction.frontier import _first_clause

    path = tmp_path / "texts.json"
    path.write_text(json.dumps(WORD_CASES))
    js = json.loads(subprocess.run(
        ["node", "-e", WORDS_SCRIPT, str(ROOT / "web" / "frontier.js"), str(path)],
        capture_output=True, text=True, check=True,
    ).stdout)
    for text, (n, clause) in zip(WORD_CASES, js):
        assert n == word_count(text), f"word count differs for {text!r}"
        assert clause == _first_clause(text), f"first clause differs for {text!r}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_visible_words_match_python_on_a_cjk_tree(tmp_path):
    """visibleWords counts a skim node's title and key points; for Chinese
    (no spaces) that used to be one word per string."""
    from riemann.abstraction.frontier import visible_words
    from riemann.abstraction.model import Node

    def node(nid, **kw):
        base = dict(id=nid, depth=0, text="", words=0, source_span=(0, 1))
        base.update(kw)
        return Node(**base)

    nodes = {
        "r": node("r", text="根节点摘要。", words=5, children=["a", "b"], hook="钩子一句话"),
        "a": node("a", depth=1, text="第一部分的摘要内容在这里。", words=12, children=["a1"], parent="r",
                  title="第一部分", key_points=["要点一很重要", "要点二也是"], hook="为什么重要"),
        "b": node("b", depth=1, text="第二部分。", words=5, parent="r", is_leaf=True),
        "a1": node("a1", depth=2, text="叶子。", words=2, parent="a", is_leaf=True),
    }
    tree = Tree(id="t", title="T", source_text="x", source_words=20, root="r", nodes=nodes, max_depth=2, status="done")
    path = tmp_path / "tree.json"
    path.write_text(tree.model_dump_json())
    script = """
    const fs = require('fs'); global.window = {};
    eval(fs.readFileSync(process.argv[1], 'utf8'));
    const tree = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const out = [window.Frontier.visibleWords(tree, ['r'], new Set()), window.Frontier.visibleWords(tree, ['a', 'b'], new Set())];
    process.stdout.write(JSON.stringify(out));
    """
    js = json.loads(subprocess.run(["node", "-e", script, str(ROOT / "web" / "frontier.js"), str(path)],
                                   capture_output=True, text=True, check=True).stdout)
    assert js == [visible_words(tree, ["r"], set()), visible_words(tree, ["a", "b"], set())]
    assert js[0] == 5  # the hook "钩子一句话": five characters, not one word
    assert js[1] == 4 + 6 + 5 + 5  # title + two key points + leaf b


SCOPED_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map((c) => window.Frontier.buildExpansionSequence(c.tree, c.anchor, new Set(c.keep), c.scope));
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_scoped_sequences_match_js(tmp_path):
    """A scope confines the order to one section; the JS and Python builders must agree on it."""
    import random

    from riemann.abstraction.frontier import frontier_at, prose_at
    from tests.test_frontier_random import KINDS, make_tree

    cases, expect = [], []
    for seed in range(1, 9):
        for kind in KINDS:
            tree = make_tree(seed, kind)
            cur = tree.root
            while len(tree.nodes[cur].children) == 1:
                cur = tree.nodes[cur].children[0]
            if not tree.nodes[cur].children:
                continue
            rng = random.Random(f"scopeparity:{seed}:{kind}")
            for _ in range(3):
                old = expansion_sequence(tree, rng.choice(sorted(tree.nodes)))
                k = rng.randint(0, len(old))
                frontier = frontier_at(tree, old, k)
                keep = _keep_for(tree, frontier, prose_at(old, k))
                anchor = rng.choice(frontier)
                scope = None
                n = anchor
                while n is not None:
                    if n in tree.nodes[cur].children:
                        scope = n
                    n = tree.nodes[n].parent
                if scope is None:
                    continue
                cases.append({"tree": tree.model_dump(), "anchor": anchor, "keep": sorted(keep), "scope": scope})
                expect.append(expansion_sequence(tree, anchor, keep_expanded=keep, scope_id=scope))
    assert len(cases) > 30
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    js = json.loads(subprocess.run(
        ["node", "-e", SCOPED_SCRIPT, str(ROOT / "web" / "frontier.js"), str(path)],
        capture_output=True, text=True, check=True,
    ).stdout)
    assert js == expect
