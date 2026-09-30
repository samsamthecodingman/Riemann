# Riemann v1: continuous zoom dial (build spec)

The approved plan (`research/reports/00-plan.md`), amended by Sam's decisions of 2026-09-28 (`research/RIEMANN-ABSORPTION-MODEL.md` §5). This file is the **contract** between the backend and frontend. Change it here first if either side needs something different.

## Scope
**In v1:**
- Paste text, upload a file (.md/.txt/.pdf) or give a URL. Riemann builds an **adaptive-depth abstraction tree**, and a local web page shows it with a **continuous zoom dial**.
- A local **event log**.
- A **resume** feature: reopen where Sam left off.

**Out of v1:**
- The objective chip (the objective is fixed to *understand*)
- Audio
- Learn-mode prompts
- Life-admin transforms
- The spatial view
- Docker

## Layout
```
riemann/
  pyproject.toml                 # uv; python >=3.12; fastapi, uvicorn[standard], claude-agent-sdk, httpx, trafilatura, pypdf, pydantic>=2, sse-starlette, pytest, pytest-asyncio
  riemann/__init__.py
  riemann/abstraction/model.py   # Node, Tree (pydantic)
  riemann/abstraction/ingest.py  # text | file | url → (title, clean markdown text)
  riemann/abstraction/chunk.py   # markdown → leaves (atomic code/procedure/equation blocks)
  riemann/abstraction/summarise.py  # Summariser protocol; ClaudeSummariser; FakeSummariser
  riemann/abstraction/build.py   # adaptive-depth bottom-up build + provisional root; emits events
  riemann/abstraction/cache.py   # ~/.cache/riemann/trees/<sha256>.json
  riemann/events.py              # append-only event log ~/.local/share/riemann/events.jsonl
  riemann/server.py              # FastAPI app; serves web/ at /
  web/index.html  web/app.js  web/style.css
  tests/
  .claude/launch.json            # {"name":"riemann","runtimeExecutable":"uv","runtimeArgs":["run","uvicorn","riemann.server:app","--port","8765"],"port":8765}
```

## Data model (shared contract)
```python
class Node(BaseModel):
    id: str                  # stable: "n" + short hash of (source_span, depth)
    depth: int               # 0 = root gist; increases toward the source; leaves carry the max depth of their branch
    text: str                # markdown
    words: int
    children: list[str]      # child node ids, in document order
    parent: str | None
    is_leaf: bool            # True = verbatim source chunk
    source_span: tuple[int, int]   # char offsets into Tree.source_text covered by this node
    cites: list[str]         # leaf ids this node's claims come from (empty for leaves)
    importance: float        # 0..1, relative to siblings; drives expansion order
    atomic: bool = False     # code/procedure/equation: never summarised; shown verbatim once reached

class Tree(BaseModel):
    id: str                  # sha256 of source_text (first 16 hex)
    title: str
    source_text: str
    source_words: int
    root: str                # root node id
    nodes: dict[str, Node]
    max_depth: int
    status: Literal["building", "done", "error"]
    provisional_root: bool   # True while the root gist is the fast provisional one
```

## Adaptive depth (build.py)
- **Chunk:**
  - Split on headings, then paragraphs, into leaves of ≤ ~350 words.
  - Code fences, numbered procedures and `$$…$$` blocks become their own atomic leaves.
  - A source of ≤ ~60 words is a single leaf, and its root *is* the leaf: 1 level, no summary.
- **Group bottom-up:** group adjacent siblings, respecting heading boundaries, into parents so that each parent summary is about ¼ of its children's words (`RATIO = 4`, a config constant). A parent summarises 2–6 children.
- **Recurse** until a single node has ≤ `GIST_WORDS = 25` words. That node is the root.
- **Skip useless levels:**
  - A node with one child that isn't at least 2× shorter than that child collapses into the child.
  - A leaf shorter than its would-be parent budget is simply carried up unsummarised. This makes the tree **ragged**, with depth varying by branch.
- **Root is a claim:** "State the single most important conclusion or takeaway in ≤25 words, not what it's about."
- **Summaries cite leaves.** Each summary prompt receives the texts of its children *and* the text of the leaves under them (truncate to fit), and must return JSON `{"text": ..., "cites": [leaf ids], "importance": {child_id: 0..1}}`. Rules:
  - Keep causal connectives.
  - Never add causation that isn't in the source.
  - Keep hedges.
  - Keep terminology consistent with the children.
- **Length check:** if the words fall outside ±35% of the target, make one retry that states the delta. After that, accept the result.
- **Fast provisional root first:** before the bottom-up build, one call over the first ~3,000 words plus the headings gives a provisional root gist, emitted immediately. The final root replaces it at the end.
- **Concurrency:** summaries at the same height run concurrently, with at most 4 at a time.
- **Events** go into an in-process queue per tree, in this order:
  1. `leaves` (all leaves plus the source)
  2. `provisional_root`
  3. `level` (each batch of new parents as a height completes)
  4. `done` (the final tree)
  5. `error`, if anything fails

## Summariser
- `Summariser` is a Protocol with `async summarise(prompt: str, system: str) -> str` (JSON text).
- **Provider selection:** env `RIEMANN_PROVIDER` = `proxy` (default) | `agent-sdk`. `get_summariser()` in `summarise.py` is the factory server.py (and everything else) should use.
- **`ProxySummariser`** (default) talks to Sam's local CLIProxyAPI, an OpenAI-compatible proxy, so summarisation doesn't spend Agent SDK credit:
  - `httpx.AsyncClient` POST to `{RIEMANN_PROXY_URL}/v1/chat/completions`, default `http://127.0.0.1:8317`. Deliberately **not** the Headroom proxy on 8787, which compresses prompts and would alter source text, breaking faithfulness.
  - Body: `{"model": RIEMANN_MODEL, "messages": [{"role":"system",...},{"role":"user",...}], "temperature": 0.2}`. Reads `choices[0].message.content`.
  - Model from `RIEMANN_MODEL`, default `claude-sonnet-5-5`.
  - API key from env `RIEMANN_PROXY_KEY`, else the first entry under `api-keys:` in `~/.cli-proxy-api/config.yaml` (a tiny line parser, no PyYAML dependency). Never logged or printed.
  - Timeout 120s. Retries once on 429/5xx or connection errors, with backoff.
  - A `model_cooldown` error code from the proxy raises a clear error naming the model and telling Sam to set `RIEMANN_MODEL` to another model (e.g. `gemini-3.8-flash-high`).
- **`ClaudeSummariser`** (the alternative, `RIEMANN_PROVIDER=agent-sdk`) uses `claude_agent_sdk.query()`:
  - no tools, `max_turns=1`
  - model from the env var `RIEMANN_MODEL`, default `claude-sonnet-5-5`
  - auth is the local Claude Code login; **never** read or require an API key
- **`FakeSummariser`** is deterministic. For tests, it returns the first N words of the input plus cites for all leaves.

## API (server.py)
| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/api/abstract` | JSON `{"text"}` or `{"url"}`, or multipart `file` | `{"tree_id", "cached": bool}` (starts the build in the background if not cached) |
| GET | `/api/tree/{id}` | — | the Tree JSON (whatever exists so far) |
| GET | `/api/tree/{id}/events` | — | SSE: `leaves`, `provisional_root`, `level`, `done`, `error`; data = JSON (nodes added/updated). If the build is already done, send one `done` with the full tree and close |
| POST | `/api/events` | JSON array of UI events | 204. Appended to the event log with a server timestamp |
| GET | `/api/recent` | — | the last 20 trees (id, title, words, updated) for the start screen |
| GET | `/` | — | web/index.html |

## Continuous zoom (frontend)
**Dial state:**
- `z ∈ [0, 1]`: 0 is the root gist only; 1 is every leaf (the full source).
- **Frontier:** the set of nodes rendered, in document order, such that no rendered node is an ancestor of another rendered node.
- **Expansion order:** precompute one ordered list of all internal nodes, the "expansion sequence", with a priority function:
  1. **distance from the anchored node** (in tree hops or document offset), nearest first. This is recomputed when the anchor changes, e.g. after a scroll.
  2. then higher `importance`
  3. then shallower depth
- **Mapping z to the frontier:** z maps to k = number of expansions applied, where k = round(z × total_expansions). **Frontier(k)** = the root with the first k nodes of the sequence expanded (a node can only expand if its parent already has, so the sequence must be topologically valid).
- **Result:** the dial feels continuous. Each small turn expands or collapses one node near where Sam is reading.

**Controls:**
- A slider, plus:
  - `←`/`→`: ±1 expansion
  - `Shift+←`/`Shift+→`: ±10%
  - `Home`/`End`: 0 or 1
  - `Ctrl+wheel`: fine steps
  - Hold-and-drag on the readout
- **No level names.** The readout shows `~{minutes} min · {pct}% of original` (at 238 wpm; a small, muted, never-counting-down label).

**Anchoring:**
- Before an expansion, record the node at viewport centre and its screen y.
- After rendering, find that node or its replacement (the child whose `source_span` contains the old centre offset, or the parent) and scroll so it sits at the same y.

**Transitions:**
- An expanding node crossfades out (opacity) while its children fade in, over 180 ms.
- Headings that persist use a FLIP transform.
- `prefers-reduced-motion`: instant.
- Jumps of more than ~15% of the dial crossfade the whole column (a cut).

**Chrome:**
- The root gist is a persistent header, with the provisional root marked "gist coming…" until final.
- A home control (z → 0).
- A breadcrumb (appears only when the anchored node's ancestors are off-screen): the nearest two ancestors' first clauses, clickable.
- A minimal-chrome toggle (`m`): hides everything except the content and the dial.

**Reading column:**
- 60–75 characters wide.
- Leaves render as markdown (marked from cdn.jsdelivr) with a subtle left rule.
- Summaries render in normal weight, with a dotted underline on hover.
- **Source hover** on a summary sentence shows a popover with the 1–2 most relevant sentences from its cited leaves: first cited leaf, first 2 sentences. Click jumps: it expands along the path to that leaf and anchors on it.

**Accessibility:**
- The dial is `role="slider"` with `aria-valuetext="about N minutes, P percent of original"`.
- A persistent `aria-live="polite" aria-atomic="true"` region announces changes, debounced 400 ms.
- Nodes are `<section>` with headings where the source has them.

**Start screen:**
- A paste box, file input and URL field.
- Below them, recent trees as plain links. No counts, no "unfinished" language.

**Resume:**
- `localStorage['riemann:pos:'+tree_id] = {z, anchor_node_id, anchor_offset}`, saved on change (debounced) and on `visibilitychange`/`pagehide`.
- On reopen, restore it. A new tree opens at the z where the frontier is closest to ~2 minutes of reading (or 1.0 if the whole source is ≤2 minutes).
- A resume card appears for 4 s on reopen: "Back where you left off: {anchor's first clause}". Dismissible. No shame language.

**Never:** progress bars, "% read", streaks, badges, or countdown timers.

## Event log (approved by Sam)
- **Client** batches events every 5 s, and on `pagehide` via `navigator.sendBeacon('/api/events', ...)`.
- **Event types:**
  - `open {tree_id, resumed}`
  - `dial {tree_id, z_from, z_to, input: "slider|key|wheel|home"}`
  - `dwell {tree_id, node_id, ms}`: the node at centre for >1.5 s, emitted when the anchor changes
  - `hover_source {tree_id, node_id}`
  - `jump_source {tree_id, leaf_id}`
  - `idle {tree_id, ms}`: no input for >60 s, emitted on return
  - `close {tree_id}`
  - `not_helpful {tree_id, z}`: a small "not helpful" link in the chrome
- **Server** appends `{"ts": iso8601, ...event}` per line. The log is local only, never sent anywhere.

## Tests (pytest, FakeSummariser, no network)
- **chunk:** heading splits; the ≤350-word cap; code/procedure/equation atomic; a tiny input gives one leaf.
- **build:**
  - Depth adapts: 150 words gives max_depth ≤2; 1,500 gives 3–5; 20,000 gives 5–7.
  - The root is ≤25 words (±35%).
  - Every internal node has cites ⊆ leaves under it.
  - source_spans nest and cover the source.
  - The tree is ragged when sections differ in length.
  - The provisional_root event comes before any level event.
- **expansion sequence** (a Python reference implementation in `riemann/abstraction/frontier.py`, mirrored in JS):
  - topologically valid;
  - k=0 gives the root;
  - k=total gives exactly the leaves;
  - monotonic.
- **Anchoring helper:** a node's replacement contains the old centre offset.
- **Server:** POST text → tree_id; SSE completes with `done`; POST /api/events appends lines to a temp log path (env `RIEMANN_DATA_DIR`); caching works (a second POST gives `cached: true`).
- **Cache:** the same text gives the same id and no second build.

## Evaluation harness (tests/eval/)
- `tests/eval/docs/`: 3 sample docs of about 150, 1,500 and 8,000 words (public-domain text, e.g. Wikipedia excerpts saved as .md).
- `tests/eval/questions.yaml`: 3–5 questions per doc, each tagged `kintsch: situation|textbase|surface` and `expected_z`.
- `tests/eval/run_eval.py`: a manual runner that uses the real summariser and prints, per question, whether the frontier at `expected_z` contains the answer. It asks Claude a yes/no question and states that it's a rough check. Not run in CI.
