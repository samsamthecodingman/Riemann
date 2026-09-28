"""Tree cache: ~/.cache/riemann/trees/<sha256>.json.

RIEMANN_DATA_DIR, when set, overrides both the cache dir and the events
log dir (events.py mirrors this override -- see docs/v1-build-spec.md,
"Data dirs").
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from riemann.abstraction.model import Tree


def cache_dir() -> Path:
    override = os.environ.get("RIEMANN_DATA_DIR")
    if override:
        base = Path(override) / "cache"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / "riemann"
    trees_dir = base / "trees"
    trees_dir.mkdir(parents=True, exist_ok=True)
    return trees_dir


def tree_id_for(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def path_for(tree_id: str) -> Path:
    return cache_dir() / f"{tree_id}.json"


def load_tree(tree_id: str) -> Tree | None:
    path = path_for(tree_id)
    if not path.exists():
        return None
    return Tree.model_validate_json(path.read_text(encoding="utf-8"))


def save_tree(tree: Tree) -> None:
    path = path_for(tree.id)
    path.write_text(tree.model_dump_json(), encoding="utf-8")


def exists(tree_id: str) -> bool:
    return path_for(tree_id).exists()


def recent_trees(limit: int = 20) -> list[dict]:
    """Last `limit` cached trees (id, title, words, updated), newest first."""
    trees_dir = cache_dir()
    entries = []
    for path in trees_dir.glob("*.json"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        entries.append((mtime, path))
    entries.sort(key=lambda e: e[0], reverse=True)

    out = []
    for mtime, path in entries[:limit]:
        try:
            tree = Tree.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append(
            {
                "id": tree.id,
                "title": tree.title,
                "words": tree.source_words,
                "updated": mtime,
            }
        )
    return out
