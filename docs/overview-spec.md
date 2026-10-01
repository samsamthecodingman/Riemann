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

"Do it" tiles (`overviewHTML` in `web/app.js`, `web/doit.js`): when the overview has them, the tile grid starts with
**Start here** (full width, a prominent tile with `start_here.text` and its `¶` link), then **Due**, then **Size of
the job** (`size_of_job.text`, with `basis` as a "Based on ..." line), then the essentials in the order the server
sent them (act-first). **Due** is worded in the browser from today's date and `deadline.iso`: "Due in 5 days · Fri 14
Nov, 5 pm", "Due tomorrow", "Due today", "Overdue by 2 days" (calendar days in the reader's timezone; the time only
changes the date text; the year is added when it is not this year); `year_inferred` adds a subtle "year assumed". It is
computed on every render and re-worded when the tab becomes visible again; nothing ticks. An essential whose label is a
start-here or deadline label is not repeated as a tile when the matching field is shown. For `genre == "meeting"` an
**Actions** list follows the tiles, one row per `overview.actions` entry, in the served order (earliest due first): who,
what, then "Due in N days · <date as written>" (or just the date as written when there is no `due_iso`) and the `¶` link.
Values are never clamped. The tile grid is one column whenever two columns would give under about 45 characters a line.

Old trees: `POST /api/tree/{id}/overview` builds it from the root and section summaries plus the source's leaves
(first ~4000 words), once per tree; the reader calls it on open when the overview is missing. The result is saved
into the current cache namespace.

## Cache namespaces

`SCHEMA_VERSION = "schema7"`. `/api/recent`, `/api/tree/{id}` and open-by-id fall back, read-only, to older
build-version dirs (and the flat `trees/` dir), so documents built earlier still open. Nothing is written to them.

## Phase 1 data contract

What the backend now produces for the reader (phase 2 builds the UI on it). Everything is additive and
optional: an old tree, or one where a check removed a field, simply lacks it, and nothing here needs a progress
bar, a read mark or a "checked" tick. The cache namespace is `schema7`; older trees still open read-only.

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

### Genre (`Tree.genre`)

`Tree.genre` is one of `assignment`, `paper`, `news`, `email`, `meeting`, `legal`, `technical`, `article`, `other`
(plain labels for display: "Assignment or task brief", "Research paper", "News article", "Email or thread", "Meeting
notes", "Legal or policy document", "Technical documentation", "General article", "Other"; see `genre.GENRES`).
It is `null` only for trees built before genre detection, and for those it is filled in when the overview is
backfilled (`POST /api/tree/{id}/overview`, which saves the tree). The reader does not need it for anything but
labels; the overview fields below depend on it.

How it is decided (no extra model call):

1. `genre.detect_genre(title, text)`: cue words in the title, headings and first ~3,500 characters (an email's own
   headers, "Abstract" plus IMRaD headings, "(Reuters)", "Attendees"/"Actions", "shall"/"pursuant to", code fences
   plus "Installation"/"Usage" headings, "due"/"submit"/"marking criteria" ...). A strong result is used for every call
   from the start.
2. Otherwise the quick provisional-gist call also returns `"genre"`; the root summary, every layer after the first,
   and the overview use it (the first layer never waits for it, so it keeps its overlap with the gist call). If that
   reply is missing or not one of the keys, a weak cue-word guess is used, else `other`.

Each genre has a `GENRE_FOCUS` block (what a summary of that kind of document must cover: an assignment unpacks the
task and puts constraints first; a paper keeps question, method and sample, main result with its number, and limits;
news keeps the lede and attribution; email puts the ask first and separates decided from open; meeting notes keep
decisions and who-does-what-by-when; legal keeps "must", "unless" and deadlines; technical docs keep how-to steps in
order). It is added to the summary, root and overview prompts before the goal's `OBJECTIVE_FOCUS` block, so the goal
still decides what to emphasise. `GENRE_ESSENTIALS` gives the overview its labels (a paper: Question, Method and sample,
Main result, Limits); the goal's hint follows it.

### "Do it" overview fields (`Tree.overview`)

For a task-like document (`genre` is `assignment` or `meeting`, or the goal is `execute` or `plan`) the overview has
three more optional fields. All are `null` (never `""`) when the source does not support them; every one is
cited (`cites` are real leaf ids, each `¶` link opens that leaf) and passes the number, date and overlap checks above.

    "start_here":  {"text": "Download the dataset and starter notebook from Moodle, then run the first three cells.",
                    "cites": ["n4d33..."]}
    "size_of_job": {"text": "About 3 sessions of 2 hours",
                    "basis": "an 1,800-word report, 8 pages, a notebook and 3 sites",
                    "cites": ["n2a7a...", "nead8..."]}
    "deadline":    {"iso": "2025-11-14", "time": "17:00", "label": "Report PDF and zipped notebook",
                    "cites": ["nead8..."], "year_inferred": false}

- `start_here.text`: one concrete first step doable in about ten minutes, at most 25 words.
- `size_of_job.text`: a rough estimate of the effort, at most 20 words; the model's own words, so its numbers are
  not matched against the source. `basis` is what it rests on, in the source's quantities (every number in it is in the
  cited leaves): show it as the "why", for example beneath the estimate.
- `deadline`: the single main deadline. `iso` is `YYYY-MM-DD` and the day number and month are in a cited leaf.
  `time` is `"HH:MM"` (24 h) or `null` (dropped when no matching clock time is in the cited leaves). `year_inferred`
  is `true` when the source gives no year (or the model left it out): `iso` then uses the year the context implies, or
  the next occurrence of that day counted from the day of the build; a year the source states must match. The browser
  computes "in N days" from `iso` (and `time`) and today's date; nothing here counts down.

**Act-first order.** `essentials` are sorted by what the reader must act on first, by label: deadline labels (Due,
Deadline, Reply by, Submit by ...), then deliverable labels (Deliverables, What you need to do, The ask, Task ...),
then first-step labels (Start here, First step, Next action), then everything else in the model's order. The prompt
asks for the same order. The UI should show `start_here`, `deadline` and `size_of_job` before the essentials.

### Meeting actions (`Overview.actions`)

For `genre == "meeting"` the overview has `actions`, a list (empty otherwise, never `null`), earliest due first and
undated actions last. At most 12.

    {"who": "Aisha Rahman", "what": "Chase Dr Malik about the ethics check",
     "due": "Wednesday 15 October", "due_iso": "2025-10-15", "cites": ["n870d..."], "year_inferred": false}

- `who` and `what` are checked against the cited leaves: some word of `who` (a name) must be in them, and `what` must
  share content words with them (the same overlap floor as essentials). An action with no cite, or one that fails
  either check, is dropped.
- `due` is the date as the source writes it (`null` when none). Its weekday, month and day number must be in the
  cited leaves, otherwise the whole action is dropped. `due_iso` is `YYYY-MM-DD` or `null`: it is kept only when its day
  and month are in the cited leaves (a wrong one is dropped but the action stays). `year_inferred` is as for the deadline.
- The browser sorts nothing: the order is already the display order. "Which are mine" is not built.

### Rebuild, and builds the server never finished (item 9)

- **`POST /api/tree/{id}/rebuild`** builds the same document again under the current schema, from the tree's stored
  `source_text` (put through ingest again, so the newer clean-up applies), with the tree's own model (the default model
  for an old tree that has none) and goal. Response: `{"tree_id": "<new id>", "cached": false}`; follow it like a
  fresh `POST /api/abstract` (poll `GET /api/tree/{new id}`, or stream its events). The id is the usual hash of
  text, model and goal, so for a tree that already has a model it is often the **same id**: the new tree is saved in
  the current cache namespace and shadows the old copy, which stays untouched (read-only) in its old namespace.
  `{"cached": true}` means that tree already exists under the current schema and nothing was started. `404` for an
  unknown tree, `409` while that tree is still building.
- **Building marker.** When a build starts, a small marker (source text, title, goal, model, start time) is written
  to `<cache>/building/<id>.json`; it is deleted when the build finishes or fails (a failed build is retried with
  `POST /api/tree/{id}/retry` as before). If the server stops mid-build the marker is left behind.
- **`GET /api/tree/{id}`** (and `/events`) for an id that has a marker but no live builder and no saved tree answers
  **`409`** with
  `{"state": "interrupted", "tree_id": "...", "title": "...", "objective": "learn"|null, "model": "...", "started": <unix seconds>, "message": "..."}`.
  A live builder, or a saved tree, always wins over a marker (a stale marker is swept). The loading screen can show the
  message and a "Resume" button.
- **`POST /api/tree/{id}/resume-build`** restarts it from the marker with the same source, goal and model and returns
  `{"tree_id": "<same id>"}`; poll it as usual. Idempotent: a build already running, or a finished tree, is left alone and
  the same body comes back. `404` if there is no marker, `409` if that build failed (use `retry`). Re-posting the same
  document to `POST /api/abstract` also just starts a fresh build.

### Experiment events (item 10)

Optional fields for the two-week ABAB protocol (`docs/experiment.md`; the method is R4 in `docs/overnight-review.md`).
`POST /api/events` accepts them on **any** event; `events.clean_event` drops a value that is the wrong type or
outside its range and keeps the event. No field is a progress or read mark.

| Field | Values | Meaning |
|---|---|---|
| `condition` | `"A"` or `"B"` | A = the original document, B = Riemann |
| `phase` | `"A1"`, `"B1"`, `"A2"`, `"B2"` | which block of the design |
| `doc_label` | text, at most 80 characters | the experiment's own name for the document (no document text) |
| `first_zoom_ms` | number 0 to 86,400,000 | time from open to the first dial input |
| `max_z` | number 0 to 1 | deepest zoom reached in the session |
| `session_ms` | number 0 to 86,400,000 | open to close |
| `source_checks` | integer >= 0 | `hover_source` + `jump_source` in the session |
| `did_it_help` | boolean | the yes or no asked on close |
| `minutes_to_know` | number 0 to 1440 | self-timed minutes until "I know what to do" |
| `checklist_score` | integer 0 to 5 | the fixed five-question checklist, scored against the source |
| `tlx_mental`, `tlx_physical`, `tlx_temporal`, `tlx_performance`, `tlx_effort`, `tlx_frustration` | number 0 to 100 | NASA-TLX raw sub-scales |
| `missed_later` | boolean | a week later: did I find I had missed something? |
| `started_within_24h` | boolean | self-reported |
| `minutes_to_first_action` | number 0 to 20,160 | first opening to the first real action |

Event types the UI should send (a phase-2 task; nothing sends them yet):

- `experiment {action: "set"|"end", condition, phase, doc_label}`: marks that everything after it, until the next
  `experiment` event, belongs to that condition, phase and document. Sent when Sam switches condition or document.
- `close {tree_id, session_ms, first_zoom_ms, max_z, source_checks}`: the existing `close` event with the
  session numbers added. `first_zoom_ms` is open to the first `dial` event.
- `did_it_help {tree_id, value}` on close; `outcome {doc_label, minutes_to_know, checklist_score, tlx_*, missed_later,
  started_within_24h, minutes_to_first_action}`, one per document or several partial ones for the same `doc_label`.

`scripts/experiment_report.py` reads the log and summarises it by phase and condition (`--csv`, `--json`).

### Other phase-1 changes the UI should know about

- **Word counts.** `Tree` word counts (`node.words`, `source_words`) now count each Han or Kana character as about one
  word, Hangul by its spaces, CJK punctuation not at all. `web/frontier.js` exports `Frontier.countWords(text)` and
  `Frontier.firstClause(text)` with the same rules (parity-tested against Python); `app.js` has its own `countWords`
  and `firstClause` copies, which should call these so the reader and the zoom steps agree for Chinese and Japanese.
- **Chunking.** An over-long paragraph is cut at the latest sentence end, else the latest clause end, never in the
  middle of a sentence unless the text has neither. Leaves never pack across any heading level.
- **PDF and email.** PDFs are read by layout; a pasted email loses quoted history, signature and legal footer. Both
  are server-side only. A ruled PDF table becomes a markdown table leaf (atomic, as before).
