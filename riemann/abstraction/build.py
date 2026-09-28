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
from riemann.abstraction.model import Node, Tree
from riemann.abstraction.summarise import Summariser, parse_json_robustly

RATIO = 4
GIST_WORDS = 25
MAX_CONCURRENCY = 4
LEAF_CONTEXT_CHAR_BUDGET = 6000
LENGTH_TOLERANCE = 0.35
MAX_BUILD_ROUNDS = 40

SYSTEM_SUMMARY_TEMPLATE = """You are compressing part of a document into a shorter summary node for an adaptive-depth abstraction tree.
Rules:
- Keep causal connectives (because, therefore, however, ...) that are present in the source.
- Never add causation that isn't in the source.
- Keep hedges (may, likely, suggests, ...) rather than stating things as more certain than the source does.
- Keep terminology consistent with the children's wording.
- Target length: about {{TARGET}} words.

Respond with ONLY JSON, no prose outside it and no markdown code fences:
{"text": "...", "cites": ["leaf_id", ...], "importance": {"child_id": 0.0}}

"cites": leaf ids only, drawn from the "Leaf ids you may cite" list below -- the ones this summary's claims actually come from.
"importance": one entry per id listed in "Child ids" below, 0..1, relative to its siblings, reflecting how much that child matters to the overall point."""

SYSTEM_ROOT_TEMPLATE = SYSTEM_SUMMARY_TEMPLATE + (
    "\n\nThis call produces the ROOT of the tree: state the single most important conclusion or"
    " takeaway in the target word count -- not what the document is about."
)

SYSTEM_PROVISIONAL = """You are producing a fast provisional one-line gist for a document, to show while the full abstraction tree builds in the background.
State the single most important conclusion or takeaway in <= 25 words, not what the document is about.
Respond with ONLY JSON, no prose outside it and no markdown code fences: {"text": "..."}"""

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


def start_build(tree_id: str, title: str, source_text: str, summariser: Summariser) -> TreeBuilder:
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
    prov_result = await _call_summariser_json(summariser, prov_prompt, SYSTEM_PROVISIONAL)
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
            system = system_template.replace("{{TARGET}}", str(target))
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
            )
            nodes[nid] = parent
            for cid in group_ids:
                nodes[cid].parent = nid
                if cid in importance_map:
                    try:
                        nodes[cid].importance = max(0.0, min(1.0, float(importance_map[cid])))
                    except (TypeError, ValueError):
                        pass
            return nid, parent

    current_level = list(leaf_ids)
    height = 0
    final_root_id: str | None = None

    for _ in range(MAX_BUILD_ROUNDS):
        if len(current_level) == 1:
            only = current_level[0]
            if word_count(nodes[only].text) <= GIST_WORDS:
                final_root_id = only
                break
            nid, parent = await process_group([only], is_root_call=True, force=True)
            if parent is not None:
                await builder._emit("level", {"nodes": [parent.model_dump()], "height": height + 1})
            current_level = [nid]
            height += 1
            final_root_id = nid
            if word_count(nodes[nid].text) <= GIST_WORDS:
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

        if len(current_level) == 1 and word_count(nodes[current_level[0]].text) <= GIST_WORDS:
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

    _save(tree)
    await builder._emit("done", {"tree": tree.model_dump()})


def _save(tree: Tree) -> None:
    from riemann.abstraction.cache import save_tree

    save_tree(tree)
