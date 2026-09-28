"""Shared data model for the abstraction tree.

This is the contract between the backend build pipeline and the frontend
zoom dial (see docs/v1-build-spec.md, "Data model"). Keep it in lockstep
with that spec.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Node(BaseModel):
    """One node in the abstraction tree.

    depth increases toward the source (0 = root gist). Leaves carry the
    max depth of their branch, so depth is not uniform across the tree --
    the tree is intentionally ragged (see build.py).
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
