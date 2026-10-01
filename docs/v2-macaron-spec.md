# Riemann v2: Macaron Command Centre (build spec)

**Design source:** Claude Design canvas https://claude.ai/artifact/GBpLU32rdKLGYg73DtwkxJ. The boards used here are **Theme-Macaron** and **Macaron-Palette**, with local copies in `design/Macaron-Palette.dc.html` and tokens in `design/softpastel-tokens.json`.
**Keep:** everything in `docs/v1-build-spec.md` that isn't changed below. That includes the continuous zoom-at-pointer (Z+move, Ctrl+wheel, ←/→, =/−), zero anchor drift, adaptive depth, the event log, resume, `aria` slider semantics and reduced motion.
**Non-negotiables:** `docs/design-brief.md`, which applies in full. There must be no progress bars or read/unread marks. Section-map items show position only.

## 1. Data: structured nodes (backend)

### Node additions (`model.py`), all optional so old trees still load
```python
title: str | None = None          # 2–8 word faithful headline for this node (leaves too)
hook: str | None = None           # ≤ 20 words, one line: why this part matters (internal nodes)
key_points: list[str] = []        # 2–4 short bullets (internal nodes whose children are sections or paragraphs)
key_fact: KeyFact | None = None   # {big: "Hundreds → billions", detail: "…", cites: [leaf ids]}
steps: list[str] = []             # 3–6 short labels when the content describes a sequence or process; else []
```
Tree gains `sections: list[str]`: node ids of the **section level**, the first depth from the root that has ≥2 nodes. A single-leaf tree has no sections.

### Generation: no extra model calls
- Extend the existing per-parent summarise JSON to return, alongside `text`, `cites` and `importance`:
  - `title` and `hook` for the parent itself
  - `child_titles` (`{child_id: title}`, which is how leaves and children get their subheads)
  - `key_points`, `key_fact` (or null) and `steps` (or [])
- Leaf titles come from their parent's `child_titles`.
- The root's call also returns `hook`, which is used as the header's one-line gist.

**Prompt rules** (add to the system prompts):
- Titles are **punchy but faithful**: specific and concrete, like a good explainer headline. They must not claim anything the source doesn't say. No clickbait, questions only where the source poses one, no exclamation marks, no emoji.
- Keep hedges ("often", "may") where the source has them.
- `key_fact` only when the source contains a genuinely striking, specific fact. Otherwise null.

**Deterministic validation, applied after generation:**
- `key_fact`: every number-like token in `big` and `detail` (`\d[\d,.]*`, "billion", "million", decades like "1980s") must appear in the text of the cited leaves. If not, set `key_fact = None`.
- `title` ≤ 8 words, `hook` ≤ 20 words, `key_points` ≤ 4 items of ≤ 18 words each. Truncate or drop; don't retry.
- `child_titles` keys must be actual child ids.

`build_version()` (the cache namespace) must include a schema version (e.g. `schema2`) so old trees rebuild.

**Tests** (FakeSummariser emits deterministic `title`, `hook` etc.):
- the `sections` computation, including a chained root and a single leaf
- key-fact number validation (kept when the number is in the source, dropped when it isn't)
- word-limit enforcement
- old-schema JSON still loads

## 2. UI: Macaron Command Centre (frontend, `web/`)

### Tokens (CSS custom properties on `:root`)
```
--bg:#FBF7F2 --panel:#FFFDFA --border:#ECE4D8 --chip:#F3EEE6
--text:#2A2521 --body:#38312B --muted:#5E554C --label:#6B6157 --fact-label:#5A4E3F --fact-sub:#3E362E
--ink-btn:#2A2521 --ink-btn-text:#FFFDFA
--radius:20px --radius-sm:12px --pill:999px
--display:'Fraunces',serif  --ui:'Work Sans',sans-serif
--sec-1..--sec-5 (section hues, from the palette), --hl (current highlighter colour)
```
- Fonts: Google Fonts, Fraunces opsz 9..144 wght 600, and Work Sans 400/600/700.
- The app is **light only** in v2. Remove the old dark theme and the `prefers-color-scheme` dark block, since Macaron is a light system. A dark Macaron is future work.

### Layout: desktop ≥ 1100 px
A CSS grid: `300px | minmax(0,1fr) | 380px` columns and a `72px | 1fr` row. The page scrolls in the middle column; the header, nav and rail are sticky.
- **Header** (fixed 72 px; must never change height):
  - home ⌂
  - two-line title block: the document title in small caps, plus the root `hook` (or root text) in Fraunces 17 px, one line with ellipsis
  - flexible gap
  - the **Palette** button (three mini dots)
  - the zoom pill: **− Less** | `~N min · P% of original` | **More +** (the ink button)
  - The pill's buttons step one expansion **at the viewport-centre anchor**. The readout keeps its ARIA slider role, focusable, with arrow keys and the live region.
- **Left nav "SECTIONS":** one item per `tree.sections` entry: `NN` plus its `title`, with a 10 px dot in its section hue.
  - The **current section** (the section-level ancestor of the anchored node) gets a full pastel fill and weight 600, with no dot.
  - Clicking an item jumps there using the existing `jumpToNode`.
  - The Z-hint text sits at the bottom of the nav.
- **Middle (the reading flow)**, rendered per section in document order:
  - The first time a section appears in the frontier, render a **section header**:
    - kicker: the pill `NN` in its hue, then `· SECTION TITLE UPPER`
    - an `h1` title in Fraunces 46/1.1
    - the `hook` as a 19 px muted lede
  - Then that section's frontier nodes, each as a block with an `h2` subhead (the node `title`, 17 px bold) and its text. The **text of leaves is verbatim**.
  - Blocks flow in a **2-column grid** (`repeat(2,minmax(0,1fr))`, gap 36 px) within each section when each column would hold about 45 characters (otherwise one column; see "Automatic single column" below). Code, equations and atomic nodes span both columns.
  - Summaries vs originals: summaries in Work Sans 17 px `--body`; originals in the same face, with a 2 px left rule in the section hue plus the subhead. The distinction must be legible without colour: keep the rule, and add a small `¶ n` provenance label next to the subhead of original text, and `¶ a–b` on summaries.
  - When the frontier is just the root, show the root as a big Fraunces hero with its hook.
- **Right rail** (sticky, top 72 + 36 px), for the **current section**:
  1. **KEY FACT** card, if `key_fact`: background in the section hue, `big` in Fraunces 34, `detail` 14 px. Hovering it shows its cited source (reuse the source popover).
  2. **Steps** card, if `steps`: "HOW IT WORKS", with chips on `--sec-(n+1)` and the last chip on the current section hue in weight 600. Otherwise show **KEY POINTS** (bullets) if present.
  3. **UP NEXT · NN**: the next section's title (Fraunces 21) and hook. Clicking jumps there.
  - The rail cards crossfade (180 ms) when the current section changes, with an instant fallback under reduced motion.
- **Minimal chrome (`m`):** hides the header, nav, map, rail and column handles (faded, then `visibility: hidden` so they leave the Tab order, and with zero padding so they cannot widen the page); the middle goes full width (capped at 1200 px). The small diamond, bottom right, and `m` bring the chrome back.
- **Automatic single column:** two columns only while each would still give about 45 characters a line (`MIN_CPL` in `app.js`). `applyColumnMode` measures the average character width of running text in the real reader font (a hidden probe, canvas `measureText`, plus letter-spacing, with 10% allowed for words that wrap), takes the reading area's inner width, and sets `.one-col` on `#content` (the section grid) and `.ov-one-col` (the overview tiles) when two columns would be under that. It re-runs on resize, font load, column drags, map open and close, and settings changes, holding the reading position across the reflow. At 1366x768 with the nav and rail open the reader is one column (about 65 characters a line; two columns gave about 24); two columns return when each can hold about 45 (about 1920 wide). `#content` carries `data-cols` and `data-cpl` (the estimate) for tests.
- **Breadcrumb:** unnecessary now (the nav shows position), so remove it.
- **Tablet and phone (< 1100 px):** single column. The nav becomes a horizontally scrollable pill row under the header. The rail cards move below each section header. The header's two-line block becomes one line. It must work at 390 px with a 16 px gutter.
- **Start screen and "gist coming…":** restyle in Macaron (cream, Fraunces heading, panel cards, ink primary button). The recent list stays as plain links.

### Palette panel (from the `Macaron-Palette` board)
- The **Palette** button toggles a panel: a popover anchored under the header's right side, 420 px, with a panel background, 22 px radius and shadow. It closes with Esc or ✕ and traps focus while open.
- **16 pastels** (name, hex):
  - Blush `#F6D5D1`
  - Pastel pink `#F9D3E3`
  - Rose quartz `#F3C6D3`
  - Candy floss `#FBDDEB`
  - Peach `#FBDCC8`
  - Apricot `#F8E0B8`
  - Butter `#F7E8B5`
  - Lemon `#F5F0B8`
  - Pistachio `#E1ECCB`
  - Sage `#D5E6CF`
  - Mint `#D2EBDD`
  - Seafoam `#CFE8E1`
  - Sky `#D3E4F2`
  - Periwinkle `#D9DDF4`
  - Lavender `#E2D8F0`
  - Lilac `#EBD9F0`
- **Presets** (sections; highlighter):
  - **Macaron:** `[F6D5D1, D5E6CF, F7E8B5, D3E4F2, E2D8F0]`; `F9D3E3`
  - **Pink party:** `[F9D3E3, F3C6D3, FBDDEB, F6D5D1, EBD9F0]`; `F9D3E3`
  - **Garden:** `[E1ECCB, D5E6CF, F5F0B8, FBDCC8, D2EBDD]`; `F5F0B8`
  - **Sky & lilac:** `[D3E4F2, D9DDF4, E2D8F0, CFE8E1, EBD9F0]`; `D9DDF4`
- **Section colours:** five slots. Click a slot, then a swatch. With more than 5 sections, hues cycle (section i uses slot `i mod 5`).
- **Highlighter colour** mode: a swatch sets `--hl` for new highlights.
- **Storage:** everything persists in `localStorage['riemann:palette']`, as `{sections:[5], hl, preset}`, wrapped in try/catch. The default is the Macaron preset with the highlighter set to pastel pink `#F9D3E3`.
- **Accessibility:** swatches are `<button>`s with an `aria-label` (the colour name) and `aria-pressed`, with a visible 2 px ink ring on the selected swatch.
- **Event log:** `palette {preset|slot|hl, value}`.

### Highlights
- **Adding one:** selecting text inside a node's text shows a floating **toolbar** above the selection, with the 7 most-used swatches (blush, pastel pink, rose quartz, butter, sage, sky, lavender), the current `--hl` pre-selected, and a Cancel option. Choosing a swatch creates the highlight.
- **Storage:** `{id, nodeId, start, end, colour}`, where `start` and `end` are char offsets into that node's plain text. Stored in `localStorage['riemann:hl:'+tree_id]`.
- **Rendering:** as a `<mark>` with `background: linear-gradient(transparent 50%, colour 50%)` and ink text.
- **Editing:** clicking a highlight opens the same toolbar with **Remove**.
- **Across zoom:** highlights live on nodes. A node that isn't in the frontier shows nothing, but its highlights come back when you zoom back in. Rendering highlights must never change the node's block height (inline marks only).
- **Event log:** `highlight {action: add|recolour|remove, node_id, colour}`.

### Skim form (added 2026-09-30)
- Every summary except the root has two forms:
  - **skim:** its title plus its `key_points` as bullets, or the `hook` when it has no key points
  - **prose:** its summary paragraph
- Zooming in on a summary goes skim → prose → its parts, and parts that are summaries start as skim.
- The zoom sequence therefore has two kinds of token: `"~id"` (show id as prose) and `"id"` (expand). This is in both `frontier.py` and `frontier.js`, and the parity test covers it.
- Word counts and the readout count a skim block as its title plus bullets.
- A section's own block drops its title, because the section header already shows it. The rail hides KEY POINTS while those bullets are on the page.
- Why: Sam found the jump from one paragraph to full section paragraphs too big and wanted to "get the idea first reading titles".

### Unchanged behaviour to re-verify
- Pointer-anchored zoom with 0 px drift in the 2-column layout.
- No layout shift from the sticky header, nav or rail when the current section changes: rail height changes must not move the middle column.
- Resume.
- The event log.
- The JS/Python frontier parity test.


## In-document search

`/` or Ctrl+F (only while a document is open), or the magnifier button in the header, opens a search box
(`#search-bar`: a labelled input, an `aria-live="polite"` count such as "3 of 12" or "No matches", previous and next
buttons, close). It searches the **whole document**, not just what is expanded: every node's title, key points and text
(so every source leaf), and the overview card. Enter or the down arrow goes to the next match, Shift+Enter or the up
arrow to the previous one (wrapping). Esc closes the box and clears the marks; Ctrl+F pressed again inside the box is
left to the browser's own find. A query needs 2 or more characters; matching ignores case.

A match that is not on the page opens the shallowest form that contains it: the node is revealed with the same
`kToReveal` path as a jump (a match in a summary's text also asks for its prose form); if that node has already been
opened into its parts, the page is re-composed around it (a fresh expansion order anchored there), so it shows whole.
Marked text is wrapped in `span.search-hit` (the current match also `.search-current` with an outline, so it does not
rely on colour); marks are re-applied after every re-render while the box is open, and never change the text offsets
that highlights use. Counting and marking use one text-extraction routine (blocks separated by newlines), so they agree.

The log gets one `search` event per settled query with only `query_length` and `matches` (a number), never the text.


## Zoom history

Alt+Left returns to the previous zoom level **and** position; Alt+Right goes forward. An entry is the page as it was
(what is open and in which form, the anchor passage, and where that passage sat on screen) and is taken at the end of
each zoom gesture (Z drag or sticky mode, Ctrl+wheel burst, a key or pill step), section jump (nav, "Up next", a `¶`
link), search jump and map jump, after a 650 ms settle so a smooth scroll has finished. Entries within about a second of
the last one merge into it (the first entry, taken on open, never merges); a new entry after going back drops the forward
ones. Going back re-composes that page (same open passages, same forms) and puts the anchor passage back at the screen
position it had. After a big jump (3 or more zoom steps, or another section) a "← Back" button appears under the zoom
pill for 6 seconds. Alt+Left and Alt+Right are always taken by this while a document is open, so they never reach the
browser's Back; the header's home button and the browser's own Back and Forward still work through the `#/t/<id>`
hash, and the history is in memory per open document. The log gets a `history` event (`dir`, `via`).


## Reading settings

The palette panel has a **Reading** section with two settings, saved in `localStorage['riemann:reading']` as
`{spacing: bool, width: "narrow"|"normal"|"wide"}` and checked on read like the palette (anything else gives the
defaults: spacing off, normal):

- **Wider letter spacing** (off by default): `--reading-ls: 0.04em` on the reading text (summaries, source passages,
  key points, titles, hooks and the overview tiles).
- **Reading width**: caps one reading column at 34, 40 or 48 em of the 17 px body size (578, 680 or 816 px) with
  `--read-em`; normal is 40 em, which does not bind at the usual window sizes, so it is the width the reader always had.

Both feed the automatic single column: the character width includes the letter-spacing, and the column cap is the
reading width, so turning letter-spacing on can turn two columns into one a little sooner. Changing either holds the
reading position.


## Maths

`$...$` (inline) and `$$...$$` (display) LaTeX in summaries and source passages is drawn with KaTeX, loaded from
cdn.jsdelivr.net like `marked` (pinned, `web/index.html`); if it does not load, a formula stays as its LaTeX text. Plain
dollar amounts are not maths: an inline formula needs a non-space after the opening `$` (which is not directly after a
letter or digit), a non-space before the closing `$` that is not directly followed by a digit, and a letter, backslash,
`^`, `_` or `=` inside, so "$5 and $10", "US$5", "$5-$10" and "$5$" stay text; `\$`, inline code and fenced blocks are
left alone (`web/mathtext.js`, tested in `tests/test_web_math.py`).

**Highlights.** Highlights are stored as text offsets in a block. Each formula is one atomic `span.math` whose
`data-len` is the length of its LaTeX source (delimiters included); `textUnits` / `findTextPos` / `selectionOffsets` in
`app.js` count it as exactly that many characters, whether the span holds KaTeX's markup or the LaTeX text, so offsets do
not depend on how KaTeX lays it out and offsets saved before maths was rendered still fit. A selection that starts or ends
inside a formula takes the whole formula. Formulas are not searched.
