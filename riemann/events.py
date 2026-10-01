"""Append-only local event log: ~/.local/share/riemann/events.jsonl.

Local only, never sent anywhere. RIEMANN_DATA_DIR, when set, overrides the
default location (mirrors cache.py's override).
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

# Optional fields for the two-week ABAB single-case experiment (docs/experiment.md, docs/overview-spec.md
# "Phase 1 data contract"). They may appear on any event; a value that is not valid is dropped (the event
# is always kept). The log never gets progress, read marks or document text.
PHASES = ("A1", "B1", "A2", "B2")


def _num(lo: float, hi: float):
    def ok(v: object) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi

    return ok


def _int(lo: int, hi: int):
    def ok(v: object) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi

    return ok


def _bool(v: object) -> bool:
    return isinstance(v, bool)


EXPERIMENT_FIELDS: dict[str, object] = {
    "condition": lambda v: v in ("A", "B"),  # A = the original document, B = Riemann
    "phase": lambda v: v in PHASES,
    "doc_label": lambda v: isinstance(v, str) and bool(v.strip()),  # trimmed and cut to 80 characters
    "first_zoom_ms": _num(0, 86_400_000),  # open -> first dial input
    "max_z": _num(0, 1),  # deepest zoom reached in the session
    "session_ms": _num(0, 86_400_000),
    "source_checks": _int(0, 100_000),  # hover_source + jump_source in the session
    "did_it_help": _bool,
    "minutes_to_know": _num(0, 1440),  # self-timed: minutes until "I know what to do"
    "checklist_score": _int(0, 5),  # the fixed 5-question checklist, scored against the source
    "tlx_mental": _num(0, 100),  # NASA-TLX raw sub-scales
    "tlx_physical": _num(0, 100),
    "tlx_temporal": _num(0, 100),
    "tlx_performance": _num(0, 100),
    "tlx_effort": _num(0, 100),
    "tlx_frustration": _num(0, 100),
    "missed_later": _bool,  # a week later: did I find I had missed something?
    "started_within_24h": _bool,
    "minutes_to_first_action": _num(0, 20_160),
}


def clean_event(event: dict) -> dict:
    """The event with any invalid experiment field removed (a doc_label is trimmed and cut to 80
    characters). Other fields, and events without experiment fields, are untouched."""
    out = dict(event)
    for name, ok in EXPERIMENT_FIELDS.items():
        if name not in out:
            continue
        value = out[name]
        if name == "doc_label" and isinstance(value, str):
            value = out[name] = value.strip()[:80]
        if not ok(value):
            del out[name]
    return out


def data_dir() -> Path:
    override = os.environ.get("RIEMANN_DATA_DIR")
    if override:
        base = Path(override) / "share"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "riemann"
    base.mkdir(parents=True, exist_ok=True)
    return base


def log_path() -> Path:
    return data_dir() / "events.jsonl"


def append_events(events: list[dict]) -> None:
    path = log_path()
    now = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as f:
        for event in events:
            record = {"ts": now, **clean_event(event)}
            f.write(json.dumps(record) + "\n")
