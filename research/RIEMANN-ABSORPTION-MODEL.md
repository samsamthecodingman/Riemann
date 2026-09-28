# The Riemann Absorption Model

*Synthesis of a research fleet run, 2026-09-28. The fleet had 17 web-research workers across three waves, plus an idea-generation worker, a skeptic worker and a fact-check pass. Source reports are in `reports/`, and every claim here traces to one of them. Evidence grades: **S** = strong (meta-analyses or replicated), **M** = moderate, **W** = weak/preliminary, **✗** = myth. Items marked ⚑ were independently fact-checked (see `reports/19-factcheck.md`).*

---

## L0: the one-liner

**Riemann should let Sam steer two dials: depth (how much detail) and activity (how much he does versus just reads). The system picks sensible starting points from his purpose, current state and prior knowledge, and four guarantees hold everywhere: every claim links back to its source, he never loses his place, nothing makes him feel bad, and it never pretends he understands more than he does.**

## L1: the two-minute version

1. **The zoom dial is a good idea and it has a long history.** Ted Nelson proposed "stretchtext" in 1970. It stalled because someone had to write every level by hand, and LLMs remove that barrier. Recursive summary trees (RAPTOR, GraphRAG) show that having several levels available beats having a single summary.
2. **The biggest risk is not boredom but false understanding.** Easy summaries create an *illusion of understanding* (S). LLM summaries also contain errors often enough to matter: 20–45% of multi-document summaries contain hallucinated content in benchmarks ⚑ (M/S). Errors also compound as you summarise summaries.
   - The fixes are cheap: link every claim to its source, add a one-line note of what each level leaves out, and occasionally ask Sam to make a quick prediction. Riemann should never say "you understand X", only "you have the gist".
3. **Sam's attention is a moving target, not a fixed budget.** In ADHD, the core marker is variability *within the same person* (S). Capacity and emotional state are separate signals that affect different things (S).
   - Default to a safe floor (L0/L1) and let him re-enter at any level without penalty.
   - Take explicit one-tap input over guessing, and learn slowly from behaviour.
4. **The strongest lever in education is fast, low-stakes feedback loops** (S, effect sizes 0.4–0.7). Detecting his state is secondary. Every dial movement should respond instantly, and occasional ~5-second retrieval checks are worth more than any clever inference.
5. **Starting is the hardest part.** Delay aversion and avoidance mean an instant, low-commitment L0 is *the* anti-avoidance mechanism, not just a convenience.
   - Never shame: no streaks, no "14 unfinished" badges, and no progress bar at the top.
6. **Orientation is everything in zoomable interfaces.** Keep the L0 line as a persistent header, show a breadcrumb of the ancestor levels, give things distinct landmark tags, and keep a home anchor.
   - Later, the spatial view should show an overview alongside the detail, be local to one document (never a "graph of everything"), and keep positions stable.
7. **Match the format to the content, never to "learning styles"** (✗ myth).
   - Use audio for short levels and diagrams for structure.
   - Worked examples and code stay nearly verbatim.
   - Modality (text, audio or map) is its own control, separate from the zoom dial.
8. **Adapt, but let Sam hold the wheel.** Giving learners full control averages about zero benefit (M), so the system suggests a starting level and Sam can always override it.
   - Show *why* it chose that level. This "open learner model" improves both trust and self-correction.
   - Keep today's state separate from long-term preferences so one bad day doesn't retrain the system.

---

## 1. The model

```
                ┌──────────── INPUTS (what Riemann reads about Sam) ────────────┐
                │ PURPOSE    gist · decide · reply/act · study · remember         │
                │ STATE      capacity (low/med/high) × affect (anxious/neutral/calm)│
                │            ·fast (this session) and slow (this week) timescales │
                │ KNOWLEDGE  topic familiarity: none/familiar/proficient (ordinal)│
                └───────────────────────────────┬───────────────────────────────┘
                                                ▼
   ┌────────────── DIALS (Sam can grab any of them; the system only sets defaults) ─────────────┐
   │ DEPTH      L0 gist ─ L1 2-min ─ L2 sections ─ L3 source          (zoom dial)              │
   │ ACTIVITY   read ─ predict-before-reveal ─ retrieval check ─ build/edit the map (learn mode) │
   │ MODALITY   text ─ text+synced audio ─ audio ─ structure map        (sticky, separate)      │
   └───────────────────────────────┬────────────────────────────────────────────────────────────┘
                                   ▼
   ┌──────────── INVARIANTS (hold at every setting, for everyone) ────────────┐
   │ GROUNDED   every claim → source span; "leaves out" line; faithfulness flag│
   │ ORIENTED   L0 header · breadcrumb ≤3 · landmarks · home · stable layout   │
   │ FORGIVING  no streaks/badges/top progress bars; shame-neutral resume      │
   │ HONEST     "gist" ≠ "understand"; no fake relevance; show why adapted     │
   │ ACCESSIBLE keyboard/ARIA slider · reduced motion · spacing controls       │
   └───────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
   LOOP  rules give sane defaults → cheap signals (dwell, dial moves, re-visits,
         idle, 1-tap probes, explicit "not helpful") → slow per-user learning
         (contextual bandit, decayed rewards) → shown back to Sam (open learner model)
```

### 1.1 Purpose sets *what* each level contains

- Relevance instructions change what readers encode without slowing them down (McCrudden & Schraw, M–S). Condition L1 and L2 on a small, closed set of purposes: study, decide, reply/act, curiosity, look-up.
- Infer the purpose from context (an exam in the calendar, the document's source, open tasks). Show it as a chip Sam can correct in one tap, rather than asking up front.
- **Don't write "this matters for your ECE4078 lab because…".** Relevance that the system asserts can backfire, but relevance the user generates works (Hulleman & Harackiewicz, S). Offer an optional "why does this matter to you?" prompt and reuse Sam's own words.
- Purpose also sets the activity dial:
  - **Reference and decide modes** stay frictionless.
  - **Study and remember modes** turn on generative touches. Bastani et al. (PNAS) found that AI help without guardrails harms unaided performance.

### 1.2 State sets the defaults, not the ceiling

Capacity and affect are two independent axes (Attentional Control Theory: anxiety hits inhibition and task-switching, fatigue hits broad attention). The table below comes from `08-fluctuation`:

| State | Default depth | Modality | Density | Tone |
|---|---|---|---|---|
| Low capacity | L0, with L1 one tap away | text-first, no audio demands | one thing on screen | "here's the short version" |
| Medium, calm | L1, dial fully live | text + optional audio | normal | occasional skippable offers |
| Anxious (any capacity) | L1, **fewer choices and tabs** | text-first, no comparison views | reduce *choices*, not content | grounding line optional |
| High, absorbed (hyperfocus) | last used, or L3 | any | full, side-by-side allowed | silent, with a subtle elapsed-time indicator |

**Inputs, ranked best first:**
1. An optional one-tap check-in, with capacity and affect as separate taps.
2. Rules Sam sets for himself once (implementation intentions, d≈0.65, S). Example: "after 9pm, open at L1".
3. Implicit signals built up over a session.

Never infer medication timing silently. It's ethically fraught and nothing has shown it works. Missing data means "medium/neutral", and the app never blocks.

**Multi-timescale:** keep a fast estimate (today) separate from a slow one (stable preference). For people other than Sam, some conditions (ME/CFS, long COVID) need a *multi-day* energy budget, not a per-session slider (`17-beyond-adhd`).

### 1.3 Prior knowledge sets how much scaffolding to show

- **Expertise reversal (S):** structure that helps novices slows experts down. When Sam knows a topic, skip L1 hand-holding and land closer to L2 or L3.
- **Detecting what he knows:**
  - Default: the cheapest proxy, i.e. has he read this topic before, to what level and how recently.
  - When unsure: a Kalyuga-style rapid true/false check with 2–3 claims (seconds, correlates well with full tests ⚑).
- Show knowledge as an **ordinal ladder** (not started / familiar / proficient), not a knowledge graph. Khan Academy built a graph-shaped knowledge map and replaced it with a simple ladder ⚑.

### 1.4 The loop

- **Signals**, ranked by cost and privacy:
  1. Interaction logs: dwell time per node, dial moves, re-visits, idle gaps, scroll-backs.
  2. One-tap micro-probes at natural breaks.
  3. Explicit "not helpful".
  4. Never webcam or eye-tracking for v1.
- **Reading the signals:**
  - **Confusion** (dwell or re-read spikes on one passage) → *give more*: expand, clarify, show the source. Confusion is productive (D'Mello & Graesser).
  - **Boredom or frustration** (rapid dial-flicking, bailing out) → *back off*: offer L0, or suggest stopping.
- **Learning:** a contextual bandit with rule-based priors and decayed rewards, learning slowly. Run cheap A/B variations on Sam himself (the JITAI-lite approach) instead of hand-tuning rules forever.
- **Show the reasoning:** "Opened at L1 because it's late and this is new to you", with a one-tap "wrong". This open learner model improves both trust and error correction.

---

## 2. Principles with evidence

### 2.1 Building the tree (generation)

| Principle | Grade | Source report |
|---|---|---|
| Generate or check L0/L1 **against the source spans**, not only against the level below; errors amplify in recursive pipelines | M | 01 |
| Store a cheap **faithfulness score** per node (NLI/SummaC-style, or n-gram overlap). Low score → retry, flag with a dashed underline, or fall back to *extractive* highlights (Semantic Reader/Scim pattern) | M | 01, 10 |
| L0 is a **claim, not a topic** ("X causes Y", not "about X"), ≤25 words. Optionally test a "gap question" style, since curiosity boosts memory (Gruber 2014 ⚑) | M | 01, 08 |
| **Validate length and retry once**: LLMs often miss explicit length targets. One benchmark paper is on topic, but the "about half" figure couldn't be confirmed | M | 16 |
| **Two-pass chain-of-density** for L0/L1 (draft → add the missing salient fact at the same length) | M | 01, 16 |
| Keep **causal connectives** ("because / so / which led to"), since narrative form is recalled better | S | 04 |
| Keep **worked examples, procedures, code and equations** nearly verbatim at L2 | S | 04 |
| Follow the **ISO 24495-1** plain-language pillars; audit L0 for idioms (autistic readers take them literally) | M | 16, 17 |
| Keep terminology **consistent across levels** (same name for the same thing) | M | 01 |
| Size levels roughly like Forte's progressive-summarisation funnel: L2 ≈ 20% of source, L1 ≈ 5%, L0 = one line | W | 01 |
| Time estimates use **238 wpm** (Brysbaert ⚑), then **recalibrate to Sam's own measured rate**, since ADHD readers read slower on dense text | S / M | 05, 13 |
| Summaries that are simpler aren't automatically easier: one 2025 study found AI-simplified text no easier once familiarity was controlled ⚑. **Measure it; don't assume it** | M | 17 |

### 2.2 The dial (v1 page)

| Principle | Grade | Source report |
|---|---|---|
| Label every detent with **name, description and read time** ("L1 · 2-min summary · ~1:50"). Progressive disclosure beyond 2 levels confuses people unless every level is labelled ⚑ | M | 12 |
| **Persistent L0 header** plus a **breadcrumb** of ≤3 ancestors (the Workflowy/Logseq pattern) plus a **home** control, to prevent "desert fog" | S | 06, 12 |
| **Anchoring as a space-scale diagram**: hold the source span fixed, sweep the level, and scroll to its ancestor or descendant | M | 06 |
| **Transitions:** FLIP-animate headings (they persist across levels) and crossfade body text over 150–250 ms. Jumps of more than one level are a quick crossfade cut. `prefers-reduced-motion` → instant | M (text-specific: untested) | 02, 12, 17 |
| **Layer-cake layout** for L2: real headings plus 40–80-word bodies, with the claim in the first clause. L2 acts as a *graphic* advance organiser (effect sizes ~1.2 vs ~0.2–0.3 for prose) | M | 02, 05 |
| Keep a **60–75-character column**. Letter, word and line **spacing controls** (evidence-backed); **no "dyslexia font"** (✗) | S | 02, 17 |
| **Discrete, paged levels rather than endless scroll**: paging beats scrolling for comprehension, especially for low working memory | M | 18 |
| **Source-span hover** showing 1–2 real sentences. Checking a claim must take under ~5 s, or the link becomes a trust badge nobody reads (Vasconcelos) | S (mechanism) | 11 |
| A collapsed **"this level leaves out: …"** line on L1/L2 (DiSCo-style: more useful, slightly less easy ⚑) | W | 11 |
| **Accessibility:** `role="slider"` with `aria-valuetext` labels, Arrow/Home/End/PageUp keys, a persistent polite live region (`aria-atomic`), and each level as a heading-navigable region | S | 17 |
| **No top progress bar or "% read".** If progress is shown at all, put it at the bottom and count L0 as progress already made | M | 13 |
| **Instant perceived L0.** Show L3 immediately and stream the levels in; delay is aversive in ADHD | S | 03 |
| Keep a small **"get unstuck"** control visible at all times (W3C COGA) | M | 03, 17 |

### 2.3 Attention, fluctuation and re-entry

| Principle | Grade | Source report |
|---|---|---|
| Re-enter at **any level, any time**: no forced "start at L0" | S | 03, 08 |
| **Resume card captured when Sam pauses**: the anchored node, the level, and a one-line recap. Cues saved at the moment of interruption beat reconstructed ones (Altmann & Trafton; Parnin & Rugaber) | S | 08, 14 |
| **Shame-neutral language:** "here's where you left off", never "you didn't finish". Shame after an unfinished task *increases* avoidance through rumination | M | 13 |
| **No streaks.** At most a non-resetting "engaged days" count | M/W | 08, 10 |
| **Interruption tiers map to channels.** "Worth interrupting" fires only at a natural break (crossing an L2 boundary or a settled dial) and outside focus mode. "Mention later" is a **predictable batch** (~3×/day ⚑). "Log silently" is a peripheral line that **decays**, never a growing backlog | S | 14 |
| **Focus mode** is a first-class, one-utterance control. Deferred important items go into the batch, not the silent log | M | 14 |
| **Hyperfocus:** protect it and never throttle depth; show only an unobtrusive elapsed-time indicator | M | 08 |
| Give **bounded choices at open** ("start at L0 / jump to section / let Riemann pick") rather than an open canvas. Bounded choice has ADHD-specific support; open-ended self-direction costs executive function | M | 13 |
| **Novelty plus fast feedback**: ADHD novelty-seeking comes with slower reward learning, so show the payoff of an exploratory click immediately | M | 13 |
| **Movement is fine.** Fidgeting helps ADHD performance, so never "hold still" or focus-lock the UI | M | 03 |

### 2.4 Modalities

| Principle | Grade | Source report |
|---|---|---|
| **Audio suits short levels** (L0/L1). For long L3, the modality effect *reverses* (transient speech overloads working memory), so long audio is opt-in with scrubbing | S | 04 |
| **Speed:** 1–1.5× by default, up to 2× offered. Little cost up to ~2× ⚑ | M | 04, 13 |
| **Synced text + audio** is an *open question*. The redundancy effect says it hurts; ADHD reports describe it as scaffolding. **Run it as an experiment on Sam** | contested | 04, 13 |
| **Map view of the L2 tree.** Concept maps beat text (g≈0.58), and *building* one beats studying one (0.72 vs 0.43 ⚑). The tree already *is* a map, with no risky LLM-extracted edges | S | 04, 15 |
| Treat any **LLM-inferred cross-links** as unverified: auto concept maps have poor precision, and a few correct edges beat many shaky ones | M | 16 |
| **Pick the format from the content type**: comparison → table, sequence → timeline, causal → chain, procedure → steps. This is a heuristic, not proven for each type | W/M | 04, 16 |
| **RSVP (one word at a time):** in general it's a skim tool that hurts literal comprehension. *But* one controlled study found adults with ADHD comprehended better with RSVP while controls got worse ⚑. Make it an **opt-in experiment for Sam**, not a default | W/M | 13, 15 |
| **Podcast-style two-voice audio:** no controlled evidence that it helps comprehension, and generated podcasts are measurably unfaithful. Later, and only with source grounding | W | 16 |

### 2.5 Durable learning (when purpose = study or remember)

| Principle | Grade | Source report |
|---|---|---|
| **Retrieval practice** is the best-evidenced time-efficient technique: about 61% vs 40% recall at one week at equal study time ⚑. Offer a ~5–10 s factual check after L1 | S | 05, 15 |
| **Prequestions** before expanding a section help even when wrong, mainly for factual material | M–S | 05 |
| A **delayed** self-summary or keyword step makes his sense of how well he understood more accurate (Thiede/Dunlosky) | S | 11 |
| **Spaced return** is opt-in ("remember this later"), a per-topic memory state in the spirit of FSRS, and not part of the default reading flow | S | 05, 15 |
| **Summarising and highlighting are low-utility on their own** (Dunlosky). Riemann doing the summarising *for* Sam is not the same as learning | S | 05, 11 |
| Build a gain-per-minute table **from Riemann's own logs**. The literature almost never reports it | — | 15 |

### 2.6 The spatial view (later)

| Principle | Grade | Source report |
|---|---|---|
| The brain reuses its navigation systems for abstract concept spaces (grid-like coding ⚑), which is a real justification for spatial layout | S | 06 |
| **Overview + detail** with a dismissible minimap that shows landmark tags. Zooming alone costs orientation. Overview+detail gave better synthesis but slower lookup ⚑ | S | 06, 12 |
| **2D or 2.5D, never true 3D.** 3D slows retrieval; depth must encode real structure | S | 06, 10 |
| A **local, ego-centred view of one document's tree**. Global "graphs of everything" become hairballs past a few hundred nodes | M | 06, 12 |
| **Preserve the mental map**: when content updates, keep relative positions rather than re-optimising the layout | S | 06 |
| **Node identity is independent of position** (Heptabase-style cards), which avoids "canvas rot" | M | 12 |
| **Lay out from tree structure, not embedding projections.** UMAP-style distances between clusters are meaningless | S | 06 |
| **Landmarks must be permanent, unique and identifiable at a glance.** Give L1 nodes and heavily branching L2 nodes a deterministic visual tag | M | 12 |
| Use **Lynch's checklist** for every screen: paths, edges, districts, nodes, landmarks | M | 06 |
| Build **consistent, pre-built landmarks over emergent structure**, because ADHD spatial working-memory costs grow with difficulty | M | 13 |
| The **home anchor never moves**; new features attach to the edges (habit-context binding) | S | 08 |

---

### 2.7 Borrowed from other fields (cross-domain ideas)

Fields that have to transfer understanding fast, under stress or divided attention, converged on patterns that fit Riemann. Most of these are **practitioner doctrine rather than controlled research**, so treat them as design hypotheses. The idea-generation worker stalled partway, and its partial output is in `09-lateral-grok-partial.md`. This section is curated from that output plus the orchestrator's own knowledge.

| Borrowed pattern | Source domain | Riemann feature |
|---|---|---|
| **Commander's intent**: state the purpose, not only the facts, so people can act when details are missing | Military (ADP 6-0) | L0 carries the *why* ("so that…"), not just the claim. At low capacity, intent alone is enough to act on |
| **Estimative language and key judgments**: fixed words for likelihood ("likely" ≈ 55–80%) with confidence stated separately (ICD 203) | Intelligence analysis | A fixed hedging vocabulary in generated levels. Carry the source's own uncertainty upward instead of flattening it; a hedge in L3 must survive to L1 |
| **Dark cockpit**: when everything is normal the panel is dark, and only abnormal states light up | Aviation (Airbus) | Calm-tech default: the log-silently tier is truly quiet, and only changes surface |
| **Warning / caution / advisory**: three urgency classes with distinct, never-mixed signals | Aviation alerting | The three interruption tiers, each with its own fixed channel and sound (spearcon) |
| **Sterile cockpit**: no non-essential talk during critical phases | Aviation (FAR 121.542) | Focus mode. At low capacity Riemann asks nothing unless asked |
| **SBAR / I-PASS "synthesis by receiver"**: the receiver restates the handoff in their own words | Clinical handoff | The optional one-line teach-back in study mode. It's the generative act that breaks the illusion of understanding (§2.5) |
| **"Previously on…"** recap before an episode | TV | The resume card: a 10-second recap of *this* document from where Sam left off, not a generic summary |
| **Trailer / cold open**: give the stakes before the exposition | Film | Optional "gap question" L0 style (the curiosity experiment in §4) |
| **Fog of war / minimap / quest log** | Game design | The spatial view reveals regions as they're read, and the minimap shows explored vs unexplored. A quest log lists open loops *without* failure framing |
| **Teach by doing, no text tutorials**: the first level teaches the controls | Game onboarding | The dial explains itself on first use: turn it and see. No onboarding screens |
| **Map generalisation**: substitute symbols by scale; never just shrink | Cartography | Levels *substitute* content (already in the design). Landmark labels appear and disappear in fixed zoom bands (Google Maps) |
| **Line diagram / subway map**: topology over geography | Transit maps | An optional "route" view of a long argument: stations are claims, lines are reasoning threads |
| **Headnotes**: an editor's numbered holdings ahead of a legal opinion | Law | L2 section gists numbered and linked into L3, like headnote → paragraph |
| **Graphical abstract**: one image for the whole paper | Science publishing | Later: a single diagram at L0/L1 for causal or process content, only when the source-span check passes |
| **Chunking in chess**: experts see patterns, not pieces | Expertise research (S) | Explains *why* expertise reversal happens. Feeds the knowledge ladder: once a topic is "proficient", group its content into bigger chunks |
| **Speedrun routing**: know which sections can be skipped for your goal | Games | Purpose-conditioned "skip map": for this purpose, sections 3–5 can be skipped, and Riemann says why |
| **Wayfinding "you are here"** with the map oriented to the direction you face | Museums, wayfinding | The breadcrumb and minimap always oriented from the current node outward |
| **Short-form video hooks** (and their harms) | Social media | Borrow the fast payoff (instant L0). Refuse infinite feed, autoplay and variable-reward loops, which exploit ADHD reward-learning differences (13) |

---

## 3. What this changes in the approved v1 plan

These additions fit v1 without widening its scope. Everything else is deferred.

1. **`build.py`:**
   - Ground L1 and L0 against the leaf source spans.
   - Make the L0 prompt claim-first.
   - Add a length-band check with one targeted retry, and a two-pass density step.
   - Keep procedures and code verbatim.
   - Keep causal connectives.
2. **`model.py`:** add `faithfulness: float | None`, `leaves_out: str | None` and `kind` (prose / procedure / comparison / timeline) to `Node`.
3. **`chunk.py`:** mark procedural, code and equation blocks as atomic.
4. **Frontend:**
   - Labelled detents with read times.
   - A persistent L0 header, a breadcrumb (≤3) and a home control.
   - FLIP headings, crossfaded body text and reduced motion.
   - The ARIA slider and live region.
   - A 60–75-character column, spacing controls and paged levels.
   - Source-span hover showing real sentences.
   - A collapsed "leaves out" line.
   - No progress bar.
5. **Instrumentation from day one:** a local JSONL event log of dial moves, per-node dwell, re-visits, idle gaps and "not helpful" taps. This has to be reliable before any adaptivity is built on it (Li et al.'s stage model: when collection fails, everything downstream fails).
6. **Resume card:** on pause, blur or close, save the anchored node, the level and a one-line recap; show it on reopen.
7. **Evaluation harness:**
   - 3–5 checkable questions per test document.
   - Record which level answers each one, and the time taken.
   - No existing study measures "does this level deliver this understanding in this time". Riemann can.

**v1.x** (next): the map view of the L2 tree, the purpose chip, the one-tap capacity/affect check-in, the retrieval check in study mode, predict-before-reveal (occasional and skippable), TTS on L0/L1 with speed control, and the prior-knowledge rapid check.

**v2:** the contextual-bandit defaults with the open learner model, interruption tiers and batching, synced audio and RSVP as n-of-1 experiments, and spaced return.

**v3:** the spatial view (§2.6).

## 4. Experiments to run on Sam (n-of-1)

The literature can't settle these for one person, but Riemann can, by randomising the default between sessions and logging the outcome:

1. **Synced text+audio vs text alone** (the redundancy vs scaffold question).
2. **RSVP vs normal reading at L2/L3** (the ADHD crossover finding).
3. **L0 as a claim vs L0 as a curiosity-gap question.**
4. **Default level: L0 vs L1** across capacity states.
5. **Predict-before-reveal:** on vs off, measuring retrieval-check accuracy.
6. **Idle-threshold calibration.** No validated ADHD number exists; start generous.

## 5. Tensions only Sam can decide

- **Reference tool or learning tool?** The research is clear that frictionless reading is right for *finding and deciding* and wrong for *learning*. The proposal is a purpose-driven mode rather than one global answer. How much friction will study mode be allowed?
- **How much control?** The literature says system defaults with easy override. ADHD evidence favours bounded choices. Is "Riemann opens where it thinks best" acceptable, or should it always open at the last level?
- **Four levels vs "more than two levels confuses people".** The mitigation is labelled detents and a capped breadcrumb. If the levels still feel like a maze, a three-level variant (gist / sections / source) is the fallback.
- **Stability vs novelty.** A fixed home and layout build habit, but an ADHD brain wants novelty. The proposal is a stable core with novelty at the edges.

## 6. Myths to avoid building

- Learning-styles matching ✗
- Bionic reading ✗ ⚑
- Dyslexia fonts ✗ ⚑
- "Speed reading" at 2–3× with equal comprehension ✗
- The 8-second goldfish attention span ✗
- Uniform background white noise: it helps some ADHD profiles and hurts others ⚑; opt-in only
- Streaks and gamified guilt: evidence is weak but the direction is consistently harmful
- A static "AI may make mistakes" disclaimer: automation bias isn't fixed by warnings, only by making verification cheap
- Body doubling as a proven technique: it's popular but has almost no controlled evidence (fine as an optional feature)
- Claims that NotebookLM-style podcasts help learning: marketing, not evidence

## 7. Where research runs out (Riemann's opportunities)

Nobody has published:
- a zoom or abstraction dial tested with ADHD readers
- a comparison of reading an AI summary vs the original for later comprehension
- object-constancy transitions for *text* changing its level of detail
- ADHD-calibrated idle and dwell thresholds
- a medication-aware interface
- landmark selection for abstraction trees
- two-voice vs monologue vs text comprehension

Riemann's event log plus the evaluation harness can produce this evidence, first for Sam and later for other users.

## 8. Report index

| # | Report | Worker |
|---|---|---|
| 01 | Multi-level abstraction and faithfulness | Sonnet 5 |
| 02 | Graphic and information design for cognitive load | Sonnet 5 |
| 03 | ADHD information absorption | Sonnet 5 |
| 04 | Presentation modalities | Sonnet 5 |
| 05 | Fastest path to a chosen depth of understanding | Sonnet 5 |
| 06 | Spatial representation, zoomable interfaces, maps and networks | Sonnet 5 |
| 07 | Adaptive teaching signals and tutoring systems | Sonnet 5 |
| 08 | Fluctuating attention, motivation and energy; state model | Sonnet 5 |
| 09 | Cross-domain lateral ideas (no web access; **partial**: the GPT run hit its quota and the Grok run stalled; curated into §2.7) | Grok 4.7 |
| 10 | Skeptic's view: failure modes and myths (no web access) | Gemini 3.1 Pro |
| 11 | Illusion of understanding and AI trust calibration | Sonnet 5 |
| 12 | Text zoom transitions, spatial hypertext, canvases, landmarks | Sonnet 5 |
| 13 | ADHD deep dive (reading, audio, autonomy, shame, spatial, strengths) | Sonnet 5 |
| 14 | Interruption, resumption, calm tech, proactive assistants | Sonnet 5 |
| 15 | Learning efficiency, RSVP, open learner models, long-horizon modelling | Sonnet 5 |
| 16 | Generation recipes per format | Sonnet 5 |
| 17 | Beyond ADHD: inclusion and zoom-dial accessibility | Sonnet 5 |
| 18 | Reading purpose, personal relevance, screen vs paper | Sonnet 5 |
| 19 | Fact-check of load-bearing claims | Sonnet 5 |
