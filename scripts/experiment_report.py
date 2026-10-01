#!/usr/bin/env python3
"""Summarise Riemann's event log for the two-week ABAB experiment (docs/experiment.md).

    uv run python scripts/experiment_report.py            # a readable report of the default log
    uv run python scripts/experiment_report.py --csv      # one row per document, for a spreadsheet
    uv run python scripts/experiment_report.py --json     # everything, for your own plotting
    uv run python scripts/experiment_report.py --file path/to/events.jsonl

Events are assigned to a phase (A1, B1, A2, B2) and a condition (A = the original document, B = Riemann) by
their own `phase` and `condition` fields, or else by the latest `experiment` event before them. Outcomes come
from `outcome` events (one per document; several partial ones for the same document are merged) and the
behaviour numbers from the `close`, `did_it_help` events. Judge the result by the pattern across the phases
(did B beat A, and did it again after the reversal), not by a p-value. Nothing here is a progress measure.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import sys
from pathlib import Path

PHASE_ORDER = ["A1", "B1", "A2", "B2"]
TLX = ["tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration"]
OUTCOME_NUMBERS = ["minutes_to_know", "checklist_score", "minutes_to_first_action"]
OUTCOME_FLAGS = ["missed_later", "started_within_24h"]
# metric -> (label, which direction is better, how to centre the phase: median for minutes, mean for scores)
PATTERN_METRICS = {
    "minutes_to_know": ("Minutes to know what to do", "lower", "median"),
    "checklist_score": ("Checklist score (0 to 5)", "higher", "mean"),
    "tlx_raw": ("Effort, NASA-TLX raw (0 to 100)", "lower", "mean"),
    "minutes_to_first_action": ("Minutes to the first real action", "lower", "median"),
}


def default_log_path() -> Path:
    from riemann import events

    return events.log_path()


def read_events(path: Path) -> list[dict]:
    """The log's events in order; a missing file or a damaged line is skipped."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {"n": len(values), "mean": statistics.fmean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _yes_no(values: list[bool]) -> dict:
    return {"yes": sum(1 for v in values if v), "no": sum(1 for v in values if not v)}


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class _Doc:
    def __init__(self, phase: str, condition: str, label: str) -> None:
        self.phase, self.condition, self.label = phase, condition, label
        self.fields: dict[str, object] = {}
        self.sessions = 0
        self.session_ms: list[float] = []
        self.first_zoom_ms: list[float] = []
        self.max_z: list[float] = []
        self.source_checks: list[float] = []
        self.did_it_help: list[bool] = []

    def tlx_raw(self) -> float | None:
        vals = [self.fields.get(k) for k in TLX]
        return statistics.fmean(vals) if all(_is_num(v) for v in vals) else None


def summarise(events: list[dict]) -> dict:
    state: dict[str, str | None] = {"condition": None, "phase": None, "doc_label": None}
    docs: dict[tuple[str, str], _Doc] = {}
    unassigned = 0
    for ev in events:
        if ev.get("type") == "experiment":
            if ev.get("action") == "end":
                state = {"condition": None, "phase": None, "doc_label": None}
                continue
            for key in ("condition", "phase", "doc_label"):
                if isinstance(ev.get(key), str) and ev[key]:
                    state[key] = ev[key]
            if state["phase"] and not ev.get("condition"):
                state["condition"] = state["phase"][0]
            continue
        phase = ev.get("phase") if ev.get("phase") in PHASE_ORDER else state["phase"]
        if phase is None:
            unassigned += 1
            continue
        condition = ev.get("condition") if ev.get("condition") in ("A", "B") else (phase[0] if ev.get("phase") in PHASE_ORDER else state["condition"] or phase[0])
        label = ev.get("doc_label") if isinstance(ev.get("doc_label"), str) and ev.get("doc_label") else state["doc_label"] or ev.get("tree_id") or "(unlabelled)"
        key = (phase, str(label))
        doc = docs.get(key)
        if doc is None:
            doc = docs[key] = _Doc(phase, str(condition), str(label))
        t = ev.get("type")
        if t == "outcome":
            for name in OUTCOME_NUMBERS + TLX + OUTCOME_FLAGS:
                if name in ev:
                    doc.fields[name] = ev[name]
        elif t == "close":
            doc.sessions += 1
            for name, bucket in (("session_ms", doc.session_ms), ("first_zoom_ms", doc.first_zoom_ms), ("max_z", doc.max_z), ("source_checks", doc.source_checks)):
                if _is_num(ev.get(name)):
                    bucket.append(float(ev[name]))
            if isinstance(ev.get("did_it_help"), bool):
                doc.did_it_help.append(ev["did_it_help"])
        elif t == "did_it_help" and isinstance(ev.get("value"), bool):
            doc.did_it_help.append(ev["value"])

    def phase_entry(phase: str, ds: list[_Doc]) -> dict:
        def vals(name: str) -> list[float]:
            return [float(d.fields[name]) for d in ds if _is_num(d.fields.get(name))]

        def flags(name: str) -> dict:
            return _yes_no([d.fields[name] for d in ds if isinstance(d.fields.get(name), bool)])

        entry = {
            "phase": phase,
            "condition": ds[0].condition,
            "documents": len(ds),
            "sessions": sum(d.sessions for d in ds),
            "tlx_raw": _stats([v for d in ds if (v := d.tlx_raw()) is not None]),
            "session_ms": _stats([v for d in ds for v in d.session_ms]),
            "first_zoom_ms": _stats([v for d in ds for v in d.first_zoom_ms]),
            "max_z": _stats([v for d in ds for v in d.max_z]),
            "source_checks": _stats([v for d in ds for v in d.source_checks]),
            "did_it_help": _yes_no([v for d in ds for v in d.did_it_help]),
        }
        for name in OUTCOME_NUMBERS:
            entry[name] = _stats(vals(name))
        for name in OUTCOME_FLAGS:
            entry[name] = flags(name)
        return entry

    phases = []
    for phase in PHASE_ORDER:
        ds = [d for d in docs.values() if d.phase == phase]
        if ds:
            phases.append(phase_entry(phase, ds))
    by_condition = {}
    for cond in ("A", "B"):
        ds = [d for d in docs.values() if d.condition == cond]
        if ds:
            by_condition[cond] = {"documents": len(ds), "sessions": sum(d.sessions for d in ds), "phases": [p["phase"] for p in phases if p["condition"] == cond]}

    pattern = []
    for metric, (label, better, centre) in PATTERN_METRICS.items():
        series = [(p["phase"], p[metric][centre]) for p in phases if p[metric]["n"] > 0]
        if len(series) < 2:
            continue
        changes = []
        for (_, a), (_, b) in zip(series, series[1:]):
            if a == b:
                changes.append("same")
            else:
                improved = b < a if better == "lower" else b > a
                changes.append("better" if improved else "worse")
        # "B beat A twice": each B phase beat the A phase before it.
        by_phase = dict(series)
        pairs = [("A1", "B1"), ("A2", "B2")]
        beat = None
        if all(a in by_phase and b in by_phase for a, b in pairs):
            beat = all((by_phase[b] < by_phase[a]) if better == "lower" else (by_phase[b] > by_phase[a]) for a, b in pairs)
        pattern.append({"metric": metric, "label": label, "better": better, "centre": centre, "series": series, "changes": changes, "b_beat_a_twice": beat})
    return {"phases": phases, "by_condition": by_condition, "pattern": pattern, "unassigned_events": unassigned, "documents": [_doc_row(d) for d in sorted(docs.values(), key=lambda d: (PHASE_ORDER.index(d.phase), d.label))]}


def _doc_row(d: _Doc) -> dict:
    row = {"phase": d.phase, "condition": d.condition, "doc_label": d.label}
    for name in OUTCOME_NUMBERS:
        row[name] = d.fields.get(name) if _is_num(d.fields.get(name)) else None
    row["tlx_raw"] = d.tlx_raw()
    for name in OUTCOME_FLAGS:
        row[name] = d.fields.get(name) if isinstance(d.fields.get(name), bool) else None
    row["sessions"] = d.sessions
    row["session_ms"] = sum(d.session_ms) if d.session_ms else None
    row["first_zoom_ms"] = d.first_zoom_ms[0] if d.first_zoom_ms else None
    row["max_z"] = max(d.max_z) if d.max_z else None
    row["source_checks"] = sum(d.source_checks) if d.source_checks else None
    row["did_it_help"] = d.did_it_help[-1] if d.did_it_help else None
    return row


def to_csv(report: dict) -> str:
    rows = report["documents"]
    cols = ["phase", "condition", "doc_label", "minutes_to_know", "checklist_score", "tlx_raw", "minutes_to_first_action", "missed_later",
            "started_within_24h", "sessions", "session_ms", "first_zoom_ms", "max_z", "source_checks", "did_it_help"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r[c] is None else r[c] for c in cols])
    return buf.getvalue()


def _fmt(x: float | None, digits: int = 1) -> str:
    return "-" if x is None else (f"{x:.{digits}f}".rstrip("0").rstrip(".") or "0")


def to_text(report: dict) -> str:
    if not report["phases"]:
        return (
            "No experiment events found yet.\n"
            "Log an `experiment` event when you start each phase (see docs/experiment.md), then read or score some documents.\n"
            f"({report['unassigned_events']} events were not inside a phase.)\n"
        )
    out = ["Riemann two-week experiment (A = original document, B = Riemann)", ""]
    for p in report["phases"]:
        out.append(f"{p['phase']}  condition {p['condition']}  {p['documents']} document(s), {p['sessions']} Riemann session(s)")
        out.append(f"    Minutes to know what to do: median {_fmt(p['minutes_to_know']['median'])} (n={p['minutes_to_know']['n']})")
        out.append(f"    Checklist score (0 to 5): mean {_fmt(p['checklist_score']['mean'])} (n={p['checklist_score']['n']})")
        out.append(f"    Effort, NASA-TLX raw (0 to 100): mean {_fmt(p['tlx_raw']['mean'])} (n={p['tlx_raw']['n']})")
        if p["minutes_to_first_action"]["n"]:
            out.append(f"    Minutes to the first real action: median {_fmt(p['minutes_to_first_action']['median'])}")
        for name, label in (("started_within_24h", "Started within 24 hours"), ("missed_later", "Missed something, found a week later"), ("did_it_help", "Did it help")):
            yn = p[name]
            if yn["yes"] + yn["no"]:
                out.append(f"    {label}: yes {yn['yes']}, no {yn['no']}")
        if p["sessions"]:
            out.append(
                f"    In Riemann: session median {_fmt((p['session_ms']['median'] or 0) / 60000)} min, first zoom median {_fmt((p['first_zoom_ms']['median'] or 0) / 1000)} s, "
                f"deepest zoom median {_fmt(p['max_z']['median'], 2)}, source checks mean {_fmt(p['source_checks']['mean'])} per session"
            )
        out.append("")
    if report["pattern"]:
        out.append("Pattern across the phases (judge by this, not a p-value; each arrow compares with the phase before)")
        for m in report["pattern"]:
            parts = [f"{ph} {_fmt(v)}" for ph, v in m["series"]]
            arrows = " ".join(f"({c})" for c in m["changes"])
            line = f"  {m['label']} ({m['better']} is better): " + " > ".join(parts) + "  " + arrows
            if m["b_beat_a_twice"] is not None:
                line += "  B beat A both times: " + ("yes" if m["b_beat_a_twice"] else "no")
            out.append(line)
        out.append("")
    if report["unassigned_events"]:
        out.append(f"{report['unassigned_events']} event(s) were outside any phase and are not counted.")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", type=Path, help="events.jsonl to read (default: Riemann's own log)")
    fmt = ap.add_mutually_exclusive_group()
    fmt.add_argument("--csv", action="store_true", help="one row per document")
    fmt.add_argument("--json", action="store_true", help="the whole summary as JSON")
    args = ap.parse_args(argv)
    report = summarise(read_events(args.file or default_log_path()))
    if args.csv:
        sys.stdout.write(to_csv(report))
    elif args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(to_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
