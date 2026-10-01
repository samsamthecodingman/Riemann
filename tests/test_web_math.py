"""web/mathtext.js: which dollar signs are maths (pure; run under Node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const cases = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(cases.map((t) => window.MathText.split(t).maths.map((m) => [m.src, m.tex, m.display]))));
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def maths(*texts):
    r = subprocess.run(["node", "-e", SCRIPT, str(ROOT / "web" / "mathtext.js"), json.dumps(list(texts))],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.parametrize("text", [
    "$5 and $10",
    "It costs $5, then $6.",
    "I have $100 and you have $200.",
    "US$5 and US$6 and A$7",
    "$5-$10 each",
    "Just $5$ here",       # digits only
    "$ x $",               # space after the opening dollar
    "price is $x$5",       # closing dollar followed by a digit
    "a $x\ny$ b",          # inline maths does not cross a line
    "escaped \\$x$ stays text",
    "`$x$` is code",
    "```\n$x$\n```",
    "$$ $$",               # empty display
])
def test_prices_code_and_odd_dollars_are_not_maths(text):
    assert maths(text) == [[]]


def test_inline_and_display_maths_are_found():
    out = maths(
        "Energy is $E = mc^2$ today.",
        "The $x$-axis and $y$.",
        "$$\\int_0^1 f\\,dx$$",
        "Between\n$$a +\nb$$\nafter",
        "I have $100 but $a_1$ is maths",
        "```\n$no$\n```\nthen $yes$",
    )
    assert out[0] == [["$E = mc^2$", "E = mc^2", False]]
    assert [m[1] for m in out[1]] == ["x", "y"]
    assert out[2] == [["$$\\int_0^1 f\\,dx$$", "\\int_0^1 f\\,dx", True]]
    assert out[3][0][2] is True and out[3][0][1] == "a +\nb"
    assert out[4] == [["$a_1$", "a_1", False]]
    assert out[5] == [["$yes$", "yes", False]]
