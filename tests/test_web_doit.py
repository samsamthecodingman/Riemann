"""web/doit.js: how a deadline is worded relative to today (pure; run under Node)."""
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
const D = window.DoIt;
const cases = JSON.parse(process.argv[2]);
// "now" is local noon on 2025-11-09 (a Sunday), unless the case says otherwise
const out = cases.map(([fn, ...a]) => D[fn](...a.map((x) => (x && x.now ? new Date(...x.now) : x))));
process.stdout.write(JSON.stringify(out));
"""


def run(cases):
    r = subprocess.run(
        ["node", "-e", SCRIPT, str(ROOT / "web" / "doit.js"), json.dumps(cases)],
        capture_output=True, text=True, timeout=20,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


NOW = {"now": [2025, 10, 9, 12, 0]}  # months are 0-based: 9 Nov 2025


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_relative_due_wording():
    out = run([
        ["relativeDue", "2025-11-14", NOW],
        ["relativeDue", "2025-11-09", NOW],
        ["relativeDue", "2025-11-10", NOW],
        ["relativeDue", "2025-11-08", NOW],
        ["relativeDue", "2025-11-07", NOW],
        ["relativeDue", "2025-11-11", NOW],
        ["relativeDue", "2025-12-09", NOW],
        ["relativeDue", "not a date", NOW],
        ["relativeDue", "2025-02-30", NOW],
    ])
    assert out[0] == {"days": 5, "text": "Due in 5 days", "state": "future"}
    assert out[1]["text"] == "Due today" and out[1]["state"] == "today"
    assert out[2]["text"] == "Due tomorrow"
    assert out[3]["text"] == "Overdue by 1 day" and out[3]["state"] == "overdue"
    assert out[4]["text"] == "Overdue by 2 days"
    assert out[5]["text"] == "Due in 2 days"
    assert out[6]["text"] == "Due in 30 days"
    assert out[7] is None and out[8] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_time_of_day_never_changes_the_day_count():
    late = {"now": [2025, 10, 9, 23, 59]}
    early = {"now": [2025, 10, 9, 0, 1]}
    out = run([["relativeDue", "2025-11-10", late], ["relativeDue", "2025-11-10", early]])
    assert out[0]["text"] == out[1]["text"] == "Due tomorrow"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_date_and_clock_text():
    out = run([
        ["dueDateText", "2025-11-14", "17:00", NOW],
        ["dueDateText", "2025-11-14", "09:30", NOW],
        ["dueDateText", "2025-11-14", None, NOW],
        ["dueDateText", "2025-11-14", "00:00", NOW],
        ["dueDateText", "2025-11-14", "12:00", NOW],
        ["dueDateText", "2026-01-05", "17:00", NOW],
        ["dueDateText", "garbage", "17:00", NOW],
        ["dueDateText", "2025-11-14", "25:00", NOW],
    ])
    assert out == ["Fri 14 Nov, 5 pm", "Fri 14 Nov, 9:30 am", "Fri 14 Nov", "Fri 14 Nov, 12 am",
                   "Fri 14 Nov, 12 pm", "Mon 5 Jan 2026, 5 pm", "", "Fri 14 Nov"]
