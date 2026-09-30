"""Shared data model for the abstraction tree.

This is the contract between the backend build pipeline and the frontend
zoom dial (see docs/v1-build-spec.md, "Data model"). Keep it in lockstep
with that spec.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KeyFact(BaseModel):
    """A striking, specific fact surfaced for a node (see build.py's
    deterministic validation -- every number-like token in `big`/`detail`
    must appear in the text of the cited leaves, or the whole KeyFact is
    dropped)."""

    big: str
    detail: str
    cites: list[str] = Field(default_factory=list)


class Node(BaseModel):
    """One node in the abstraction tree.

    depth increases toward the source (0 = root gist). Leaves carry the
    max depth of their branch, so depth is not uniform across the tree --
    the tree is intentionally ragged (see build.py).

    title/hook/key_points/key_fact/steps are all optional (schema2, see
    docs/v2-macaron-spec.md §1) so trees cached under the old schema still
    load -- they simply come back with these fields at their defaults.
    """

    id: str
    depth: int
    text: str
    words: int
    children: list[str] = Field(default_factory=list)
    parent: str | None = None
    is_leaf: bool = False
    source_span: tuple[int, int]
    cites: list[str] = Field(default_factory=list)
    importance: float = 0.5
    atomic: bool = False
    title: str | None = None
    short_title: str | None = None
    """<=3 words / 24 chars label for the spatial map's small tiles (optional)."""
    hook: str | None = None
    key_points: list[str] = Field(default_factory=list)
    key_fact: KeyFact | None = None
    steps: list[str] = Field(default_factory=list)


class Tree(BaseModel):
    """An abstraction tree for one source document."""

    id: str
    title: str
    source_text: str
    source_words: int
    root: str
    nodes: dict[str, Node] = Field(default_factory=dict)
    max_depth: int = 0
    status: Literal["building", "done", "error"] = "building"
    provisional_root: bool = False
    model: str | None = None
    """The summariser model that built this tree (None for older trees)."""
    objective: str | None = None
    """What the reader wants the document for (a key of OBJECTIVE_FOCUS in
    build.py, e.g. "execute"); None for older trees / no stated goal."""
    sections: list[str] = Field(default_factory=list)
    """Node ids at the section level: the first depth from the root with
    >=2 nodes. Empty for a single-leaf tree or a tree that never branches
    (a straight chain from root to one leaf). See build.compute_sections."""
