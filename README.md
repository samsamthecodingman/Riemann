# Riemann

**Read anything at the depth you need.**

Riemann is a reading assistant built for an ADHD brain. Give it an article, a paper, lecture notes or an assignment brief, and it builds an *abstraction tree*: a one-to-two-minute gist at the top, section titles and bullets below that, then summaries, and finally the original paragraphs. A continuous zoom dial moves you up and down that tree, passage by passage, and the page stays pinned to wherever you were looking.

![Home: paste text, drop a file or give a link](docs/screenshots/home.png)

## Why

Long documents are hard to start and easy to lose your place in. Riemann starts from the smallest useful version of the text and lets you open up only the parts you care about, so there's always a quick way in and you never have to hold the whole thing in your head.

The design is grounded in the research notes in [`research/`](research/). In particular [`RIEMANN-ABSORPTION-MODEL.md`](research/RIEMANN-ABSORPTION-MODEL.md) covers what the evidence does and doesn't support for adult ADHD reading.

## What it does

### Gist first, then zoom where you look

Every document opens as a short gist: section titles with two or three skim bullets each. Everything links back to the source paragraphs it came from (`¶ 1–9`).

![Gist view: section titles with skim bullets](docs/screenshots/gist.png)

Zoom in and the section you're pointing at unfolds into titled sub-points, then prose, then the original text. Nothing else on the page moves.

![One level deeper: titled sub-points under the section](docs/screenshots/skim.png)

**How to zoom**

| Input | Zoom |
|---|---|
| Mouse | Hold **Z** and move the mouse left or right over a passage |
| Trackpad | Tap **Z**, then scroll or swipe with two fingers (tap Z again, press Esc or pause to stop) |
| Pinch | Pinch on the trackpad (or Ctrl + scroll wheel) |
| Keyboard | **=** / **−** step the whole page; **Home** / **End** jump to the gist or the full text |
| Buttons | **− Less** / **More +** in the header |

The header always shows roughly how long the current view takes to read and what share of the original it covers.

### A map of the document

Press **Map** (or **G**) for a region map of the whole document beside the reader. Sections are coloured districts sized by length, and the map mirrors the reader: what's expanded in the reader is split into its parts on the map, and **You are here** follows your scrolling. Click any region to jump there. Scroll to zoom the map, drag to move it, and **Fit** resets it.

![The map beside the reader](docs/screenshots/map.png)

On a laptop screen the map switches to a compact mode that shows only numbers and short key titles. Drag the edge between the columns to make any of them wider or narrower. The widths are remembered, and dragging the map wider brings back the detailed version.

![Compact map on a 1366×768 laptop screen](docs/screenshots/laptop.png)

### Built around what the text is *for*

Pick a goal before building, or let Riemann suggest one from the title and format:

| Goal | Summaries focus on |
|---|---|
| **Learn it** | Ideas, explanations and how things connect |
| **Do it** | Deliverables, steps, deadlines and marking criteria |
| **Decide** | Options, trade-offs and the recommendation |
| **Look it up** | Facts, numbers and definitions |
| **Plan** | Timeline, dependencies and owners |
| **Reply** | What's being asked of you and what to say |

The same document built for a different goal is kept as a separate version.

### A quick check-in (optional)

A folding panel on the home page asks about energy, mood, sleep, caffeine and meds, with one tap each. It only changes how a document *opens*, never what the summaries say. For example, low energy or short sleep opens at about a one-minute read with the map closed. Each check-in counts for four hours, and a small note always shows what was adjusted, with an undo.

### Other details

- **Palette:** swap the pastel section colours. The Palette panel closes when you click away.
- **Key facts and Up next:** the right-hand rail pulls out a key number and previews the next section.
- **Models:** choose the summarising model from the home page. The default is Claude Sonnet 5.5.
- **Local only:** trees and the reading-event log live on your machine, under `~/.local/share/riemann/` by default. Nothing is sent anywhere except the model calls themselves.
- **Accessibility:** it respects reduced motion, all interactive parts are buttons with labels, and it has a full-screen map sheet on phones.

## Running it

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

```bash
uv run uvicorn riemann.server:app --port 8765
```

Then open <http://localhost:8765>.

### Model access

Riemann summarises through one of two providers, chosen with `RIEMANN_PROVIDER`:

| `RIEMANN_PROVIDER` | Uses |
|---|---|
| `proxy` (default) | An OpenAI-compatible proxy at `RIEMANN_PROXY_URL` (default `http://127.0.0.1:8317`). The key comes from `RIEMANN_PROXY_KEY`. |
| `agent-sdk` | Your local Claude Code login, through the Claude Agent SDK |

Other settings:

| Variable | Default | Purpose |
|---|---|---|
| `RIEMANN_MODEL` | `claude-sonnet-5-5` | Default summarising model |
| `RIEMANN_DATA_DIR` | `~/.local/share/riemann` | Tree cache and event log |

### Tests

```bash
uv run pytest -q
```

The suite includes a parity test that runs the JavaScript zoom logic (`web/frontier.js`) in Node against its Python twin, so Node needs to be installed.

## How it works

```
text / file / URL
      │  chunk into leaves (source paragraphs)
      ▼
abstraction tree   ← built bottom-up by the model: each parent summarises
      │              its children, with titles, skim bullets, short titles
      │              and key facts, shaped by the chosen goal
      ▼
expansion sequence ← an ordering of "open this node" steps outward from
      │              where you're looking
      ▼
zoom dial z ∈ [0,1] → frontier (what's shown, and in which form)
```

- **Backend** (`riemann/`): FastAPI. `/api/abstract` streams the build over server-sent events so the loading screen shows real progress. Trees are cached by a hash of the text, model and goal.
- **Frontend** (`web/`): plain JavaScript, no build step.
  - `app.js`: the reader
  - `frontier.js`: the zoom maths
  - `map.js` and `maplayout.js`: the map, an ordered strip treemap
  - `cols.js`: resizable columns
  - `objective.js`: goal suggestion
- **Specs**: [`docs/v1-build-spec.md`](docs/v1-build-spec.md), [`docs/v2-macaron-spec.md`](docs/v2-macaron-spec.md) (reader design) and [`docs/spatial-view-spec.md`](docs/spatial-view-spec.md) (the map).

## Status

Riemann is a personal project and still early. Reader, map, goals and check-in are working. Next up: a library map across documents, and better titles for pasted text.
