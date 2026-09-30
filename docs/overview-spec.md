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
- **PDF:** lines that repeat at the top or bottom of at least half the pages (running titles, "Page 3 of 12", bare page numbers), digits blanked, are dropped; the first page's top lines (the title) are kept. PDF and Word failures come back as a 400 with a plain message.
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

`SCHEMA_VERSION = "schema4"`. `/api/recent`, `/api/tree/{id}` and open-by-id fall back, read-only, to older
build-version dirs (and the flat `trees/` dir), so documents built earlier still open. Nothing is written to them.
