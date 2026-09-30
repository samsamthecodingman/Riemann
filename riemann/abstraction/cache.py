"""Tree cache: ~/.cache/riemann/trees/<sha256>.json.

RIEMANN_DATA_DIR, when set, overrides both the cache dir and the events
log dir (events.py mirrors this override -- see docs/v1-build-spec.md,
"Data dirs").
"""

from __future__ import annotations

import hashlib
import re
import os
from pathlib import Path

from riemann.abstraction.model import Tree


def _trees_root() -> Path:
    override = os.environ.get("RIEMANN_DATA_DIR")
    if override:
        base = Path(override) / "cache"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / "riemann"
    return base / "trees"


def cache_dir() -> Path:
    trees_dir = _trees_root() / build_version()
    trees_dir.mkdir(parents=True, exist_ok=True)
    return trees_dir


def legacy_dirs() -> list[Path]:
    """Older cache namespaces (other build versions, and the flat trees/ dir
    from before namespacing), newest first. Read-only: trees found there
    still open, but nothing is ever written to them (a backfilled copy is
    saved into the current namespace instead)."""
    root = _trees_root()
    if not root.is_dir():
        return []
    current = build_version()
    subs = [d for d in root.iterdir() if d.is_dir() and d.name != current]
    subs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return subs + [root]


SCHEMA_VERSION = "schema5"  # bump whenever prompts, chunking/normalisation or node fields change (schema2: v2 macaron fields; schema3: sentence-case titles; schema4: normalised text, no single-child chains, overview card; schema5: sentence-aware splitting of long paragraphs)


def build_version() -> str:
    """Cache namespace derived from the build parameters, so changing RATIO,
    leaf size or gist length never serves a tree built under old settings.
    Also namespaced by SCHEMA_VERSION, so a bump there (e.g. new Node/Tree
    fields the old prompts never populated) forces a rebuild instead of
    silently serving stale-shaped trees from the new code path."""
    from riemann.abstraction import build, chunk  # lazy: build imports this module
    return (
        f"r{build.RATIO}-leaf{chunk.MAX_LEAF_WORDS}-gist{build.GIST_WORDS}-stop{build.GIST_STOP_WORDS}"
        f"-{SCHEMA_VERSION}"
    )


def tree_id_for(text: str, model: str | None = None, objective: str | None = None) -> str:
    """Content hash of the source, plus the model that summarises it and the
    reader's objective, so the same document built with a different model or
    goal is a separate tree. With no objective the id is unchanged, so
    existing cached trees keep their ids."""
    key = text if model is None else f"{model}\n{text}"
    if objective:
        key = f"objective:{objective}\n{key}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def is_safe_id(tree_id: object) -> bool:
    """Tree ids are 16 hex digits (or short test names): never a path. Anything
    with a dot, slash or backslash is refused before it can reach the disk."""
    return isinstance(tree_id, str) and _SAFE_ID.fullmatch(tree_id) is not None


def path_for(tree_id: str) -> Path:
    if not is_safe_id(tree_id):
        raise ValueError("invalid tree id")
    return cache_dir() / f"{tree_id}.json"


def _find(tree_id: str) -> Path | None:
    if not is_safe_id(tree_id):
        return None
    for d in [cache_dir(), *legacy_dirs()]:
        path = d / f"{tree_id}.json"
        if path.exists():
            return path
    return None


def load_tree(tree_id: str) -> Tree | None:
    path = _find(tree_id)
    if path is None:
        return None
    return Tree.model_validate_json(path.read_text(encoding="utf-8"))


def save_tree(tree: Tree) -> None:
    path = path_for(tree.id)
    path.write_text(tree.model_dump_json(), encoding="utf-8")


def exists(tree_id: str) -> bool:
    """Whether a tree with this id is cached *under the current build
    version* (an older-version tree is openable but not a reusable build)."""
    return is_safe_id(tree_id) and path_for(tree_id).exists()


def recent_trees(limit: int = 20) -> list[dict]:
    """Last `limit` cached trees (id, title, words, updated), newest first,
    across the current and older cache namespaces (the current one wins for an id)."""
    entries: dict[str, tuple[float, Path]] = {}
    for trees_dir in [cache_dir(), *legacy_dirs()]:
        for path in trees_dir.glob("*.json"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            entries.setdefault(path.stem, (mtime, path))
    ordered = sorted(entries.values(), key=lambda e: e[0], reverse=True)

    out = []
    for mtime, path in ordered:
        if len(out) >= limit:
            break
        try:
            tree = Tree.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append(
            {
                "id": tree.id,
                "title": tree.title,
                "words": tree.source_words,
                "model": tree.model,
                "objective": tree.objective,
                "updated": mtime,
            }
        )
    return out
