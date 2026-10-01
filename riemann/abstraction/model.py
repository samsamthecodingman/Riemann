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


class Essential(BaseModel):
    """One label/value line of a document's overview card (e.g. "Due" /
    "Friday 5 pm"). Every number in `value` must appear in the cited leaves."""

    label: str
    value: str
    cites: list[str] = Field(default_factory=list)


class CitedText(BaseModel):
    """A short model-written line with the leaves it comes from (Overview.start_here)."""

    text: str
    cites: list[str] = Field(default_factory=list)


class SizeOfJob(BaseModel):
    """A rough estimate of the work ("about 3 sessions of 2 hours") and what it is
    based on (`basis`, e.g. "a 2,000-word report and 4 datasets": every number in it
    appears in the cited leaves)."""

    text: str
    basis: str
    cites: list[str] = Field(default_factory=list)


class Deadline(BaseModel):
    """The single main deadline, checked against the cited leaves: the day number and the
    month must appear there. `time` is "HH:MM" (24 h) when the source gives one. When the source
    gives no year, `iso` uses the next occurrence of that day and `year_inferred` is true."""

    iso: str
    time: str | None = None
    label: str
    cites: list[str] = Field(default_factory=list)
    year_inferred: bool = False


class Action(BaseModel):
    """One meeting action: who does what by when. `due` is the source's own wording of the date
    ("Friday 14 November"), `due_iso` the same date as YYYY-MM-DD when it could be worked out."""

    who: str
    what: str
    due: str | None = None
    due_iso: str | None = None
    cites: list[str] = Field(default_factory=list)
    year_inferred: bool = False


class Overview(BaseModel):
    """The "what is this" card shown above section 01 at every zoom level:
    what kind of document it is, its real title, one plain sentence, and the
    few things the reader most needs (chosen by their goal and the kind of
    document). Built once by build.generate_overview, or backfilled for older
    trees; optional so trees cached before it existed still load."""

    doc_title: str
    doc_kind: str
    what_it_is: str
    essentials: list[Essential] = Field(default_factory=list)
    start_here: CitedText | None = None
    """One concrete first step, doable in about ten minutes (at most 25 words). Task-like documents only."""
    size_of_job: SizeOfJob | None = None
    """A rough estimate of the work (at most 20 words), with what it is based on. Task-like documents only."""
    deadline: Deadline | None = None
    """The single main deadline, if the source states one. Task-like documents only."""
    actions: list[Action] = Field(default_factory=list)
    """Meeting notes only: who does what by when, earliest due first, undated last."""


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
    genre: str | None = None
    """Document genre: a key of genre.GENRES (assignment, paper, news, email, meeting, legal,
    technical, article, other); None for trees built before genre detection."""
    overview: Overview | None = None
    """"What is this" card (see Overview); None for trees built before it
    existed, until the backfill endpoint adds it."""
