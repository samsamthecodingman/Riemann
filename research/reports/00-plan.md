# Riemann: rolling abstraction ("zoom dial") v1

## Context
Riemann's first feature should present any body of information at an adjustable level of detail. It opens at a high abstraction that can be read in 1–2 minutes, and one continuous dial zooms in until you reach the original text. v1 renders plain markdown on a local web page. The same data structure (an abstraction tree) will later drive the **spatial view**, where zoom becomes camera distance. No Riemann code exists yet, so this is greenfield in `~/Projects/riemann`.

Decisions so far: a global zoom dial, not per-node expand; a local web page, not a TUI; and inputs are pasted text, files and URLs (email comes later).

## Core idea: the abstraction tree
Every input becomes one tree, and zooming just picks which depth of that tree to render.

| Level | Content | Target size |
|---|---|---|
| L0 | One-line gist | ≤ 25 words |
| L1 | "1–2 minute read" summary | ~230 words/min × 1–2 min, scaled by source length |
| L2 | One gist per section | ~40–80 words each |
| L3 | Original text chunks (verbatim) | — |

Each node has `id, level, markdown, children[], source_span`. The parent/child links make zoom feel continuous. When you change level, the node nearest the viewport centre maps to its ancestor or descendant, and the view scrolls to keep it anchored. That anchoring is the "live rolling" part.

## Architecture
```
riemann/
  pyproject.toml            # uv; fastapi, uvicorn, claude-agent-sdk, httpx, trafilatura, pypdf, pydantic, pytest
  riemann/abstraction/
    model.py                # pydantic Node / Tree; JSON (de)serialisation
    ingest.py               # text | file (.md/.txt/.pdf) | URL → clean text (trafilatura for URLs, pypdf for PDF)
    chunk.py                # split on headings, then paragraphs, to ~1.5k-token L3 leaves
    summarise.py            # Summariser protocol + ClaudeSummariser (Agent SDK) + FakeSummariser (tests)
    build.py                # leaves → L2 gists → L1 → L0; streams events as each level completes
    cache.py                # trees stored as JSON under ~/.cache/riemann keyed by content hash
  riemann/server.py         # FastAPI: POST /abstract (text|file|url) → tree id; GET /tree/{id}; SSE /tree/{id}/events
  web/index.html, app.js, style.css   # vanilla JS; markdown via marked (cdn.jsdelivr); dial = slider + ←/→ keys + ctrl-scroll
  tests/
```

**Build strategy** (`build.py`):
- If the chunked source fits comfortably in one context (< ~120k tokens), make **one call** that returns JSON for L0–L2, with each L2 gist citing the leaf ids it covers. Validate with pydantic and retry once if validation fails.
- Otherwise, map-reduce: summarise each leaf to L2 in parallel (bounded concurrency), then group and reduce to L1, then L0.
- Emit SSE events per level so the page can show the original (L3) at once and let higher levels fill in as they arrive.

**Summariser**: `ClaudeSummariser` uses the Python Claude Agent SDK `query()` with no tools. It authenticates through the subscription-linked Claude Code login, not an API key, which matches the Phase 1 principle. Everything sits behind a `Summariser` protocol so models or providers can be swapped later and tests don't call Claude.

**Frontend**:
- The dial has 4 detents (L0–L3) and a label showing the level and estimated read time. The readout is computed from word count.
- Rendering is a flat walk of the nodes at the selected level. Each block is tagged `data-node-id` so the anchoring logic above can find it.
- Keep the page plain and markdown-first. No spatial rendering yet, but the tree JSON is the future contract for the spatial view.

## Out of scope for v1
Per-node expand, email input, the spatial view itself, Docker, voice, persistence beyond the tree cache.

## Prerequisites to confirm when building
- Agent SDK credit opt-in, and SDK auth working with the subscription login. Check current Anthropic docs, since the billing figures are unverified.
- `uv`, `node` and the `claude` CLI are present on this machine (uv and node are confirmed).

## Verification
1. `uv run pytest`: chunker boundaries, tree validation, anchor mapping (level change keeps the same source span), and build pipeline, all using `FakeSummariser`.
2. Add a `.claude/launch.json` entry (`uv run uvicorn riemann.server:app --port 8765`) and open it with preview_start.
3. In the browser pane, paste a long article (for example a ~5k-word Wikipedia page by URL) and a local PDF, then check:
   - L3 shows immediately and L2→L0 stream in.
   - L1's word count falls within the 1–2 minute target.
   - Dragging the dial or pressing ←/→ keeps the centred passage anchored.
   - There are no console errors.
   - A reload hits the cache without a new Claude call.
4. Share screenshots of L0, L1 and L3 for the same document.
