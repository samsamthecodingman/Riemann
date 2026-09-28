# Riemann: reading UI design brief (for Claude Design)

**Claude Design canvas:** https://claude.ai/artifact/GBpLU32rdKLGYg73DtwkxJ (private to Sam). It holds this brief, a baseline board of the current build, and the two real trees in `data/`.

**The ask:** design the visual language and screens for Riemann's reading view, the "zoom dial" for text. Behaviour already works (v1 is built and tested); this is about how it looks and feels. Where a choice would change behaviour, it's marked **fixed** or **open** below.

## What Riemann is
- **Riemann** is a personal assistant for Sam, an engineering student with ADHD whose attention, energy and motivation fluctuate a lot.
- **The first feature:** paste any text, file or URL, and it becomes an **adaptive abstraction tree** that you zoom through continuously.
  - The top is a one-line gist.
  - The bottom is the original text.
  - Between them are summaries that each cite the passages they came from.
- **Depth adapts to the content.** A 130-word note has about 3 levels; a 6,000-word article about 6. There are no named levels or modes.
- **The goal:** reach whatever depth of understanding you want in the least time, in a way that flexes with low- and high-capacity days.
- **Later,** the same tree drives a "spatial view", a map-like layout of the document. This brief covers only the reading view.

## How it works (fixed)
- **Zoom where you point.**
  - Hold **Z** and move the mouse → for more detail, ← for less.
  - **Ctrl+scroll** or a trackpad **pinch** does the same.
  - **←/→** or **=/−** step one passage.
- **The passage under the pointer never moves on screen while zooming** (0 px drift, measured). Detail unfolds *outward from where you're reading*, one passage at a time.
- **The dial isn't a control you reach for.** It's a thin passive indicator plus a quiet readout: `~2 min · 33% of original` (238 wpm). It still works as a keyboard and screen-reader slider.
- **The root gist stays pinned** as a header at every zoom level. A home control returns to the gist.
- **A breadcrumb** (the nearest ancestors' first clauses) appears when your passage's ancestors are off-screen. It's a single-line overlay under the header and **must never change the header's height**, because that shifts the text the zoom is holding still.
- **Summaries link to their source.** Hovering a summary sentence shows 1–2 real sentences from the original; clicking jumps there.
- **Resume:** reopening a document restores where you were, with a 4-second card: "Back where you left off: …".
- **The first-use hint** explains the gesture once, then never again.
- **Minimal-chrome mode (`m`)** leaves just the text and indicator.

## Non-negotiables (from the research; `research/RIEMANN-ABSORPTION-MODEL.md`)
1. **Never** show progress bars, "% read", streaks, badges, countdowns, or "you didn't finish" language. They create shame and avoidance for ADHD users.
2. **Never** name levels ("L2", "Summary", "Detail"). Depth is continuous; the readout is the only depth cue.
3. **Never** use language implying Sam understands something just because he read a summary. "Gist" is fine; "you now understand" is not.
4. **Reading column** is 60–75 characters, generous line height, and body text at least 16 px.
5. **Nothing in the flow above the text may change height during a zoom.** Headers are fixed-height, and overlays sit out of the flow.
6. **Reduced motion:** any transition has an instant fallback under `prefers-reduced-motion`. Level changes crossfade in about 180 ms; persistent headings slide (FLIP). No big scaling animations, which cause vestibular discomfort.
7. **Accessibility:**
   - text contrast ≥ 4.5:1
   - visible focus
   - real buttons and links
   - touch targets ≥ 44 px
   - colour never the only cue
8. **It must work at phone width** (390 px) with a 16 px gutter.
9. **Calm and low-arousal, but not sterile.** Delay and clutter are aversive for ADHD, so the gist appears instantly and there's one thing to look at. Novelty belongs at the edges, never in the core layout, which stays stable over time.

## Open to design
- The whole visual language: type pairing, palette, and light *and* dark themes. The current build is a placeholder warm-dark.
- How summaries vs original text are distinguished. Today it's a subtle left rule on original text and a dotted underline on hover for summaries. It must be legible without colour alone.
- The readout and indicator: how depth is felt without being a progress bar.
- **The "transition feel":** how a passage unfolding into its children should look within the constraints above.
- The source popover, breadcrumb, resume card and first-use hint.
- The start screen: paste box, file, URL, and recent documents. Recent documents are **plain links**, with no counts or "unfinished" markers.
- **The "gist coming…" state:** the root gist arrives about 1–2 s after opening, and the original text shows instantly.
- Minimal-chrome mode, the "not helpful" link, and the error state (e.g. the model is unavailable).
- **Optional, forward-looking:** how capacity states might change density, e.g. a low-capacity view showing one thing at a time. Design at most one exploratory board for this.

## Screens to produce (suggested artboards)
1. Reading view on desktop (1280×800), zoomed out: gist plus a ~2-minute summary.
2. The same view zoomed in partway: mixed summaries and original passages. Show the summary/original distinction and a breadcrumb.
3. Source popover open on a summary sentence.
4. Phone reading view (390×844).
5. Start screen, including the "gist coming…" building state.
6. Dark and light variants of at least board 1.
7. Micro-states: the resume card, first-use hint, error, and minimal chrome.

## Real content (no lorem ipsum)
The canvas includes two real abstraction trees in `data/`, in the same JSON format the app uses:
- `data/internet-1300w.json`: *How the Internet Actually Moves Your Data*, 1,290 words, 4 levels.
- `data/software-5800w.json`: *How Large Software Systems Actually Get Built, Run, and Kept Alive*, 5,829 words, 6 levels.

Tree format: `nodes{id: {depth, text, words, children[], parent, is_leaf, source_span, cites[], importance}}`, plus `root` and `title`. What's on screen at any moment is a "frontier": a set of nodes in document order, none an ancestor of another, where leaves are the original text and the others are summaries. The "Current v1" artboard shows today's build with real content, as a baseline to improve on, not a style to keep.

## Handing it back
When you're happy, Sam sends the canvas link to Claude Code. It reads the design and implements it in `web/`: tokens and CSS first, then markup. It re-runs the zoom-drift and accessibility checks. Anything that conflicts with a **fixed** item or a non-negotiable gets flagged, not silently changed.
