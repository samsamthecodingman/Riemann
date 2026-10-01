"""Experiment support (the ABAB single-case protocol, docs/overnight-review.md R4): optional fields on the
event log, and scripts/experiment_report.py, which summarises the log by condition and phase."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from riemann import events

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "experiment_report.py"


# --- the optional fields --------------------------------------------------------------------

def test_valid_experiment_fields_pass_through_untouched():
    ev = {
        "type": "close", "tree_id": "t1", "condition": "B", "phase": "B2", "doc_label": "week2-brief", "session_ms": 340000,
        "first_zoom_ms": 4200, "max_z": 0.75, "source_checks": 3, "did_it_help": True,
    }
    assert events.clean_event(ev) == ev


def test_invalid_experiment_fields_are_dropped_but_the_event_stays():
    ev = {"type": "close", "tree_id": "t1", "condition": "C", "phase": "B9", "max_z": 7, "first_zoom_ms": -5, "did_it_help": "yes",
          "checklist_score": 9, "tlx_mental": 101, "doc_label": "x" * 500, "session_ms": "long", "minutes_to_know": float("nan")}
    out = events.clean_event(ev)
    assert out["type"] == "close" and out["tree_id"] == "t1"
    assert set(out) == {"type", "tree_id", "doc_label"} and out["doc_label"] == "x" * 80


def test_booleans_are_not_numbers_and_numbers_are_not_booleans():
    out = events.clean_event({"type": "outcome", "session_ms": True, "checklist_score": True, "missed_later": 1, "started_within_24h": False})
    assert out == {"type": "outcome", "started_within_24h": False}


def test_other_events_and_unknown_fields_are_not_touched():
    ev = {"type": "dial", "tree_id": "t", "z_from": 0.5, "z_to": 1, "input": "key", "anything": {"nested": [1, 2]}}
    assert events.clean_event(ev) == ev


def test_the_documented_field_names_are_the_accepted_ones():
    assert set(events.EXPERIMENT_FIELDS) == {
        "condition", "phase", "doc_label", "first_zoom_ms", "max_z", "session_ms", "source_checks", "did_it_help",
        "minutes_to_know", "checklist_score", "tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort",
        "tlx_frustration", "missed_later", "started_within_24h", "minutes_to_first_action",
    }
    assert events.PHASES == ("A1", "B1", "A2", "B2")


async def test_post_events_cleans_experiment_fields_before_logging(tmp_path, monkeypatch):
    import riemann.server as server

    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as c:
        r = await c.post("/api/events", json=[{"type": "close", "tree_id": "t", "max_z": 0.5, "phase": "nope"}])
        assert r.status_code == 204
    line = json.loads(events.log_path().read_text().splitlines()[-1])
    assert line["max_z"] == 0.5 and "phase" not in line and line["type"] == "close" and "ts" in line


# --- the report -----------------------------------------------------------------------------

def _load():
    spec = importlib.util.spec_from_file_location("experiment_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["experiment_report"] = mod
    spec.loader.exec_module(mod)
    return mod


def _log(path: Path, rows: list[dict]):
    with path.open("w") as f:
        for i, row in enumerate(rows):
            f.write(json.dumps({"ts": f"2026-10-{1 + i // 20:02d}T10:{i % 20:02d}:00+00:00", **row}) + "\n")


def _abab_rows():
    """Four phases of two documents each; B phases are faster and score higher."""
    rows = []
    for phase, cond, minutes, score, tlx in (("A1", "A", 14, 2, 70), ("B1", "B", 6, 4, 40), ("A2", "A", 13, 3, 65), ("B2", "B", 5, 5, 35)):
        rows.append({"type": "experiment", "action": "set", "condition": cond, "phase": phase, "doc_label": f"{phase}-doc1"})
        if cond == "B":
            rows += [{"type": "open", "tree_id": f"t-{phase}-1", "resumed": False}, {"type": "dial", "tree_id": f"t-{phase}-1", "z_from": 0, "z_to": 0.5, "input": "key"},
                     {"type": "hover_source", "tree_id": f"t-{phase}-1", "node_id": "n1"},
                     {"type": "close", "tree_id": f"t-{phase}-1", "session_ms": 300000, "first_zoom_ms": 3000, "max_z": 0.75, "source_checks": 2},
                     {"type": "did_it_help", "tree_id": f"t-{phase}-1", "value": True}]
        rows.append({"type": "outcome", "doc_label": f"{phase}-doc1", "minutes_to_know": minutes, "checklist_score": score, "tlx_mental": tlx, "tlx_physical": 10,
                     "tlx_temporal": tlx, "tlx_performance": tlx, "tlx_effort": tlx, "tlx_frustration": tlx, "started_within_24h": cond == "B"})
        rows.append({"type": "experiment", "action": "set", "condition": cond, "phase": phase, "doc_label": f"{phase}-doc2"})
        rows.append({"type": "outcome", "doc_label": f"{phase}-doc2", "minutes_to_know": minutes + 2, "checklist_score": score, "missed_later": cond == "A"})
    return rows


def test_report_groups_documents_by_phase_and_condition(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    _log(log, _abab_rows())
    rep = mod.summarise(mod.read_events(log))
    assert [p["phase"] for p in rep["phases"]] == ["A1", "B1", "A2", "B2"]
    a1, b1 = rep["phases"][0], rep["phases"][1]
    assert a1["condition"] == "A" and b1["condition"] == "B" and a1["documents"] == 2 and b1["documents"] == 2
    assert a1["minutes_to_know"]["median"] == 15 and b1["minutes_to_know"]["median"] == 7  # docs of 14 and 16 / 6 and 8
    assert b1["checklist_score"]["mean"] == 4 and a1["checklist_score"]["mean"] == 2
    assert a1["tlx_raw"]["mean"] == pytest.approx((70 * 5 + 10) / 6)
    assert b1["sessions"] == 1 and b1["max_z"]["median"] == 0.75 and b1["first_zoom_ms"]["median"] == 3000 and b1["source_checks"]["mean"] == 2
    assert b1["did_it_help"] == {"yes": 1, "no": 0}
    assert a1["missed_later"] == {"yes": 1, "no": 0} and rep["by_condition"]["B"]["documents"] == 4


def test_report_reads_the_pattern_across_the_reversals(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    _log(log, _abab_rows())
    rep = mod.summarise(mod.read_events(log))
    m = {x["metric"]: x for x in rep["pattern"]}
    assert m["minutes_to_know"]["better"] == "lower" and m["minutes_to_know"]["changes"] == ["better", "worse", "better"]
    assert m["checklist_score"]["better"] == "higher" and m["checklist_score"]["changes"] == ["better", "worse", "better"]
    assert m["minutes_to_know"]["b_beat_a_twice"] is True


def test_events_without_a_preceding_experiment_event_are_left_out_of_the_phases(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    _log(log, [{"type": "open", "tree_id": "x"}, {"type": "close", "tree_id": "x", "session_ms": 1000}, {"type": "outcome", "doc_label": "d", "minutes_to_know": 3}])
    rep = mod.summarise(mod.read_events(log))
    assert rep["phases"] == [] and rep["unassigned_events"] == 3


def test_an_explicit_condition_on_an_event_beats_the_carried_state(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    _log(log, [{"type": "experiment", "action": "set", "condition": "A", "phase": "A1", "doc_label": "d"},
               {"type": "outcome", "doc_label": "e", "condition": "B", "phase": "B1", "minutes_to_know": 4}])
    rep = mod.summarise(mod.read_events(log))
    assert [p["phase"] for p in rep["phases"]] == ["B1"] and rep["phases"][0]["documents"] == 1


def test_partial_outcomes_for_one_document_are_merged(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    _log(log, [{"type": "experiment", "action": "set", "condition": "B", "phase": "B1", "doc_label": "d"},
               {"type": "outcome", "doc_label": "d", "minutes_to_know": 5},
               {"type": "outcome", "doc_label": "d", "checklist_score": 4},
               {"type": "outcome", "doc_label": "d", "missed_later": False}])
    rep = mod.summarise(mod.read_events(log))
    b1 = rep["phases"][0]
    assert b1["documents"] == 1 and b1["minutes_to_know"]["n"] == 1 and b1["checklist_score"]["mean"] == 4 and b1["missed_later"] == {"yes": 0, "no": 1}


def test_bad_lines_and_empty_logs_do_not_crash(tmp_path):
    mod = _load()
    log = tmp_path / "events.jsonl"
    log.write_text('not json\n{"type": "open"}\n[1,2]\n\n{"ts": 5}\n')
    rep = mod.summarise(mod.read_events(log))
    assert rep["phases"] == []
    assert mod.read_events(tmp_path / "missing.jsonl") == []


def test_command_line_text_csv_and_json(tmp_path):
    log = tmp_path / "events.jsonl"
    _log(log, _abab_rows())
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPT), "--file", str(log), *a], capture_output=True, text=True, check=True).stdout
    text = run()
    assert "A1" in text and "B2" in text and "minutes to know what to do" in text.lower()
    assert "progress" not in text.lower() and "%" not in text.split("\n")[0]
    csv_out = run("--csv")
    lines = csv_out.strip().splitlines()
    assert lines[0].startswith("phase,condition,doc_label") and len(lines) == 9  # header + 8 documents
    data = json.loads(run("--json"))
    assert [p["phase"] for p in data["phases"]] == ["A1", "B1", "A2", "B2"]


def test_default_path_follows_riemann_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    mod = _load()
    assert mod.default_log_path() == events.log_path() == tmp_path / "share" / "events.jsonl"
