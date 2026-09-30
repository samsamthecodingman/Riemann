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
import re

from riemann.abstraction.chunk import TINY_DOC_WORDS, chunk, word_count
from riemann.abstraction.model import KeyFact, Node, Tree
from riemann.abstraction.summarise import Summariser, parse_json_robustly

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
Respond with ONLY JSON, no prose outside it and no markdown code fences: {"text": "..."}"""

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


def _group_leaves(ids: list[str], boundary_keys: dict[str, str | None]) -> list[list[str]]:
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


def _clean_title(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _truncate_words(raw.strip(), TITLE_MAX_WORDS)


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


def _clean_hook(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _truncate_words(raw.strip(), HOOK_MAX_WORDS)


def _clean_key_points(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        out.append(_truncate_words(item.strip(), KEY_POINT_MAX_WORDS))
        if len(out) >= KEY_POINTS_MAX_ITEMS:
            break
    return out


def _clean_steps(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def _clean_child_titles(raw: object, valid_child_ids: list[str]) -> dict[str, str]:
    """child_titles keys must be actual child ids (deterministic validation)."""
    if not isinstance(raw, dict):
        return {}
    valid = set(valid_child_ids)
    out: dict[str, str] = {}
    for child_id, title in raw.items():
        if child_id not in valid or not isinstance(title, str) or not title.strip():
            continue
        out[child_id] = _truncate_words(title.strip(), TITLE_MAX_WORDS)
    return out


def _number_tokens(text: str) -> list[str]:
    return _NUMBER_TOKEN_RE.findall(text or "")


def _validate_key_fact(raw: object, nodes: dict[str, Node], leaf_ctx_ids: list[str]) -> KeyFact | None:
    """Deterministic validation: every number-like token in big/detail must
    appear in the text of the cited leaves, or the whole KeyFact is dropped."""
    if not isinstance(raw, dict):
        return None
    big = raw.get("big")
    detail = raw.get("detail")
    if not isinstance(big, str) or not big.strip() or not isinstance(detail, str) or not detail.strip():
        return None
    big = big.strip()
    detail = detail.strip()

    cites_raw = raw.get("cites")
    cites = [c for c in cites_raw if isinstance(c, str) and c in leaf_ctx_ids] if isinstance(cites_raw, list) else []
    source_text = " ".join(nodes[c].text for c in cites if c in nodes).lower()

    for token in _number_tokens(big) + _number_tokens(detail):
        if token.lower() not in source_text:
            return None

    return KeyFact(big=big, detail=detail, cites=cites)


def _provisional_prompt(source_text: str, title: str) -> str:
    words = source_text.split()
    truncated = " ".join(words[:3000])
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
    raise ValueError(f"Summariser did not return valid JSON after retry (prompt started: {prompt[:120]!r})")


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
        await builder._emit("error", {"message": str(exc)})


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
        await builder._emit("leaves", {"nodes": [node.model_dump()]})
        await builder._emit("done", {"tree": tree.model_dump()})
        _save(tree)
        return

    nodes: dict[str, Node] = {}
    counter = [0]
    leaf_ids: list[str] = []
    boundary_keys: dict[str, str | None] = {}
    for leaf in leaves:
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
        boundary_keys[nid] = leaf.heading_path[0] if leaf.heading_path else None

    tree.nodes = nodes
    await builder._emit(
        "leaves",
        {"nodes": [nodes[i].model_dump() for i in leaf_ids], "source_words": tree.source_words},
    )

    # 1. Fast provisional root, emitted before any `level` event.
    prov_prompt = _provisional_prompt(source_text, tree.title)
    prov_result = await _call_summariser_json(
        summariser, prov_prompt, with_objective(SYSTEM_PROVISIONAL, tree.objective)
    )
    prov_text = str(prov_result.get("text", "")).strip() or "(gist coming...)"
    prov_id = _new_id(counter, (0, len(source_text)))
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

    # 2. Bottom-up build.
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def process_group(group_ids: list[str], is_root_call: bool, force: bool) -> tuple[str, Node | None]:
        if len(group_ids) == 1 and not force:
            return group_ids[0], None  # collapse: carried up unsummarised

        async with sem:
            child_words = sum(nodes[c].words for c in group_ids)
            target = max(1, round(child_words / RATIO))
            system_template = SYSTEM_ROOT_TEMPLATE if is_root_call else SYSTEM_SUMMARY_TEMPLATE
            system = with_objective(system_template.replace("{{TARGET}}", str(target)), tree.objective)
            prompt, leaf_ctx_ids = _build_prompt(nodes, group_ids)

            result = await _call_summariser_json(summariser, prompt, system)
            text = str(result.get("text", "")).strip()
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
                    text = str(result.get("text", "")).strip() or text
                    words = word_count(text)

            if not text:
                text = " ".join(nodes[c].text for c in group_ids)[:200]
                words = word_count(text)

            cites_raw = result.get("cites")
            cites = [c for c in cites_raw if c in leaf_ctx_ids] if isinstance(cites_raw, list) else []
            importance_map = result.get("importance") if isinstance(result.get("importance"), dict) else {}

            title = _clean_title(result.get("title"))
            short_title = _clean_short_title(result.get("short_title"))
            hook = _clean_hook(result.get("hook"))
            key_points = _clean_key_points(result.get("key_points"))
            steps = _clean_steps(result.get("steps"))
            key_fact = _validate_key_fact(result.get("key_fact"), nodes, leaf_ctx_ids)
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
                await builder._emit("level", {"nodes": [parent.model_dump()], "height": height + 1})
            current_level = [nid]
            height += 1
            final_root_id = nid
            if word_count(nodes[nid].text) <= GIST_STOP_WORDS:
                break
            continue

        groups = _group_leaves(current_level, boundary_keys) if height == 0 else _group_run(current_level)
        is_final_round = len(groups) == 1

        results = await asyncio.gather(
            *[process_group(group, is_root_call=is_final_round, force=False) for group in groups]
        )

        new_level = [nid for nid, _ in results]
        new_nodes = [node for _, node in results if node is not None]
        if new_nodes:
            await builder._emit("level", {"nodes": [n.model_dump() for n in new_nodes], "height": height + 1})

        current_level = new_level
        height += 1

        if len(current_level) == 1 and word_count(nodes[current_level[0]].text) <= GIST_STOP_WORDS:
            final_root_id = current_level[0]
            break

    if final_root_id is None:
        final_root_id = current_level[0]

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

    assign_depth(final_root_id, 0)
    tree.nodes = nodes
    tree.max_depth = max(n.depth for n in nodes.values())
    tree.status = "done"
    tree.sections = compute_sections(tree)

    _save(tree)
    await builder._emit("done", {"tree": tree.model_dump()})


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
