"""Adaptive-depth bottom-up tree build.

Builds a Tree from source text: chunk into leaves, then group siblings
bottom-up so each parent summary is about a quarter of its children's
words (RATIO), recursing until a single node has <= GIST_WORDS words
(the root). Useless levels collapse (see `_group_run` / the `force` param
on `_process_group`). Emits events as it goes: leaves, provisional_root,
level*, done, error -- see docs/v1-build-spec.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable

from riemann.abstraction import checks
from riemann.abstraction.chunk import TINY_DOC_WORDS, chunk, head_words, word_count
from riemann.abstraction.genre import (
    GENRE_ESSENTIALS,
    GENRE_FOCUS,
    GENRES,
    detect_genre,
    valid_genre,
)
from riemann.abstraction.model import Essential, KeyFact, Node, Overview, Tree
from riemann.abstraction.summarise import ModelError, Summariser, parse_json_robustly

RATIO = 3  # compression per step; Forte's practitioner funnel suggests 2.5-4x (weak evidence)
GIST_WORDS = 25
# A node within the usual length tolerance of the gist budget already *is* the gist;
# summarising it again only produces a stub level (seen in testing: 26 -> 11 words).
GIST_STOP_WORDS = round(GIST_WORDS * 1.35)
MAX_CONCURRENCY = 4
LEAF_CONTEXT_CHAR_BUDGET = 6000
LENGTH_TOLERANCE = 0.35
MAX_BUILD_ROUNDS = 40

# Deterministic validation limits (docs/v2-macaron-spec.md §1): "Truncate
# or drop; don't retry."
TITLE_MAX_WORDS = 8
HOOK_MAX_WORDS = 20
SHORT_TITLE_MAX_WORDS = 3
SHORT_TITLE_MAX_CHARS = 24
KEY_POINTS_MAX_ITEMS = 4
KEY_POINT_MAX_WORDS = 18
STEPS_MAX_ITEMS = 8
STEP_MAX_WORDS = 20
# Character caps back up the word caps: a hostile or broken reply can send one
# enormous "word", which a word count alone never trims.
TITLE_MAX_CHARS = 120
HOOK_MAX_CHARS = 300
POINT_MAX_CHARS = 300
KEY_FACT_BIG_MAX_WORDS = 12
KEY_FACT_DETAIL_MAX_WORDS = 40
TEXT_MAX_WORDS = 400

# "\d[\d,.]*" (numbers, incl. thousands separators/decimals), "billion",
# "million", and decades like "1980s" (the trailing "s?" on the digit run
# covers that last case without a separate alternative).
_NUMBER_TOKEN_RE = re.compile(r"\d[\d,.]*s?|\bbillion\b|\bmillion\b", re.IGNORECASE)

SYSTEM_SUMMARY_TEMPLATE = """You are compressing part of a document into a shorter summary node for an adaptive-depth abstraction tree.
Rules:
- Keep causal connectives (because, therefore, however, ...) that are present in the source.
- Never add causation that isn't in the source.
- Keep hedges (may, likely, suggests, ...) rather than stating things as more certain than the source does.
- Keep terminology consistent with the children's wording.
- Target length: about {{TARGET}} words.

Titles (this node's own "title"/"hook", and every value in "child_titles") are punchy but faithful: specific and
concrete, like a good explainer headline -- never a vague label. They must not claim anything the source doesn't
say: no clickbait, no questions unless the source itself poses one, no exclamation marks, no emoji. Write titles in
sentence case (capitalise only the first word, proper nouns and acronyms), e.g. "When a site won't load, suspect DNS". Keep hedges
("often", "may", "suggests") in titles and hooks where the source has them.

Respond with ONLY JSON, no prose outside it and no markdown code fences:
{"text": "...", "cites": ["leaf_id", ...], "importance": {"child_id": 0.0},
 "title": "2-8 word faithful headline for this node",
 "short_title": "<=3 words, <=24 characters: a label for this node on a small map tile",
 "hook": "<=20 words, one line: why this part matters",
 "child_titles": {"child_id": "2-8 word faithful headline for that child"},
 "child_short_titles": {"child_id": "<=3 words, <=24 characters"},
 "key_points": ["2-4 short bullets, each <=18 words, only for a node whose children are sections or paragraphs"],
 "key_fact": {"big": "the number/finding", "detail": "one short clause of context", "cites": ["leaf_id", ...]},
 "steps": ["3-6 short labels, only when the content describes a sequence or process"]}

"cites": leaf ids only, drawn from the "Leaf ids you may cite" list below -- the ones this summary's claims actually come from.
"importance": one entry per id listed in "Child ids" below, 0..1, relative to its siblings, reflecting how much that child matters to the overall point.
"child_titles": one entry per id listed in "Child ids" below.
"short_title" / "child_short_titles": very short labels (at most 3 words and 24 characters) for the same nodes.
"key_points": [] when the children aren't sections/paragraphs (e.g. a single atomic block).
"key_fact": only when the source contains a genuinely striking, specific fact -- otherwise null. Every number in
"big"/"detail" must actually appear in the cited leaves' text. "cites" here are the leaf ids that support the fact.
"steps": [] when the content doesn't describe a sequence or process."""

SYSTEM_ROOT_TEMPLATE = SYSTEM_SUMMARY_TEMPLATE + (
    "\n\nThis call produces the ROOT of the tree: state the single most important conclusion or"
    " takeaway in the target word count -- not what the document is about."
)

SYSTEM_PROVISIONAL = """You are producing a fast provisional one-line gist for a document, to show while the full abstraction tree builds in the background.
State the single most important conclusion or takeaway in <= 25 words, not what the document is about.
Also say what kind of document it is, as "genre": one of "assignment" (an assignment or task brief: something to do, with a deadline or marking), "paper" (a research paper), "news" (a news story), "email" (an email or thread), "meeting" (meeting notes or minutes), "legal" (a contract, policy or rules), "technical" (technical documentation, a guide or a manual), "article" (any other article or essay), "other".
Respond with ONLY JSON, no prose outside it and no markdown code fences: {"text": "...", "genre": "..."}"""

# Reader-goal focus blocks. These steer WHAT to foreground; the faithfulness
# rules in the base template stay absolute and are restated in each block.
# FakeSummariser detects the block via the "Reader's goal: <key>" marker.
_FOCUS_TAIL = (
    "\nThis changes emphasis only. Every claim, number, date and title must still be supported by the source;"
    " never invent requirements, deadlines or options that the source does not state."
)
OBJECTIVE_FOCUS: dict[str, str] = {
    "execute": (
        "Reader's goal: execute\n"
        "The reader must DO something with this document (an assignment, brief or task), not study it. Lead with"
        " what must be produced, then requirements, constraints, marking criteria, deadlines and steps. Phrase"
        " titles as tasks or requirements (e.g. \"Submit a 2,000-word report by Friday\"). Fill \"steps\""
        " whenever the content describes a process or things to do. Prefer a deadline, weighting or word/size"
        " limit found in the text for \"key_fact\". Background and explanation come last and stay brief."
        + _FOCUS_TAIL
    ),
    "learn": (
        "Reader's goal: learn\n"
        "The reader wants to understand and retain this. Foreground the concepts, the explanations and the why"
        " (the causal links the source gives), and how ideas relate. Titles name the idea or claim."
        + _FOCUS_TAIL
    ),
    "decide": (
        "Reader's goal: decide\n"
        "The reader must make a decision. Foreground the options, the trade-offs, the evidence for and against,"
        " and any stated recommendation or criteria. Titles name the option or the trade-off."
        + _FOCUS_TAIL
    ),
    "reference": (
        "Reader's goal: reference\n"
        "The reader will look things up. Foreground facts, definitions, names, values and where things are, so"
        " each piece can be found quickly. Titles name the thing a section covers."
        + _FOCUS_TAIL
    ),
    "plan": (
        "Reader's goal: plan\n"
        "The reader is planning something. Foreground dependencies, sequencing, dates, resources and constraints."
        " Fill \"steps\" when there is an order. Titles name the phase or milestone."
        + _FOCUS_TAIL
    ),
    "communicate": (
        "Reader's goal: communicate\n"
        "The reader needs to reply or respond to someone. Foreground the ask, who is asking, by when, and what"
        " is needed from the reader. Titles state the ask or the point to answer."
        + _FOCUS_TAIL
    ),
}


def with_objective(system: str, objective: str | None) -> str:
    """Append the objective's focus block to a system prompt (no-op for an
    unknown or missing objective)."""
    focus = OBJECTIVE_FOCUS.get(objective or "")
    return f"{system}\n\n{focus}" if focus else system


def with_focus(system: str, objective: str | None, genre: str | None) -> str:
    """The system prompt plus the document genre's structure (what a summary of this kind of
    document must cover) and then the reader's goal (what to emphasise inside it). Either may
    be missing or unknown; "other" has no block."""
    parts = [system]
    for block in (GENRE_FOCUS.get(genre or ""), OBJECTIVE_FOCUS.get(objective or "")):
        if block:
            parts.append(block)
    return "\n\n".join(parts)


_JSON_RETRY_NOTE = "\n\nYour previous response was not valid JSON. Respond with ONLY valid JSON, no prose, no code fences."


def _new_id(counter: list[int], span: tuple[int, int]) -> str:
    counter[0] += 1
    digest = hashlib.sha256(f"{span[0]}:{span[1]}:{counter[0]}".encode()).hexdigest()
    return "n" + digest[:10]


def _span_union(nodes: dict[str, Node], ids: list[str]) -> tuple[int, int]:
    starts = [nodes[i].source_span[0] for i in ids]
    ends = [nodes[i].source_span[1] for i in ids]
    return (min(starts), max(ends))


def _leaves_under(nodes: dict[str, Node], node_id: str) -> list[str]:
    node = nodes[node_id]
    if node.is_leaf:
        return [node_id]
    out: list[str] = []
    for child in node.children:
        out.extend(_leaves_under(nodes, child))
    return out


def _group_run(ids: list[str]) -> list[list[str]]:
    """Group a run of adjacent siblings into clusters of 2-6, avoiding a
    trailing group of size 1 where possible. A run of exactly one id
    returns a single group of size 1 (the caller decides whether that
    collapses or is force-summarised)."""
    n = len(ids)
    if n <= 1:
        return [list(ids)] if ids else []
    if n <= 6:
        return [list(ids)]
    groups: list[list[str]] = []
    i = 0
    while i < n:
        remaining = n - i
        if remaining <= 6:
            groups.append(ids[i : i + remaining])
            i = n
        else:
            take = RATIO
            if remaining - take == 1:
                take = RATIO - 1
            groups.append(ids[i : i + take])
            i += take
    return groups


def section_boundary_keys(paths: list[tuple[str, ...]]) -> list[tuple[str, ...] | None]:
    """The heading that separates sections, per leaf. Normally the top-level
    heading; but a document with one title (`# Title`) over `##` sections has
    the same first heading on every leaf, which made every boundary useless, so
    a shared leading heading is skipped and the first one that varies is used
    (`# Meeting notes` > `## 1. Data`, `## 2. Budget` ... split at the `##`)."""
    k = 0
    while paths and all(len(p) > k for p in paths) and len({p[k] for p in paths}) == 1:
        k += 1
    return [p[: k + 1] if p else None for p in paths]


def _group_leaves(ids: list[str], boundary_keys: dict[str, tuple[str, ...] | None]) -> list[list[str]]:
    """Group leaves into siblings, respecting top-level heading boundaries.
    (Boundary-respecting grouping only applies at the leaf level -- once a
    section has its own summary node, higher rounds group freely, which is
    how separate sections eventually merge toward a single root.)"""
    groups: list[list[str]] = []
    run: list[str] = []
    run_key: object = object()
    for node_id in ids:
        key = boundary_keys.get(node_id)
        if run and key != run_key:
            groups.extend(_group_run(run))
            run = []
        run_key = key
        run.append(node_id)
    if run:
        groups.extend(_group_run(run))
    return groups


def _build_prompt(nodes: dict[str, Node], child_ids: list[str]) -> tuple[str, list[str]]:
    lines = ["Children to summarise (in document order):"]
    for cid in child_ids:
        node = nodes[cid]
        lines.append(f"--- child {cid} ({node.words} words) ---")
        lines.append(node.text)

    leaf_ids: list[str] = []
    leaf_lines = ["", "Leaves under these children, for citation context:"]
    used = 0
    budget_hit = False
    for cid in child_ids:
        if budget_hit:
            break
        for leaf_id in _leaves_under(nodes, cid):
            leaf_ids.append(leaf_id)
            leaf = nodes[leaf_id]
            snippet = leaf.text
            if used + len(snippet) > LEAF_CONTEXT_CHAR_BUDGET:
                snippet = snippet[: max(0, LEAF_CONTEXT_CHAR_BUDGET - used)]
            leaf_lines.append(f"--- leaf {leaf_id} ---")
            leaf_lines.append(snippet)
            used += len(snippet)
            if used >= LEAF_CONTEXT_CHAR_BUDGET:
                budget_hit = True
                break

    lines.extend(leaf_lines)
    lines.append("")
    lines.append(f"Child ids (in order): {', '.join(child_ids)}")
    lines.append(f"Leaf ids you may cite (in order): {', '.join(leaf_ids)}")
    return "\n".join(lines), leaf_ids


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def _cap_chars(text: str, max_chars: int) -> str:
    """Cut to max_chars, at a word boundary when there is one."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    space = cut.rfind(" ")
    return (cut[:space] if space > max_chars // 2 else cut).rstrip(" ,;:-–")


_DANGLING = {
    "a", "an", "the", "of", "to", "by", "in", "on", "at", "for", "and", "or", "with", "from",
    "as", "than", "that", "into", "via", "per", "is", "are", "be", "before", "after",
}


def _truncate_title(text: str, max_words: int = 8) -> str:
    """Cut a title to max_words without leaving a dangling tail: a cut such as
    "Submit as one PDF by 5 pm, 14" drops the "14" (and stray connectives and
    commas) rather than ending on half a date. Untouched when already short."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    kept = words[:max_words]
    while len(kept) > 2 and (kept[-1].strip(",;:-–").lower() in _DANGLING or kept[-1].strip(",;:.").isdigit()):
        kept.pop()
    return " ".join(kept).rstrip(" ,;:-–")


def _clean_title(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _cap_chars(_truncate_title(raw.strip(), TITLE_MAX_WORDS), TITLE_MAX_CHARS)


def _clean_short_title(raw: object) -> str | None:
    """At most 3 words and 24 characters, else dropped (not truncated: a cut
    label reads worse than the ellipsis fallback)."""
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or len(s.split()) > SHORT_TITLE_MAX_WORDS or len(s) > SHORT_TITLE_MAX_CHARS:
        return None
    return s


def _clean_child_short_titles(raw: object, valid_child_ids: list[str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    valid = set(valid_child_ids)
    out: dict[str, str] = {}
    for child_id, t in raw.items():
        cleaned = _clean_short_title(t) if child_id in valid else None
        if cleaned:
            out[child_id] = cleaned
    return out


SHORT_TITLE_BACKFILL_SYSTEM = (
    "You label the parts of a document for a small map. For each node id you are given, return a short key "
    "phrase (at most 3 words and 24 characters) that names what the part is about. It must be a meaningful "
    "phrase, not the first words of the title cut off, and not a sentence. Reply with JSON only: an object "
    "mapping each node id to its label."
)
SHORT_TITLE_BACKFILL_MAX_NODES = 400


def nodes_missing_short_title(tree: Tree) -> list[str]:
    """Ids from the section level down (document order) with no short_title."""
    top = [i for i in (tree.sections or []) if i in tree.nodes]
    if not top and tree.root in tree.nodes:
        root = tree.nodes[tree.root]
        top = [c for c in root.children if c in tree.nodes] or [tree.root]
    out: list[str] = []

    def visit(node_id: str) -> None:
        node = tree.nodes.get(node_id)
        if node is None:
            return
        if not node.short_title:
            out.append(node_id)
        for c in node.children:
            visit(c)

    for i in top:
        visit(i)
    return out


def short_titles_below_sections(tree: Tree) -> dict[str, str]:
    """{id: short_title} for every node from the section level down that has one."""
    have = set(nodes_missing_short_title(tree))
    top = [i for i in (tree.sections or []) if i in tree.nodes]
    seen: dict[str, str] = {}

    def visit(node_id: str) -> None:
        node = tree.nodes.get(node_id)
        if node is None:
            return
        if node.short_title and node_id not in have:
            seen[node_id] = node.short_title
        for c in node.children:
            visit(c)

    for i in top or [tree.root]:
        visit(i)
    return seen


async def backfill_short_titles(tree: Tree, summariser: Summariser) -> dict[str, str]:
    """One batched model call for every node (section level down) that lacks a
    short_title. Validates each label with _clean_short_title and writes the
    valid ones onto the tree in place. Returns the labels that were added."""
    ids = nodes_missing_short_title(tree)[:SHORT_TITLE_BACKFILL_MAX_NODES]
    if not ids:
        return {}
    lines = []
    for i in ids:
        n = tree.nodes[i]
        title = n.title or " ".join(n.text.split()[:12])
        excerpt = " ".join((n.hook or n.text).split())[:140]
        lines.append(f"- {i} | title: {title} | about: {excerpt}")
    prompt = "Short-title node ids: " + ", ".join(ids) + "\n\nNodes:\n" + "\n".join(lines)
    result = await _call_summariser_json(summariser, prompt, SHORT_TITLE_BACKFILL_SYSTEM)
    if isinstance(result.get("titles"), dict):
        result = result["titles"]
    added: dict[str, str] = {}
    for i in ids:
        cleaned = _clean_short_title(result.get(i))
        if cleaned:
            tree.nodes[i].short_title = cleaned
            added[i] = cleaned
    return added


def _clean_hook(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _cap_chars(_truncate_words(raw.strip(), HOOK_MAX_WORDS), HOOK_MAX_CHARS)


def _clean_key_points(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        out.append(_cap_chars(_truncate_words(item.strip(), KEY_POINT_MAX_WORDS), POINT_MAX_CHARS))
        if len(out) >= KEY_POINTS_MAX_ITEMS:
            break
    return out


def _clean_steps(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    steps = [item.strip() for item in raw if isinstance(item, str) and item.strip()]
    return [_cap_chars(_truncate_words(x, STEP_MAX_WORDS), POINT_MAX_CHARS) for x in steps[:STEPS_MAX_ITEMS]]


def _clean_child_titles(raw: object, valid_child_ids: list[str]) -> dict[str, str]:
    """child_titles keys must be actual child ids (deterministic validation)."""
    if not isinstance(raw, dict):
        return {}
    valid = set(valid_child_ids)
    out: dict[str, str] = {}
    for child_id, title in raw.items():
        if child_id not in valid or not isinstance(title, str) or not title.strip():
            continue
        out[child_id] = _cap_chars(_truncate_title(title.strip(), TITLE_MAX_WORDS), TITLE_MAX_CHARS)
    return out


def _number_tokens(text: str) -> list[str]:
    return _NUMBER_TOKEN_RE.findall(text or "")


def _strip_thousands(s: str) -> str:
    return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)


_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_NUMBER_WORDS_TENS = {30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}


def _number_word(n: int) -> str | None:
    """The English word for 0-20 and the round tens up to 90 ("three", "forty"), else None."""
    if 0 <= n <= 20:
        return _NUMBER_WORDS[n]
    return _NUMBER_WORDS_TENS.get(n)


def _number_in_source(token: str, source_lower: str) -> bool:
    """Is this number token in the source as a whole number? A plain substring
    test let "5" pass against "25%" and "20" against "2025"; a match must not
    start or end inside a longer number. Thousands commas are ignored. A small
    number may be written as a word in the source ("3 offices" for "three offices")."""
    tok = token.lower().rstrip(".,")
    if not tok:
        return True
    if not tok[0].isdigit():  # "billion", "million"
        return re.search(rf"\b{re.escape(tok)}\b", source_lower) is not None
    pattern = r"(?<![\w.,])" + re.escape(_strip_thousands(tok)) + r"(?!\d|[.,]\d)"
    if re.search(pattern, _strip_thousands(source_lower)) is not None:
        return True
    if tok.isdigit() and (word := _number_word(int(tok))) is not None:
        return re.search(rf"\b{word}\b", source_lower) is not None
    return False


def _prose_numbers(text: str) -> list[str]:
    """Number-like tokens of a sentence, minus the sentence punctuation the
    token regex swallows ("2," "2025." -> "2" "2025")."""
    return [t.rstrip(".,") for t in _number_tokens(text) if t.rstrip(".,")]


# A cited item must share at least this share of its content words with the leaves it cites. Tuned on the
# cached trees: every real essential and key fact scores 0.43 or more, a random other leaf of the same
# document scores below 0.35 for about 94% of items (see docs/overview-spec.md, "Faithfulness checks").
CITE_OVERLAP_FLOOR = 0.35

Warn = Callable[[str, str, dict], None]


def log_warning(kind: str, where: str, detail: dict) -> None:
    """The default sink for non-fatal checks: the Python logger (the build also records them in its history)."""
    short = {k: (v[:160] if isinstance(v, str) else v) for k, v in detail.items()}
    logging.getLogger("riemann").warning("%s in %s: %s", kind, where, short)


def _dropped(what: str, reason: str) -> None:
    """Debug trail for an item a check removed (INFO, so a normal run stays quiet)."""
    logging.getLogger("riemann").info("dropped %s: %s", what, reason)


def _warn_dropped_qualifier(warn: Warn | None, where: str, item_text: str, cited_text: str) -> None:
    """Log only: the cited source sentence says "not", "unless", "except" ... and the item does not."""
    if warn is None:
        return
    found = checks.qualifier_dropped(item_text, cited_text)
    if found:
        warn("qualifier_dropped", where, {"qualifier": found[0], "sentence": found[1][:300], "item": item_text[:300]})


def _supported(text: str, source: str) -> bool:
    """Numbers, weekday names and month names in `text` all appear in `source`."""
    low = source.lower()
    return all(_number_in_source(tok, low) for tok in _prose_numbers(text)) and checks.dates_ok(text, source)


def _validate_key_fact(raw: object, nodes: dict[str, Node], leaf_ctx_ids: list[str], warn: Warn | None = None) -> KeyFact | None:
    """Deterministic validation: every number-like token in big/detail must
    appear in the text of the cited leaves, weekday and month names too, and
    the fact must share content words with them, or the whole KeyFact is dropped."""
    if not isinstance(raw, dict):
        return None
    big = raw.get("big")
    detail = raw.get("detail")
    if not isinstance(big, str) or not big.strip() or not isinstance(detail, str) or not detail.strip():
        return None
    big = _cap_chars(_truncate_words(big.strip(), KEY_FACT_BIG_MAX_WORDS), TITLE_MAX_CHARS)
    detail = _cap_chars(_truncate_words(detail.strip(), KEY_FACT_DETAIL_MAX_WORDS), POINT_MAX_CHARS)

    cites_raw = raw.get("cites")
    cites = [c for c in cites_raw if isinstance(c, str) and c in leaf_ctx_ids] if isinstance(cites_raw, list) else []
    if not cites:  # a key fact must point at the source it came from
        return None
    source_text = " ".join(nodes[c].text for c in cites if c in nodes)

    for token in _number_tokens(big) + _number_tokens(detail):
        if not _number_in_source(token, source_text.lower()):
            _dropped(f"key fact {big!r}", f"number {token!r} is not in the cited leaves")
            return None
    if not checks.dates_ok(f"{big} {detail}", source_text):
        _dropped(f"key fact {big!r}", "weekday or month not in the cited leaves")
        return None
    if not checks.overlap_ok(f"{big} {detail}", source_text, CITE_OVERLAP_FLOOR):
        _dropped(f"key fact {big!r}", "too few words shared with the cited leaves")
        return None
    _warn_dropped_qualifier(warn, f"key fact {big}", f"{big} {detail}", source_text)

    return KeyFact(big=big, detail=detail, cites=cites)


def _provisional_prompt(source_text: str, title: str) -> str:
    truncated = head_words(source_text, 3000)
    headings = [ln.strip() for ln in source_text.splitlines() if ln.strip().startswith("#")]
    parts = [f"Title: {title}", "", truncated]
    if headings:
        parts.append("")
        parts.append("Headings:")
        parts.extend(headings[:30])
    return "\n".join(parts)


async def _call_json(summariser: Summariser, prompt: str, system: str) -> dict | None:
    raw = await summariser.summarise(prompt, system)
    try:
        return parse_json_robustly(raw)
    except Exception:
        return None


async def _call_summariser_json(summariser: Summariser, prompt: str, system: str) -> dict:
    """Parse JSON robustly (strip code fences); retry once on bad JSON."""
    result = await _call_json(summariser, prompt, system)
    if result is not None:
        return result
    result = await _call_json(summariser, prompt + _JSON_RETRY_NOTE, system)
    if result is not None:
        return result
    raise ModelError(
        "The model did not return a usable reply (it was not the JSON Riemann asked for), even after a second try. "
        "Try building again, or pick a different model."
    )


# ---------------------------------------------------------------------------
# Overview card: "what is this" + the few essentials, above section 01
# ---------------------------------------------------------------------------
OVERVIEW_TITLE_MAX_WORDS = 16
OVERVIEW_KIND_MAX_WORDS = 4
OVERVIEW_WHAT_MAX_WORDS = 45
ESSENTIALS_MIN = 3
ESSENTIALS_MAX = 7
ESSENTIAL_LABEL_MAX_WORDS = 5
ESSENTIAL_VALUE_MAX_WORDS = 30  # shown in full, never clamped; keep in step with the prompt
OVERVIEW_LEAF_WORD_BUDGET = 4000
OVERVIEW_SECTION_TEXT_WORDS = 90

OVERVIEW_SYSTEM = """You write the "what is this" card that sits above a document in a reading app, so a reader who reads nothing else still knows what the document is and its key facts.
Respond with ONLY JSON, no prose outside it and no markdown code fences:
{"doc_title": "...", "doc_kind": "...", "what_it_is": "...",
 "essentials": [{"label": "...", "value": "...", "cites": ["leaf_id", ...]}]}

"doc_title": the document's OWN name, as its author would title it (e.g. "MMA3001 Individual Project brief: Numerical Methods and Machine Learning"). Take it from the source's heading, header or first lines; never a summary sentence. At most 16 words.
"doc_kind": what kind of document it is, in 1-4 words (e.g. "Assignment brief", "Research paper", "Meeting notes", "Email thread", "Article", "Policy", "Contract").
"what_it_is": ONE plain sentence saying what it is and who it is for or what it is about (e.g. "This is the brief for your individual MMA3001 project, worth 25% of the unit."). No more than 45 words.
"essentials": 3 to 7 items, each a short "label" (1-5 words) and a "value" (a tight phrase or a short imperative list, ideally under 15 words and never more than 30; it is shown in full, so keep it short: names, dates, numbers, not clauses). Choose the labels for THIS kind of document and this reader's goal, the things they would want to see at a glance. Examples by kind:
- assignment or task: Deliverables, Due, Weight, Submit how, What you need to do, Assessed on
- paper or article: Main claim, Evidence, Limits
- decision: Options, Recommendation, Deadline
- plan: Milestones, Next action, Dependencies
- email or message: The ask, From, Reply by
- reference or guide: Covers, Key rules, Where to look
Every value must come from the source. Never invent or guess: if the source does not say (for example no due date is given), write exactly "not stated" for that value and leave its cites empty. Copy numbers, dates, weekday and month names and people's names exactly as the source writes them.
"cites": leaf ids only, from the "Leaf ids you may cite" list, naming the leaves the value comes from. Every number, weekday and month in a value must appear in a cited leaf, and the value must be in words the cited leaves use."""

GENRE_REQUEST = """Also add "genre": one of assignment, paper, news, email, meeting, legal, technical, article, other (the kind of document this is)."""

# What the reader's goal makes the most useful essentials (appended to the
# overview prompt after the OBJECTIVE_FOCUS block).
OVERVIEW_ESSENTIALS: dict[str, str] = {
    "execute": "For this reader, prefer essentials like: Deliverables, Due, Weight, Submit how, What you need to do (a short imperative list is fine as the value), Assessed on.",
    "learn": "For this reader, prefer essentials like: Main idea, Key concepts, Why it matters, Prerequisites.",
    "decide": "For this reader, prefer essentials like: The decision, Options, Recommendation, Deadline, Criteria.",
    "reference": "For this reader, prefer essentials like: Covers, Key rules or values, Where to look, Applies to.",
    "plan": "For this reader, prefer essentials like: Milestones, Next action, Dependencies, Dates, Owners.",
    "communicate": "For this reader, prefer essentials like: The ask, From, Reply by, What is needed from you.",
}



def _essentials_hint(genre: str | None, objective: str | None) -> str:
    """The essentials hint for the overview prompt: the genre's first, then the reader's goal's."""
    genre_hint = GENRE_ESSENTIALS.get(genre or "")
    goal_hint = OVERVIEW_ESSENTIALS.get(objective or "")
    if genre_hint and goal_hint:
        return genre_hint + "\n" + goal_hint.replace("For this reader, prefer", "For this reader's goal, also consider")
    return genre_hint or goal_hint or ""


def _overview_system(tree: Tree) -> str:
    genre = tree.genre
    system = OVERVIEW_SYSTEM
    if genre is None:
        system += "\n\n" + GENRE_REQUEST
    system = with_focus(system, tree.objective, genre)
    hint = _essentials_hint(genre, tree.objective)
    return f"{system}\n\n{hint}" if hint else system


def _leaf_ids_in_order(tree: Tree) -> list[str]:
    if tree.root not in tree.nodes:
        return []
    return _leaves_under(tree.nodes, tree.root)


def _overview_prompt(tree: Tree) -> tuple[str, list[str]]:
    """The overview call's prompt: the root and section summaries, then the
    source's leaves in order (up to ~4000 words) with their ids for citation."""
    nodes = tree.nodes
    root = nodes[tree.root]
    lines = ["Task: overview", f"Document title (as extracted): {tree.title}", "", "Top-level summary:", root.text, ""]
    secs = [s for s in (tree.sections or []) if s in nodes]
    if secs:
        lines.append("Sections:")
        for sid in secs:
            n = nodes[sid]
            body = " ".join(n.text.split()[:OVERVIEW_SECTION_TEXT_WORDS])
            lines.append(f"- {n.title or 'section'} (cites: {', '.join(n.cites[:6])}): {body}")
        lines.append("")
    lines.append("Source, in order:")
    shown: list[str] = []
    used = 0
    for lid in _leaf_ids_in_order(tree):
        leaf = nodes[lid]
        if used and used + leaf.words > OVERVIEW_LEAF_WORD_BUDGET:
            break
        lines.append(f"--- leaf {lid} ---")
        lines.append(leaf.text)
        shown.append(lid)
        used += leaf.words
    lines.append("")
    lines.append(f"Leaf ids you may cite (in order): {', '.join(shown)}")
    return "\n".join(lines), shown


_NOT_STATED_RE = re.compile(r"^\s*not stated\b", re.I)


def _clean_essentials(raw: object, nodes: dict[str, Node], all_leaf_ids: set[str], warn: Warn | None = None) -> list[Essential]:
    """Deterministic validation: drop an item with no label/value, a duplicate
    label, or a value with a number, weekday or month that is not in its cited
    leaves (cites must be real leaf ids), or one that shares too few content
    words with them. "not stated" needs no cites and is not checked. A dropped
    negation or exception is only reported (`warn`)."""
    if not isinstance(raw, list):
        return []
    out: list[Essential] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        label, value = item.get("label"), item.get("value")
        if not isinstance(label, str) or not label.strip() or not isinstance(value, str) or not value.strip():
            continue
        label = _cap_chars(_truncate_words(label.strip().rstrip(":"), ESSENTIAL_LABEL_MAX_WORDS), TITLE_MAX_CHARS)
        value = _cap_chars(_truncate_words(value.strip(), ESSENTIAL_VALUE_MAX_WORDS), 600)
        if label.lower() in seen:
            continue
        cites_raw = item.get("cites")
        cites = [c for c in cites_raw if isinstance(c, str) and c in all_leaf_ids] if isinstance(cites_raw, list) else []
        source = " ".join(nodes[c].text for c in cites)
        if not _supported(value, source):
            _dropped(f"essential {label!r}", "a number, weekday or month is not in the cited leaves")
            continue
        if cites and not _NOT_STATED_RE.match(value):
            if not checks.overlap_ok(value, source, CITE_OVERLAP_FLOOR):
                _dropped(f"essential {label!r}", "too few words shared with the cited leaves")
                continue
            _warn_dropped_qualifier(warn, f"essential {label}", f"{label}: {value}", source)
        seen.add(label.lower())
        out.append(Essential(label=label, value=value, cites=cites))
        if len(out) >= ESSENTIALS_MAX:
            break
    return out


def _clean_overview(raw: object, tree: Tree, warn: Warn | None = None) -> Overview | None:
    if not isinstance(raw, dict):
        return None
    doc_title = raw.get("doc_title")
    doc_kind = raw.get("doc_kind")
    what = raw.get("what_it_is")
    if not isinstance(doc_title, str) or not doc_title.strip() or not isinstance(doc_kind, str) or not doc_kind.strip():
        return None
    doc_title = _cap_chars(_truncate_words(doc_title.strip(), OVERVIEW_TITLE_MAX_WORDS), 200)
    doc_kind = _cap_chars(_truncate_words(doc_kind.strip().rstrip("."), OVERVIEW_KIND_MAX_WORDS), 40)
    source_lower = tree.source_text.lower()
    what_ok = (
        isinstance(what, str)
        and what.strip()
        and all(_number_in_source(t, source_lower) for t in _prose_numbers(what))
        and checks.dates_ok(what, tree.source_text)
    )
    if what_ok:
        what = _cap_chars(_truncate_words(what.strip(), OVERVIEW_WHAT_MAX_WORDS), 400)
    else:
        article = "an" if doc_kind[:1].lower() in "aeiou" else "a"
        what = f"This is {article} {doc_kind[:1].lower() + doc_kind[1:]}."
    if tree.genre is None:  # an older tree: the model's answer (or "other") settles it
        tree.genre = valid_genre(raw.get("genre")) or "other"
    all_leaf_ids = {i for i in _leaf_ids_in_order(tree)}
    essentials = _clean_essentials(raw.get("essentials"), tree.nodes, all_leaf_ids, warn)
    return Overview(
        doc_title=doc_title,
        doc_kind=doc_kind,
        what_it_is=what,
        essentials=essentials,
    )


async def generate_overview(tree: Tree, summariser: Summariser, warn: Warn | None = None) -> Overview | None:
    """One model call (root/section summaries + the source's first ~4000 words
    with leaf ids) for the overview card; validated deterministically. None if
    the tree has no internal structure or the reply is unusable. A tree with no
    genre yet (built before genre detection) gets one here: the cue words first,
    then the model's answer."""
    if tree.root not in tree.nodes or tree.nodes[tree.root].is_leaf:
        return None
    if tree.genre is None:
        guessed, strong = detect_genre(tree.title, tree.source_text)
        if strong:
            tree.genre = guessed
    prompt, _shown = _overview_prompt(tree)
    result = await _call_summariser_json(summariser, prompt, _overview_system(tree))
    return _clean_overview(result, tree, warn=warn if warn is not None else log_warning)


class TreeBuilder:
    """Holds one tree's live build state and fans out its events to any
    number of SSE subscribers (a new subscriber first replays history)."""

    def __init__(self, tree: Tree) -> None:
        self.tree = tree
        self.history: list[tuple[str, dict]] = []
        self._subscribers: list[asyncio.Queue] = []
        self.task: asyncio.Task | None = None

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        for name, data in self.history:
            queue.put_nowait((name, data))
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def _emit(self, name: str, data: dict) -> None:
        self.history.append((name, data))
        for queue in list(self._subscribers):
            await queue.put((name, data))


async def _emit_warning(builder: TreeBuilder, kind: str, where: str, detail: dict) -> None:
    """A non-fatal finding of a faithfulness check: logged, and recorded in the build's history as a
    "warning" event ({kind, where, ...detail}). It never stops the build and nothing is dropped for it."""
    log_warning(kind, where, detail)
    await builder._emit("warning", {"kind": kind, "where": where, **detail})


BUILDS: dict[str, TreeBuilder] = {}


def get_builder(tree_id: str) -> TreeBuilder | None:
    return BUILDS.get(tree_id)


def start_build(
    tree_id: str, title: str, source_text: str, summariser: Summariser, objective: str | None = None
) -> TreeBuilder:
    """Create a Tree + TreeBuilder and schedule the background build task."""
    tree = Tree(
        id=tree_id,
        title=title,
        source_text=source_text,
        source_words=word_count(source_text),
        root="",
        nodes={},
        max_depth=0,
        status="building",
        provisional_root=False,
        objective=objective if objective in OBJECTIVE_FOCUS else None,
    )
    builder = TreeBuilder(tree)
    BUILDS[tree_id] = builder
    builder.task = asyncio.ensure_future(_run_build(builder, summariser))
    return builder


async def _run_build(builder: TreeBuilder, summariser: Summariser) -> None:
    tree = builder.tree
    try:
        await _run_build_inner(builder, summariser)
    except Exception as exc:  # noqa: BLE001 - surfaced to clients via the error event
        tree.status = "error"
        if isinstance(exc, ModelError):
            message = str(exc)
        else:
            logging.getLogger("riemann").exception("build failed")
            message = f"Something went wrong while building ({type(exc).__name__}). Nothing was saved; try again."
        await builder._emit("error", {"message": message})


async def _run_build_inner(builder: TreeBuilder, summariser: Summariser) -> None:
    tree = builder.tree
    source_text = tree.source_text

    leaves = chunk(source_text)

    if word_count(source_text) <= TINY_DOC_WORDS or len(leaves) == 1 and word_count(leaves[0].text) <= GIST_WORDS:
        leaf = leaves[0]
        counter = [0]
        nid = _new_id(counter, leaf.source_span)
        node = Node(
            id=nid,
            depth=0,
            text=leaf.text,
            words=leaf.words,
            children=[],
            parent=None,
            is_leaf=True,
            source_span=leaf.source_span,
            cites=[],
            importance=1.0,
            atomic=leaf.atomic,
        )
        tree.nodes = {nid: node}
        tree.root = nid
        tree.max_depth = 0
        tree.status = "done"
        tree.provisional_root = False
        tree.genre = detect_genre(tree.title, source_text)[0] or "other"
        await builder._emit("leaves", {"nodes": [node.model_dump()]})
        await builder._emit("done", {"tree": tree.model_dump()})
        _save(tree)
        return

    nodes: dict[str, Node] = {}
    counter = [0]
    leaf_ids: list[str] = []
    boundary_keys: dict[str, tuple[str, ...] | None] = {}
    keys = section_boundary_keys([leaf.heading_path for leaf in leaves])
    for leaf, key in zip(leaves, keys):
        nid = _new_id(counter, leaf.source_span)
        node = Node(
            id=nid,
            depth=0,
            text=leaf.text,
            words=leaf.words,
            children=[],
            parent=None,
            is_leaf=True,
            source_span=leaf.source_span,
            cites=[],
            importance=0.5,
            atomic=leaf.atomic,
        )
        nodes[nid] = node
        leaf_ids.append(nid)
        boundary_keys[nid] = key

    tree.nodes = nodes
    await builder._emit(
        "leaves",
        {"nodes": [nodes[i].model_dump() for i in leaf_ids], "source_words": tree.source_words},
    )

    # 1. Fast provisional root. Its model call runs alongside the first layer
    # (it does not depend on it); the event is still emitted before any `level`
    # event, because every level emit awaits `ensure_provisional()` first.
    #
    # The same call also names the document's genre. When the cue words already
    # agree on one (a strong heuristic) the genre is known now and steers every
    # call. Otherwise the first layer does not wait for it (that would undo the
    # overlap): its calls carry no genre block; every later layer, the root and
    # the overview use the model's answer, since a level is only emitted after
    # the gist call has returned.
    prov_id = _new_id(counter, (0, len(source_text)))
    guessed, strong = detect_genre(tree.title, source_text)
    genre_known = asyncio.Event()
    if strong:
        tree.genre = guessed
        genre_known.set()

    async def make_provisional() -> None:
        try:
            prov_prompt = _provisional_prompt(source_text, tree.title)
            prov_result = await _call_summariser_json(
                summariser, prov_prompt, with_focus(SYSTEM_PROVISIONAL, tree.objective, tree.genre)
            )
            if not strong:
                tree.genre = valid_genre(prov_result.get("genre")) or guessed or "other"
        finally:
            genre_known.set()
        raw_prov = prov_result.get("text")
        prov_text = raw_prov.strip() if isinstance(raw_prov, str) else ""
        prov_text = _cap_chars(_truncate_words(prov_text, 80), 600) or "(gist coming...)"
        prov_node = Node(
            id=prov_id,
            depth=0,
            text=prov_text,
            words=word_count(prov_text),
            children=[],
            parent=None,
            is_leaf=False,
            source_span=(0, len(source_text)),
            cites=[],
            importance=1.0,
            atomic=False,
        )
        tree.nodes[prov_id] = prov_node
        tree.root = prov_id
        tree.provisional_root = True
        await builder._emit("provisional_root", {"node": prov_node.model_dump()})

    prov_task = asyncio.ensure_future(make_provisional())

    async def ensure_provisional() -> None:
        await prov_task

    try:
        await _build_levels(
            builder, summariser, leaf_ids, boundary_keys, counter, prov_id, ensure_provisional, genre_known.wait
        )
    finally:
        if not prov_task.done():
            prov_task.cancel()
            await asyncio.gather(prov_task, return_exceptions=True)


async def _build_levels(
    builder: TreeBuilder,
    summariser: Summariser,
    leaf_ids: list[str],
    boundary_keys: dict[str, tuple[str, ...] | None],
    counter: list[int],
    prov_id: str,
    ensure_provisional,
    genre_known,
) -> None:
    tree = builder.tree
    nodes = tree.nodes

    # 2. Bottom-up build.
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def process_group(group_ids: list[str], is_root_call: bool, force: bool) -> tuple[str, Node | None]:
        if len(group_ids) == 1 and not force:
            return group_ids[0], None  # collapse: carried up unsummarised

        if is_root_call:
            await genre_known()  # the root summary always has the final genre; earlier calls never wait for it
        async with sem:
            child_words = sum(nodes[c].words for c in group_ids)
            target = max(1, round(child_words / RATIO))
            system_template = SYSTEM_ROOT_TEMPLATE if is_root_call else SYSTEM_SUMMARY_TEMPLATE
            system = with_focus(system_template.replace("{{TARGET}}", str(target)), tree.objective, tree.genre)
            prompt, leaf_ctx_ids = _build_prompt(nodes, group_ids)

            result = await _call_summariser_json(summariser, prompt, system)
            raw_text = result.get("text")
            text = raw_text.strip() if isinstance(raw_text, str) else ""
            words = word_count(text)

            if target > 0 and words > 0 and abs(words - target) / target > LENGTH_TOLERANCE:
                delta = target - words
                retry_prompt = (
                    prompt
                    + f"\n\nYour previous answer was {words} words; aim closer to {target} words"
                    f" ({'+' if delta > 0 else ''}{delta})."
                )
                retried = await _call_json(summariser, retry_prompt, system)
                if retried is not None:
                    result = retried
                    retried_text = result.get("text")
                    text = (retried_text.strip() if isinstance(retried_text, str) else "") or text
                    words = word_count(text)

            if not text:
                text = " ".join(nodes[c].text for c in group_ids)[:200]
            text = _cap_chars(_truncate_words(text, min(TEXT_MAX_WORDS, max(60, 3 * target))), 6 * TEXT_MAX_WORDS)
            words = word_count(text)

            cites_raw = result.get("cites")
            cites = [c for c in cites_raw if isinstance(c, str) and c in leaf_ctx_ids] if isinstance(cites_raw, list) else []
            importance_map = result.get("importance") if isinstance(result.get("importance"), dict) else {}

            title = _clean_title(result.get("title"))
            short_title = _clean_short_title(result.get("short_title"))
            hook = _clean_hook(result.get("hook"))
            key_points = _clean_key_points(result.get("key_points"))
            steps = _clean_steps(result.get("steps"))
            node_warnings: list[tuple[str, str, dict]] = []
            key_fact = _validate_key_fact(result.get("key_fact"), nodes, leaf_ctx_ids, warn=lambda *w: node_warnings.append(w))
            child_titles = _clean_child_titles(result.get("child_titles"), group_ids)
            child_short = _clean_child_short_titles(result.get("child_short_titles"), group_ids)

            span = _span_union(nodes, group_ids)
            nid = _new_id(counter, span)
            parent = Node(
                id=nid,
                depth=0,
                text=text,
                words=words,
                children=list(group_ids),
                parent=None,
                is_leaf=False,
                source_span=span,
                cites=cites,
                importance=1.0,
                atomic=False,
                title=title,
                short_title=short_title,
                hook=hook,
                key_points=key_points,
                key_fact=key_fact,
                steps=steps,
            )
            nodes[nid] = parent
            for kind, where, detail in node_warnings:
                await _emit_warning(builder, kind, where, detail)
            for cid in group_ids:
                nodes[cid].parent = nid
                if cid in importance_map:
                    try:
                        nodes[cid].importance = max(0.0, min(1.0, float(importance_map[cid])))
                    except (TypeError, ValueError):
                        pass
                if cid in child_titles:
                    nodes[cid].title = child_titles[cid]
                if cid in child_short:
                    nodes[cid].short_title = child_short[cid]
            return nid, parent

    current_level = list(leaf_ids)
    height = 0
    final_root_id: str | None = None

    for _ in range(MAX_BUILD_ROUNDS):
        if len(current_level) == 1:
            only = current_level[0]
            if word_count(nodes[only].text) <= GIST_STOP_WORDS:
                final_root_id = only
                break
            nid, parent = await process_group([only], is_root_call=True, force=True)
            if parent is not None:
                await ensure_provisional()
                await builder._emit("level", {"nodes": [parent.model_dump()], "height": height + 1})
            current_level = [nid]
            height += 1
            final_root_id = nid
            if word_count(nodes[nid].text) <= GIST_STOP_WORDS:
                break
            continue

        groups = _group_leaves(current_level, boundary_keys) if height == 0 else _group_run(current_level)
        is_final_round = len(groups) == 1

        tasks = [
            asyncio.ensure_future(process_group(group, is_root_call=is_final_round, force=False))
            for group in groups
        ]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            # One group failed: stop the rest now. gather() alone leaves its
            # siblings running, spending model calls on a build that is over.
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        new_level = [nid for nid, _ in results]
        new_nodes = [node for _, node in results if node is not None]
        if new_nodes:
            await ensure_provisional()
            await builder._emit("level", {"nodes": [n.model_dump() for n in new_nodes], "height": height + 1})

        current_level = new_level
        height += 1

        if len(current_level) == 1 and word_count(nodes[current_level[0]].text) <= GIST_STOP_WORDS:
            final_root_id = current_level[0]
            break

    if final_root_id is None:
        final_root_id = current_level[0]

    await ensure_provisional()

    # 3. Finalise: real root replaces the provisional one; depths via DFS
    # from the root (this is what makes the tree ragged -- a branch that
    # collapsed through fewer real levels ends up shallower).
    nodes[final_root_id].parent = None
    nodes[final_root_id].importance = 1.0
    tree.root = final_root_id
    tree.provisional_root = False

    if prov_id in nodes and prov_id != final_root_id:
        del nodes[prov_id]

    def assign_depth(node_id: str, depth: int) -> None:
        nodes[node_id].depth = depth
        for child_id in nodes[node_id].children:
            assign_depth(child_id, depth + 1)

    collapse_single_child_chains(nodes, final_root_id)
    assign_depth(final_root_id, 0)
    tree.nodes = nodes
    tree.max_depth = max(n.depth for n in nodes.values())
    tree.sections = compute_sections(tree)

    # The overview is part of "done": anything polling the tree's status must
    # not see a finished tree that is about to gain its card.
    overview_warnings: list[tuple[str, str, dict]] = []
    try:
        tree.overview = await generate_overview(tree, summariser, warn=lambda *w: overview_warnings.append(w))
    except Exception as exc:  # noqa: BLE001 - the reader backfills the overview on open
        logging.getLogger("riemann").warning("overview generation failed: %s", type(exc).__name__)
        tree.overview = None
    for kind, where, detail in overview_warnings:
        await _emit_warning(builder, kind, where, detail)
    tree.status = "done"

    _save(tree)
    await builder._emit("done", {"tree": tree.model_dump()})


def collapse_single_child_chains(nodes: dict[str, Node], root_id: str) -> None:
    """Never keep a pass-through level. An internal node with exactly one
    internal child absorbs it (takes over its children, keeps its own summary
    fields), repeatedly; a non-root internal node left with a single leaf child
    is replaced by that leaf. Such chains come from the forced summarising of a
    lone remaining node (root over one node over one node ...), and only make
    the first zoom steps reword the same paragraph. Mutates `nodes` in place."""

    def collapse(nid: str) -> None:
        node = nodes[nid]
        if node.is_leaf:
            return
        while len(node.children) == 1 and not nodes[node.children[0]].is_leaf:
            child = nodes.pop(node.children[0])
            node.children = list(child.children)
            for cid in node.children:
                nodes[cid].parent = nid
        for cid in list(node.children):
            collapse(cid)
        # a child that ended up with a single leaf child is replaced by that leaf
        new_children: list[str] = []
        for cid in node.children:
            c = nodes[cid]
            if not c.is_leaf and len(c.children) == 1:
                leaf = nodes[c.children[0]]
                leaf.parent = nid
                leaf.importance = c.importance
                leaf.title = leaf.title or c.title
                leaf.short_title = leaf.short_title or c.short_title
                del nodes[cid]
                new_children.append(leaf.id)
            else:
                new_children.append(cid)
        node.children = new_children

    collapse(root_id)


def compute_sections(tree: Tree) -> list[str]:
    """Node ids at the section level: the first depth from the root (depth
    >= 1) that has >=2 nodes, in document order. Empty for a single-leaf
    tree, or for a tree that never branches (a straight chain from root to
    one leaf, so no depth ever reaches 2 nodes)."""
    if tree.root not in tree.nodes:
        return []

    by_depth: dict[int, list[str]] = {}

    def visit(node_id: str) -> None:
        node = tree.nodes[node_id]
        by_depth.setdefault(node.depth, []).append(node_id)
        for child_id in node.children:
            if child_id in tree.nodes:
                visit(child_id)

    visit(tree.root)
    if not by_depth:
        return []
    for depth in range(1, max(by_depth) + 1):
        candidates = by_depth.get(depth, [])
        if len(candidates) >= 2:
            return candidates
    return []


def _save(tree: Tree) -> None:
    from riemann.abstraction.cache import save_tree

    save_tree(tree)
