"""Append-only local event log: ~/.local/share/riemann/events.jsonl.

Local only, never sent anywhere. RIEMANN_DATA_DIR, when set, overrides the
default location (mirrors cache.py's override).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


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
            record = {"ts": now, **event}
            f.write(json.dumps(record) + "\n")
