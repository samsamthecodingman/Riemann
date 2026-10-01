# Overview card, clean source text, and growing zoom steps

Three fixes made together (schema4). Everything here is additive to `docs/v2-macaron-spec.md`.

## 1. Source text is repaired before it is hashed and chunked

`riemann/abstraction/normalise.py` (`normalise_text`), applied in `ingest.py` to pasted text, uploaded
files (including PDFs) and fetched URLs. The tree id is a hash of the repaired text.

- Characters: non-breaking hyphen U+2011 and friends become `-`, soft hyphen and zero-width characters are
  dropped, NBSP becomes a space, runs of spaces collapse. Code fences are left alone.
- **Word-per-line** extraction (nearly every non-blank line is one word): the blank lines between tokens carry
  the structure: none = glued (a `.` or `-` on its own line), one = a space, two or more = a paragraph break. A
  numbered heading token (`3.`) after a sentence end starts a paragraph. A list item that ends in a full stop
  followed by a capital ends the list.
- **Hard-wrapped** prose (PDF style): wrapped lines are rejoined; `infor-\nmation` is de-hyphenated; a sentence
  that ended a short line, or a heading-like line, starts a new paragraph.
- Bullet glyphs (`●•▪◦○…`, and `– ` at a line start, also inline) become markdown `- ` items, and numbered
  items stay `1. `; a list is always its own block (blank line before and after).
- Well-formed prose and markdown are unchanged. The function is idempotent.

Later additions to the repair step (all deterministic, in `ingest.py` and `normalise.py`):

- **Word files:** `.docx` is read with the standard library (zip and XML): headings, list items, paragraphs and table rows, in order. The inflated size of `word/document.xml` is capped at 40 MB before it is read.
- **PDF (layout-aware):** `riemann/abstraction/pdftext.py` reads word positions with pdfplumber: running headers and footers and page numbers are dropped (page 1's title is kept), a two-column page is read left column then right, lines are joined into paragraphs (a bigger gap, indent, bullet or size change starts a new one; hyphenated line ends are rejoined), bullet glyphs become `- ` items, larger type becomes a markdown heading, a ruled table becomes a markdown table, and a paragraph cut by a page break is joined. Any failure (or no text found) falls back to pypdf's plain word stream. Over 400 pages goes straight to pypdf. Below, the pypdf-era rule still applies to that fallback: lines that repeat at the top or bottom of at least half the pages (running titles, "Page 3 of 12", bare page numbers), digits blanked, are dropped; the first page's top lines (the title) are kept. PDF and Word failures come back as a 400 with a plain message.
- **Numbered headings** on their own line followed by prose ("2. Method", "2.1 Data") become markdown headings (`##`, `###`), so the chunker keeps the report's sections. A real numbered list stays a list.
- Ligatures (fi, fl, ff, ffi, ffl) are expanded.
- **Links:** `https://` is added when missing, layout tables that wrap a whole article are unwrapped, and "¶" permalinks are dropped from headings and titles. The link must be http or https and every address it resolves to (and every redirect hop) must be public.
- **Chunking:** a markdown table is one atomic leaf (like a code fence).

Rendering: prose and source leaves go through `renderMarkdown` in `web/app.js` (marked, or a built-in
fallback if the CDN script did not load), then a tag/attribute allow-list sanitiser; raw HTML in the source is
shown as text. Key points and essentials use `renderInline` (escaped, then `**bold**`, `*italic*`, `` `code` ``).

## 2. Zoom steps always grow

**Build** (`build.collapse_single_child_chains`): no pass-through levels. An internal node with one internal
child absorbs it (takes its children, keeps its own summary); a non-root node left with a single leaf child is
replaced by that leaf. This removes the root -> node -> node chains the forced root summarising used to leave. The
sections are the root's children (the first level with 2+ nodes, which is now always the first level).

**Expansion sequence** (`frontier.py` and `frontier.js`, kept in parity by `tests/test_frontier_parity.py`): every
step must add at least `min(15% of the visible words, 25 words)`. A candidate step that does not (or that shows a
single-child node, or expands one) is applied tentatively and merged into the next step, which must build on it;
only that later token is emitted. So one step does both.

- Tokens keep their meaning: `"id"` expands, `"~id"` shows prose. Applying a token for node N also opens N's
  ancestors (`_apply` / `applyToken`), which is what lets a token stand in for the ones merged into it.
  `frontier_at`, `prose_at`, `frontierAtK`, `proseAtK` replay that. `kToReveal` (JS) finds the k at which a node is
  on the page, for jumps.
- Visible words = `visible_words`: a lone root is its hook line, a skim node is title + key points, anything else
  is the node's text.
- `keep_expanded` tokens (the current page) are emitted first, one plain step each, so re-anchoring never changes
  the page; `len(keep)` is the current k.
- The pinned-anchor maths in `app.js` (`offsetAtY`, `yOfOffset`, `setZ`) is unchanged.

## 3. Overview card

`Tree.overview` (optional): `doc_title` (the document's own name), `doc_kind` (a few words), `what_it_is` (one
plain sentence), `essentials` (up to 7 `{label, value, cites}`). Built by `build.generate_overview` in one call
after the root (part of "done"), steered by `OBJECTIVE_FOCUS` plus `OVERVIEW_ESSENTIALS`. Validation is
deterministic: cites must be real leaf ids; every number in a value must appear in a cited leaf (else the item is
dropped); `what_it_is` falls back to "This is a <kind>." if it contains a number not in the source; duplicate
labels are dropped; "not stated" is the value for anything the source does not say.

UI: the card sits above section 01 at every zoom level (kind pill, title, sentence, 2-column essentials tiles,
each with its `¶` link; values are shown in full, never clamped: the prompt asks for under 15 words and the validator caps a value at 30). At the gist the hero shows a
"THE GIST" kicker instead of repeating the title. The header title uses `doc_title`.

Old trees: `POST /api/tree/{id}/overview` builds it from the root and section summaries plus the source's leaves
(first ~4000 words), once per tree; the reader calls it on open when the overview is missing. The result is saved
into the current cache namespace.

## Cache namespaces

`SCHEMA_VERSION = "schema6"`. `/api/recent`, `/api/tree/{id}` and open-by-id fall back, read-only, to older
build-version dirs (and the flat `trees/` dir), so documents built earlier still open. Nothing is written to them.

## Phase 1 data contract

What the backend now produces for the reader (phase 2 builds the UI on it). Everything is additive and
optional: an old tree, or one where a check removed a field, simply lacks it, and nothing here needs a progress
bar, a read mark or a "checked" tick. The cache namespace is `schema6`; older trees still open read-only.

To see example values without a model, run the fake-summariser app and paste the sample documents in
`tests/fixtures/` (an assignment brief, a paper and meeting notes; they are synthetic):

    RIEMANN_DATA_DIR=/tmp/riemann-ui uv run uvicorn tests.e2e.fake_app:app --port 8765

### Faithfulness checks (deterministic, in `checks.py` and `build.py`)

Short model-written items (essentials, key facts, `start_here`, `size_of_job`, the deadline and actions) are
checked against the leaves they cite, and dropped when a check fails:

- **Numbers** (as before) must appear as whole numbers in a cited leaf; a small number may be a word there
  ("3 offices" for "three offices").
- **Dates:** weekday names and month names in the item must appear in a cited leaf (`Fri` matches `Friday`; a
  numeric date such as 14/11/2025 supplies its month; "may" is only a month beside a day number).
- **Cite overlap:** an essential or key fact must share at least `CITE_OVERLAP_FLOOR` (0.35) of its content words
  (stemmed, stop words ignored) with its cited leaves. "not stated" values are exempt; an item with no valid cite
  is judged on its numbers and dates only (which fail without a cite).
- **Negation and modality (log only):** if the source sentence an item is mostly about contains not, must not,
  unless, except, only if, no ... and the item (label included) has none of them, the build records a
  `warning` event and a Python log line. Nothing is dropped and nothing changes in the tree.

`warning` events appear in the build history (`GET /api/tree/{id}/events` replays them, and they are streamed as
`event: warning` while building; ignore them if you do not use them):

    {"kind": "qualifier_dropped", "where": "essential Due" | "key fact 5%" | "start_here" | "action Tom Becker",
     "qualifier": "not", "sentence": "<the source sentence, up to 300 chars>", "item": "<the item text>"}

Measured on the 15 cached trees (64 key facts and 12 essentials with cites): the date and overlap checks drop
0 of 76 real items (before: 0). As a control, the same items cited to a random other leaf of their document are
dropped 93.2% of the time (the old number check alone: 86.8%). The qualifier check would warn on 7 of 76.

