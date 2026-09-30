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
