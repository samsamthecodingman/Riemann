# Riemann spatial view v1: Map A2, "the map mirrors the reader" (build spec)

**Design source:** the Claude Design canvas https://claude.ai/artifact/GBpLU32rdKLGYg73DtwkxJ, board **Map-A2-Mirror**. The generator for that board is `design/spatial-mockups-a.py`; read it for the exact look (colours, sizes, tile styles).

**Chosen by Sam (2026-09-30):**
- a map of one document
- beside the reader
- as a region map that mirrors the reader's zoom

**Keep everything in `docs/v2-macaron-spec.md`**, including:
- zoom-at-pointer with 0 px drift
- the skim form
- highlights and the palette
- no progress bars or read/unread marks (the map shows position only, never "read")

## Concept
- The map is a **nested region map (treemap) of the document**:
  - Sections are pastel districts, sized by their source length and laid out in reading order.
  - Every node has a **fixed rectangle**, computed once from the tree structure. Positions never move as you zoom the reader, which preserves the mental map.
- The map **draws the reader's current frontier**:
  - A node that is expanded in the reader is drawn as a frame (header plus its children's tiles).
  - A node on the frontier is drawn as a solid tile.
  - Nodes above the section level are never drawn; the map always shows at least the sections.
- The frontier passages **currently visible on screen** in the reader get a 3 px ink outline. A "You are here" pill sits on the first of them.
- Clicking any tile or district calls the reader's existing `jumpToNode(id)`.

## Files
- `web/maplayout.js` (new): a **pure** layout function with no DOM. It exposes `window.MapLayout = { layout }` and must also run under Node (see the tests).
- `web/map.js` (new): the panel, rendering, camera and wiring. It exposes `window.RiemannMap = { init(api), update(), open(), close(), toggle() }`.
- `web/app.js`: small hooks only, listed under Integration. Do **not** change `frontier.js`, the anchor maths (`offsetAtY`, `yOfOffset`, `setZ` pinning) or the skim logic.
- `web/index.html` and `web/style.css`: the panel markup and styles.
- The backend change is optional short titles (see Backend).
- Tests: `tests/test_maplayout.py`, which runs `web/maplayout.js` in Node, following the pattern in `tests/test_frontier_parity.py`. Also a backend test for short titles.

## Layout (`maplayout.js`)
Signature: `layout(tree, W, H, opts) -> Map<nodeId, {x, y, w, h, headerH, side}>`.
- It is deterministic from the tree plus `W` and `H`. The same inputs always give the same output. There is no randomness and no dependence on the frontier.
- **Top level:** `tree.sections`, or the root's children if there are no sections, or just the root for a single leaf. They fill `(pad, pad, W-2pad, H-2pad)` with `pad = 12` and gaps of 8 px.
- **Ordered strip treemap** (Bederson's "strip" layout):
  - Items stay in document order and are packed into strips (rows when the container is at least as wide as it is tall, otherwise columns).
  - An item joins the current strip while that keeps the strip's average aspect ratio closer to 1. Otherwise it starts a new strip.
  - Weight is `max(node.words_in_source, 0.06 × parent total)`, a floor so small parts stay visible. `words_in_source` is the sum of `words` over its leaves, or `source_span` length ÷ 6 as a fallback.
- **Internal nodes** reserve a header, and their children are laid out recursively in the remaining content rectangle (inset 10 px, with 6 px gaps):
  - A section header is 12 + 36 (the NN numeral) + 6 + title lines × 19.5 + 6 + 17 (meta line) + 10.
  - A deeper internal node's header is 8 + title lines × 17 + 8.
  - Title lines are estimated as `ceil(chars / ((width-28) / (fontPx*0.62)))`, with a 15 px title for sections and 13 px below that.
  - If the rectangle is wide (`w > 1.8h`) the header goes on the left (`side: true`, header width `min(200, 0.35w)`) and the children fill the right-hand side.
  - If the content rectangle would be under 24 px tall or wide, the children get no rectangles and the node always draws solid.
- **Tests:** determinism, children inside their parent's content rectangle, no overlaps between siblings, reading order preserved (row-major within strips), every node from the sections down placed, and sizes roughly proportional to weight (within 40%).

## Rendering (`map.js`)
- **Panel:**
  - A **Map** toggle button in the header, left of the Palette button, styled as in the mockup (ink when active, `aria-pressed`). The `g` key also toggles it; ignore it with modifiers or when typing in an input.
  - The state persists in `localStorage['riemann:map']`, wrapped in try/catch.
- **Desktop (≥ 1100 px):**
  - The map **replaces the left SECTIONS nav column**, which becomes `clamp(440px, 36vw, 640px)` wide while the map is open (a class on `#app`, e.g. `map-open`). The nav is hidden while the map is open.
  - The panel is sticky under the header, full height.
  - When toggling, keep the reading position: record the anchor node's top before the toggle and scroll it back to the same y after the reflow, using the existing `contentTopY` and anchor state. It's fine to expose a small helper from `app.js` for this.
- **Under 1100 px:** a full-screen sheet over the reader, with a close button (✕). Esc closes it.
- **Panel chrome, as in the mockup:**
  - a "MAP" label and a subtitle such as "Mirrors the reader · 02 is open"
  - Fit, −, + and ✕ buttons (44 px targets on touch)
  - a hint line at the bottom: "Scroll to zoom · drag to move · click a region to read it"
- **Drawing:** absolutely positioned `<button>`s in a map frame (rounded, background `#F5EFE6`).
  - Walk from the sections downward. For node `n`:
    - If `n` has a descendant on the frontier (it is expanded in the reader), draw it as a **frame**: its colour, header text, then recurse into its children.
    - Otherwise draw a **solid tile**. The tile holds the smallest node on the frontier that contains it, or `n` itself; when the frontier is above the sections, sections draw solid.
  - **Section districts:** background `var(--sec-N)` (section i uses slot `i mod 5 + 1`, matching the reader) and radius 14. The header has the NN numeral (Fraunces 36/30), the title (15 px, 700) and the meta line "3 parts · 718 words". A solid district also shows the section hook (13 px, muted) when there's room.
  - **Deeper tiles:** `rgba(255,253,250,0.78)` on the district colour, radius 10, **content aligned to the top** (buttons centre vertically by default, so use flex-start). Label choice:
    - the full title if it fits
    - otherwise `short_title` if the node has one
    - otherwise the title on one line with an ellipsis
    - no text if the tile is under 26 px tall
    - leaves show their `¶ n` label before the title
  - Text is never below 13 px (12 px only for the uppercase meta labels, as in the reader).
- **"You are here":**
  - After each reader render and on scroll (debounced about 120 ms), find the frontier nodes whose blocks intersect the reader's visible area (below `contentTopY`).
  - Outline their tiles with `outline: 3px solid var(--text); outline-offset: 2px` and put the pill on the first one.
  - If a visible node sits inside a solid ancestor tile, outline that tile.
- **Camera:**
  - The wheel (without Ctrl) zooms the map at the pointer, dragging pans, and Fit resets.
  - Implement zoom by **re-running the layout at W·s × H·s** and translating, **not** with a CSS `scale()`. Text stays the same size and tiles gain room, so labels upgrade naturally (semantic zoom).
  - Scale range is 1 to 6. Re-render inside rAF.
  - The camera never moves by itself.
  - Clicks only fire if the pointer moved less than 4 px (so a drag doesn't count as a click).
- **Updates:**
  - Call `RiemannMap.update()` at the end of `render()` in `app.js`, when the tree opens, on palette change and on window resize.
  - Keep it cheap: typical documents have under 200 visible tiles.
  - New tiles may fade in (opacity 150 ms). There must be no motion under reduced motion.
- **Accessibility:**
  - Each tile is a `<button>` with `aria-label` set to the full title.
  - The panel is a `<section aria-label="Document map">`.
  - The reader remains the primary path.
- **Events:** `logEvent("map", {action: "open"|"close"|"jump"|"zoom", node_id?})`. Debounce zoom events.

## Integration (`app.js`)
- After `openTree` and at the end of `render()`: `window.RiemannMap && RiemannMap.update()`.
- Give the map what it needs through `RiemannMap.init({...})`:
  - `getTree`, `getFrontier`, `getProse`
  - `sectionsOf`, `sectionAncestor`, `nodeTitle`, `nodeProvenance`
  - `jumpToNode`, `logEvent`, `contentTopY`
  - a `visibleFrontierIds()` helper
  - a `keepReadingPosition(fn)` helper for toggling
- Leaving the document (`showStartScreen`) closes or clears the map.

## Backend: short titles (small)
- Extend the per-parent summarise JSON in `riemann/abstraction/build.py`:
  - `short_title` for the parent
  - `child_short_titles` (`{child_id: "≤3 words"}`)
- Add an optional `short_title: str | None = None` to `Node` in `model.py`.
- Validate: at most 3 words and 24 characters; otherwise drop it. The FakeSummariser emits deterministic ones.
- **Do not bump `SCHEMA_VERSION`.** The field is optional, so existing trees keep working and fall back to ellipsis labels, and new builds get short titles.
- Add a test.

## Verification (the worker must do this and report the numbers)
- `uv run pytest -q`: all existing tests, plus the new ones, pass.
- The browser pane, using the `riemann` preview. Front the tab first; a background tab runs at 3 fps. Use `?fixture=1` and the real tree `#/t/f0ccd10ec67bf72e` at 1600×900.
  - The map opens with the button and with `g`, and its state persists across a reload.
  - At the gist, 4 solid districts show. Zoom into a section in the reader and it splits into its parts. Zoom out and it merges back.
  - The outline follows reader scrolling.
  - Clicking a tile jumps the reader there.
  - Wheel zoom at the pointer keeps the point under the cursor fixed (report the drift in px). Labels upgrade on zoom. Fit resets.
  - Toggling the map keeps the anchor passage within ±4 px.
  - Pointer-anchored zoom in the reader still drifts under 2 px with the map open (re-run the existing Z-drag check).
  - No text below 13 px on tiles, and no text overflowing tiles (check programmatically: `scrollHeight > clientHeight` on tiles with visible text).
  - The 390×844 sheet works. No console errors. Reduced motion is honoured.
- Commit with a clear message ending in `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`, and push to origin master.
