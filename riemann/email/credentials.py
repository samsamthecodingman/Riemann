"""Resolve an account's credential_ref to a local path. Only "file:<path>" for now."""

from __future__ import annotations

from pathlib import Path


def resolve_ref(ref: str) -> Path:
    scheme, sep, rest = ref.partition(":")
    if sep and scheme == "file" and rest:
        return Path(rest).expanduser()
    if sep and scheme == "file":
        raise ValueError(f"credential_ref {ref!r} has an empty path; expected 'file:<path>'")
    shown = f"{scheme}:" if sep else repr(ref)
    raise ValueError(f"unsupported credential_ref scheme {shown} in {ref!r}; only 'file:<path>' is supported for now")
