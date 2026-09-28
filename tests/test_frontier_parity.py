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
