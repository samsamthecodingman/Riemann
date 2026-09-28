# The Riemann Model: objective-driven information absorption

*Version 2, 2026-09-28. This version adds the **objective** dimension, a research base where every finding records its assumptions, the 15 fixes from the Opus review (`reports/20-expert-review.md`), and targeted research on life-admin objectives (reports 21–23).*

*Sources:*
- 16 web-research reports (01–08, 11–18) and 3 targeted reports (21–23), all by Sonnet 5.
- A skeptic report (10, Gemini, no web access).
- A fact-check (19) and an expert review (20).
- The ledger in `ledger/`, which is the source of truth for individual findings. `python3 ledger/ledger.py` queries it.

*Evidence grades:* **S** strong, **M** moderate, **W** weak or preliminary, **✗** myth. **✓fc** means the fact-check confirmed the claim; **~fc** means it corrected or couldn't fully verify it. Rows marked **hyp.** are the orchestrator's design hypotheses, not research findings.

---

## L0

**Riemann first works out what Sam is trying to *do* with a piece of information: learn it, decide, plan, act, keep watch, look something up, or reply. That decides which thinking Sam should do and which Riemann should take off his hands. Only then does it pick how deep to go, how active the reading is, and in what format. Four guarantees hold everywhere: every claim links to its source, Sam never loses his place, nothing shames him, and nothing claims he understands more than he does.**

## L1: the two-minute version

1. **There's no universal right way to present information; it depends on the objective.** An assignment brief needs its reasoning explained if Sam is learning from it, needs to become steps if he's planning, needs to show only the next action if he's executing, and needs only the deadline and requirements if he's looking something up. Riemann doesn't make a user think harder or make things easier as a blanket philosophy. **It allocates cognitive work to suit the objective.** (Framing from Sam's ChatGPT brief, now backed by reports 21–23.)
2. **Learning keeps the effort, and life-admin offloads it.** Retrieval, prediction and self-explanation are among the best-evidenced learning techniques (S). But once Sam commits to a *specific* plan (how, when, where), the intrusive "don't forget" thoughts stop even though the goal isn't finished yet (Masicampo & Baumeister, S), so plans should live in Riemann, not in his head. Adults with ADHD have a particular weakness in remembering to do things at a *time* rather than on a *cue* (M), so reminders should hang off events ("when you open your laptop"), not clock times.
3. **The zoom dial works for every objective, and L0 changes meaning with the objective.** The dial is a good idea with a long history: Ted Nelson proposed "stretchtext" in 1970, and it failed then only because every level had to be written by hand. **L0 is always "the one thing that matters for this objective":**
   - learn: the core claim
   - execute: the next action
   - decide: the choice and when it's due
   - monitor: what changed
   - communicate: what's being asked, and by when

   **Reference is the exception.** Search plus a highlighted source beats any summary (M), so reference skips the tree.
4. **The main risk with summaries is false confidence, not boredom.** Easy summaries can create an illusion of understanding (M for summaries specifically). LLM summaries also contain errors; one benchmark found 20–45% of multi-document summaries contained hallucinated content (M). Three cheap defences:
   - link every claim to its source
   - add a one-line "what this leaves out"
   - in learn mode, occasionally ask Sam to predict before the answer is revealed

   Riemann says "you have the gist", never "you understand".
5. **Sam's capacity and motivation move around, so defaults flex and Sam can always steer.** Variability within the same person is the core ADHD marker (S). Capacity, emotional state and motivation are separate signals. For example, a flagging mood is helped by a curiosity hook, not by less content. Riemann:
   - opens where it makes sense and never blocks
   - lets Sam re-enter at any level
   - asks for one-tap input rather than guessing
   - learns slowly from behaviour
6. **Starting is the hardest part, and shame makes it worse.** L0 must appear *first and fast*: in ADHD, waiting is itself aversive, and delay aversion is one of the best-evidenced findings. Riemann never shows streaks, "14 unfinished" badges or progress bars at the top. Shame after an unfinished task increases avoidance (M).
7. **Riemann presents; Sam acts.** Riemann can turn information → intention → a *proposed* commitment → the next action, and later notice the outcome. It never sends, submits, books or buys anything. That limit also builds trust (M): people trust supportive AI more than AI that acts on its own.
8. **The research base keeps track of its assumptions.** Each finding records the assumptions it depends on. Each assumption records which objectives it holds for. Adding a new objective or user group means filling in one column; the ledger then lists exactly which findings and features break, and only those get re-researched.

---

## 1. The model

```
 INFORMATION ──▶ ① OBJECTIVE ──▶ ② WORK SPLIT ──▶ ③ REPRESENTATION ──▶ ④ SUCCESS SIGNAL
 (email, doc,     what is Sam      what Sam does     depth · activity ·    per-objective
  calendar,       trying to do?    vs Riemann does   modality · transform  metric
  notes, URL)          ▲                  ▲                  ▲
                       └──── STATE: capacity · affect · motivation (fast + slow timescales)
                       └──── KNOWLEDGE: topic familiarity (ordinal ladder)
 INVARIANTS (every objective, every state): grounded · oriented · forgiving · honest · accessible · presents-only
```

### 1.1 Objectives (internal vocabulary; Sam sees a one-tap chip, never a taxonomy)

| Objective | Optimises | Sam's cognitive work | Riemann's cognitive work | Transform | L0 is… | Success signal |
|---|---|---|---|---|---|---|
| **Understand** | a mental model now | read, question | compress, structure, ground | abstraction tree | the core claim | can explain it now (self-check) |
| **Learn** | retention and transfer | retrieve, predict, explain, connect | scaffold, then fade; schedule returns | tree + generative touches | the core claim | recall a week later |
| **Remember (internal)** | recall without aids | retrieval practice | spacing, prompts | cards from the tree | — | recall on schedule |
| **Remember (offloaded)** | available when needed | nothing (trust the store) | store, surface on cue | offload store + event cues | the cue | surfaced at the right moment |
| **Decide** | a decision he endorses, on time | weigh against his own values | line up options side by side, show only differing attributes, no framing bias | decision table | the choice and when it's due | decided by the deadline; he stands by it later |
| **Plan** | a realistic committed plan | choose, commit, own the plan | draft steps, estimate time from his past tasks, spot dependencies | plan breakdown (how, when, where) | the goal and first step | he commits to it; the plan survives |
| **Execute** | the action done (by Sam) | do it | surface the next action, remove friction | next-action card | the next action | done |
| **Monitor** | nothing missed, little attention spent | glance at exceptions | detect changes and exceptions, not summaries | exception digest | what changed | nothing missed; attention spent |
| **Reference** | exact fact, fast | recognise the answer | index and search | search + jump to the highlighted source | the fact | time to the fact |
| **Communicate** | the recipient gets it right | decide, write, send | work out what kind of message it is; pull out the ask, deadline and context, plus what the recipient already knows | reply brief | the ask and when it's due | a correct, on-time reply |

- **Items often serve several objectives.** An assignment brief is *learn* for the content and *plan* for the logistics. Riemann picks a primary objective, keeps secondary ones, and the chip shows the primary.
- **Inference:**
  - The objective is inferred from context: the source (email vs PDF vs lecture), the calendar (an exam in 5 days means *learn*), and the task list.
  - The chip corrects it in one tap, which is the only friction.
  - Report 23 notes that personalisation from a model's guess is often only superficial, so the correction path matters.

### 1.2 Cognitive work allocation: when to enhance and when to offload

The ledger's assumption table records, for each objective, whether each assumption holds (**Y**), holds conditionally (**C**) or fails (**N**). No cells are still marked unknown after reports 21–23. The rows that decide the work split:

| Assumption | Und. | Learn | Rem. | Decide | Plan | Exec | Monitor | Ref | Comm |
|---|---|---|---|---|---|---|---|---|---|
| A01 Durable internal learning is the goal | C | Y | Y | N | N | N | N | N | N |
| A03 Holding it in Sam's own memory beats external storage | C | Y | Y | N | **N**¹ | N | N | N | N |
| A04 Effortful processing by Sam improves the outcome | C | Y | Y | C | **C**² | N | N | N | C |
| A18 Sam wants to steer, not be directed | Y | C | C | Y | Y | **C**³ | N | Y | Y |
| A20 Riemann speaking up proactively is wanted | N | C | Y | **C**⁴ | C | Y | Y | N | C |
| A29 Detail from the original matters in itself | C | Y | C | **N**⁵ | C | N | N | C | C |
| A30 Compression is the right transform | Y | Y | C | C | N | N | **N**⁶ | N | C |
| A32 Sam generating it himself beats being given it | C | Y | Y | C | **C**⁷ | N | N | N | C |

Resolved by the targeted research:

1. **A03×plan = N.** A specific plan relieves the need to hold the goal in mind (Masicampo & Baumeister 2011, 6 studies, S). Report 22 argued for C, because no study compares keeping a plan in memory with storing it externally. The orchestrator kept N because the relief effect is direct evidence.
2. **A04×plan = C.** Effort *when the plan is formed* matters; keeping it in mind afterwards doesn't (21, 22).
3. **A18×execute = C.** Being told the next action can help ADHD initiation but can undermine autonomy. Resolved by process rather than evidence: suggestions are always declinable and editable (22, W–M).
4. **A20×decide = C.** Surface a due decision only with good timing and user control, using the same gating as monitor alerts (23).
5. **A29×decide = N.** Extra facts beyond what differs between the options *hurt* decisions. Decision aids work by linking comparable information to the person's own values (Cochrane decision-aid review, S; fact-box RCT) (23).
6. **A30×monitor = N.** Exception-based design beats compression: compression makes each item cheaper to review but doesn't reduce how many items there are (22).
7. **A32×plan = C.** No study compares a self-made plan with a given one. Adjacent evidence (IKEA effect, co-planning, self-determination theory) favours *co-generated* plans, and an abandoned co-planning session may be worse than either. **Riemann drafts; Sam edits and commits** (22).

**The rule this gives:** Riemann does the work of remembering, tracking, rebuilding context and re-deciding "what next" (plan, execute, monitor, offloaded remember). It keeps Sam's effort where the effort *is* the product: understanding, learning, making choices, and owning the commitment. Offloading has two costs, handled separately:
- **Silent corruption or unavailability of the store.** This leaves him worse off than never offloading (21, M). Remedies: visible sync status, no silent edits, and the source always one tap away.
- **Offloading trivia.** People offload more than is optimal (21, M). An occasional "you don't need to save this one" is fine; adding friction is not.

### 1.3 State sets the defaults, not the ceiling

Three separate signals:
- **Capacity** (energy and attention). Fatigue affects attention broadly.
- **Affect.** Anxiety specifically affects inhibition and task-switching.
- **Motivation** (interest). Motivation can be moved independently of energy (08).

The signals also run on two timescales: this session (fast) and this week (slow). Defaults by state:

| State | Default depth | Density and chrome | Motivation levers | Tone |
|---|---|---|---|---|
| Low capacity | L0; L1 one tap away | minimal chrome, one thing on screen | — | "here's the short version" |
| Medium, calm, motivated | L1, dial fully live | normal | — | occasional skippable offers |
| **Capacity fine, motivation low** | L1 | normal | curiosity-gap L0 variant, bounded choice, immediate visible payoff, optional "why does this matter to you?" | no pressure |
| Anxious (any capacity) | L1 | **fewer choices and tabs**; no side-by-side comparisons | — | optional grounding line (not evidence-backed; UI copy only) |
| High, absorbed (hyperfocus) | last used, or L3 | full | — | silent; subtle elapsed-time indicator |

**Inputs, best first:**
1. An optional one-tap check-in, with capacity, affect and motivation as separate taps.
2. Rules Sam sets once for himself. Implementation intentions have strong evidence (d≈0.65, S ✓fc). Example: "after 9pm, open at L1".
3. Implicit signals, learned slowly.

**What stays manual:**
- **Settings whose effect flips from person to person are explicit settings, never inferred:** background noise, motion, spacing, audio pairing, literal vs figurative language.
- **The bandit learns only the default depth.**
- **Medication timing is never inferred silently.** Doing so is ethically fraught, and no product has shown it works.

For other people later: some conditions need a *multi-day* energy budget (ME/CFS, long COVID). And for autistic users (monotropism), an **unexpected interruption is a harder constraint than for ADHD**, so interrupt defaults must be conservative (17).

### 1.4 Prior knowledge sets how much scaffolding to show

- **Expertise reversal (S):** structure that helps novices slows experts down. If Sam knows the topic, land at L2 or L3.
- **Detecting what he knows:**
  - Default: has he read this topic before, at what level, how recently.
  - When unsure: a rapid true/false check with 2–3 claims. This is Kalyuga's rapid-verification method, validated only on STEM and procedural material (~fc), so it's untested for reading.
- **Showing what he knows:** an ordinal ladder (not started / familiar / proficient), not a graph. Khan Academy retired its graph-shaped knowledge map (✓fc for the retirement; the reason is secondhand).

### 1.5 Depth of text ≠ depth of understanding

Report 05 is explicit that understanding is "not one dial". The dial sets *text* depth. The objective and the activity dial together set the *understanding* target, using Kintsch's levels:
- **Surface:** the exact wording.
- **Textbase:** the propositions the text states.
- **Situation model:** the integrated understanding Sam can reason with.

| Target | Kintsch level | Cheapest path |
|---|---|---|
| Gist ("what's this about, does it matter?") | situation, coarse | L0 (+ L1 if it matters) |
| Working understanding (can act on or discuss it) | situation | L1 → L2 on the sections he needs; a source hover on doubtful claims |
| Can explain or teach it | situation + textbase | L2 → L3 on core sections + a one-line explain-back + one retrieval check |
| Remember for the exam | durable | the above + spaced return (opt-in) |
| Exact detail | surface | search → L3 (reference path) |

Every question in the evaluation harness is tagged with its Kintsch level, so Riemann can measure whether a level delivers its promised understanding in its promised time. **No published study has measured this. Riemann can.**

### 1.6 The loop

- **Signals**, ranked by cost and privacy:
  1. Interaction logs: dwell time per node, dial moves, re-visits, idle gaps, scroll-backs.
  2. One-tap micro-probes at natural breaks.
  3. Explicit "not helpful".
  4. Never webcam or eye-tracking.
- **Reading the signals:**
  - **Confusion** (dwell or re-read spikes on one passage) → *give more*: expand, clarify, show the source. Confusion is productive (D'Mello & Graesser).
  - **Boredom or frustration** (flicking, bailing out) → *back off*: offer L0, or suggest stopping.
- **Learning:** a contextual bandit on default depth only, with rule-based priors and decayed rewards.
- **Show the reasoning:** "Opened at L1: it's late and this is new to you", with a one-tap "wrong".
- **Success per objective (§1.1)**, not one "engagement" metric.

---

## 2. Principles with evidence

The ledger holds the full per-finding detail, with assumptions attached. These are the load-bearing ones.

### 2.1 Building the tree

| Principle | Grade | Report |
|---|---|---|
| **L0 first:** a fast provisional L0 call before the full build. In the single-call path, stream L0 first in the JSON. When the default is L0, show a "gist coming" placeholder, not the full source | S (delay aversion) | 03, 20 |
| **L0 as a claim** (≤25 words), objective-relative (§1.1). The *why* (commander's intent) goes in the first sentence of L1, not L0 | M | 01 |
| **Cite leaves:** every L1/L2 sentence carries the leaf ids it came from. In the map-reduce path, the reduce step receives the cited leaf spans, not just the child summaries (errors compound in recursive summaries) | M | 01 |
| Validate **length** and retry once. LLMs often miss length targets; the "about half the time" figure couldn't be traced (~fc) | M | 16 |
| Keep **worked examples, procedures, code and equations** verbatim at L2 | S | 04 |
| Keep **causal connectives** ("because", "so"), since stories are recalled better than lists, *but* never add causation the source lacks | S / M | 04 |
| **Carry uncertainty up the tree:** a hedge in L3 must survive to L1. Use one fixed hedging vocabulary (**hyp.**, borrowed from intelligence analysis's standard likelihood words) | hyp. | 01 |
| **Plain language** (ISO 24495-1 pillars); audit L0 for idioms, since autistic readers take them literally | M | 16, 17 |
| Time estimates start at **238 wpm** (✓fc) and are **recalibrated to Sam's measured rate**; ADHD readers are slower on dense text | S / M | 05, 13 |
| Simpler isn't automatically easier: AI-simplified text was no easier once familiarity was controlled (✓fc). **Measure it** | M | 17 |

### 2.2 The dial

| Principle | Grade | Report |
|---|---|---|
| **Open at L1** with the L0 line as a persistent header; **reopen at the last level and position** | design rule | 20 |
| **Label each detent** with name, description and a small read time ("L1 · summary · ~2 min"). Progressive disclosure beyond 2 levels tends to confuse people (✓fc); labelling every level is our mitigation (**hyp.**). Keep read times small and never a countdown, because time pressure *worsens* on-screen comprehension | M | 12, 18 |
| **Breadcrumb at L2/L3 only**, showing the L1 section title (L0 is already the header), plus a **home** control | M | 06, 12 |
| **Anchoring:** hold the source span fixed and scroll to its ancestor or descendant | M | 06 |
| **Transitions:** FLIP-animate headings and crossfade body text over 150–250 ms; jumps of more than one level use a crossfade cut; `prefers-reduced-motion` → instant | M (text-specific: untested) | 02, 12 |
| **Layer-cake L2:** headings plus 40–80-word bodies, claim first. L2 acts as a *graphic* advance organiser | M | 02, 05 |
| A **60–75-character column**; no "dyslexia fonts" (✗ ✓fc) | S | 02 |
| **Source hover** shows 1–2 real sentences. Links only calibrate trust if checking them is cheap, or they become a badge nobody reads (Vasconcelos) | S (mechanism) | 11 |
| A collapsed **"leaves out"** line on L1/L2 | W (single 2026 preprint) | 11 |
| **Minimal-chrome mode** for low capacity: content plus dial only; everything else behind one "more" | design rule | 20 |
| **Open straight to content.** The "start at L0 / jump to a section / let Riemann pick" choices are a *non-blocking* row underneath | M | 13, 20 |
| **Accessibility:** `role="slider"` with `aria-valuetext`; Arrow/Home/End/PageUp keys; a persistent polite live region; each level a heading-navigable region | S | 17 |
| **No top progress bar** or "% read" | M | 13 |
| **Scroll within a level** in v1. Paging beats scrolling for comprehension (M, within one text); paginated L3 is an experiment, not a default | M | 18 |

### 2.3 Attention, re-entry and interruption

| Principle | Grade | Report |
|---|---|---|
| **Re-enter at any level, any time** | S | 03, 08 |
| **Resume card captured at pause:** the anchored node, the level, and a one-line recap. Cues saved when interrupted beat reconstructed ones | S | 08, 14 |
| **Shame-neutral:** "here's where you left off", never "you didn't finish" | M | 13 |
| **No streaks** | M/W | 08 |
| **Interruption tiers map to channels:** "worth interrupting" only at a natural break and outside focus mode; "mention later" as a **predictable batch** (~3×/day ✓fc); "log silently" is peripheral and **decays** | M (our mapping of S findings) | 14 |
| **Batching needs a brief per item**, or it only moves the triage cost to later | M | 23 |
| **Event cues beat time cues** for ADHD reminders; 2–3 varied touches before a deadline | M / W | 21 |
| **Focus mode** is one tap or one utterance; deferred important items go into the batch, not the silent log | M | 14 |
| **Hyperfocus:** protect it; an unobtrusive elapsed-time indicator only. ADHD time-blindness is a deficit in reproducing time, not estimating it, so a *live visible timer* during execution beats up-front estimates | M | 08, 22 |
| **Novelty plus fast feedback** (ADHD reward learning is slower) | M | 13 |

### 2.4 Modalities

| Principle | Grade | Report |
|---|---|---|
| **Audio for short levels.** For long L3 the modality effect reverses; long audio is opt-in, with scrubbing | S | 04 |
| **Speed** 1–1.5× by default, up to 2× offered (✓fc) | M | 04 |
| **Synced text+audio is contested:** the redundancy effect says it hurts; ADHD reports call it scaffolding. **n-of-1 experiment** | contested | 04, 13 |
| **Map view of the L2 tree:** concept maps g≈0.58; building one beats studying one (0.72 vs 0.43 ✓fc) | S | 04, 15 |
| **LLM-inferred cross-links are unverified.** A few correct edges beat many | M | 16 |
| **RSVP (one word at a time):** adults with ADHD comprehended *better* under it while controls got worse (n=76, ✓fc), but it generally hurts literal comprehension. Reports disagree on where it belongs (13: at L3; 15: L0 only). **n-of-1 experiment** | M | 13, 15 |
| **Two-voice podcast audio:** no controlled evidence it helps; generated podcasts are measurably unfaithful (✓fc) | W | 16 |
| **Match the format to the content, never to "learning styles"** (✗ ✓fc) | S | 04 |

### 2.5 Learn and remember (effort is the product)

| Principle | Grade | Report |
|---|---|---|
| **Retrieval check** (~5–10 s, factual) after L1 in learn mode; about 61% vs 40% recall at one week at equal study time (✓fc). This is formative feedback on Sam's own recall; effect sizes are contested (0.2–0.7) | S | 05, 15 |
| **Prequestions** before expanding a section help even when wrong, mainly for facts | M–S | 05 |
| A **delayed explain-back** in his own words makes his sense of how well he understands more accurate (Thiede/Dunlosky) | S | 11 |
| **AI help without guardrails harms unaided performance.** In learn mode Riemann gives hints, not answers (Bastani et al., PNAS; a correction was published; ✓fc on direction) | S | 11 |
| **Spaced return** is opt-in, per topic | S | 05, 15 |
| **Generative touches only in learn mode.** Forcing functions lower satisfaction (✓fc), so they must pay for themselves | S | 11 |

### 2.6 Life-admin objectives (effort is waste)

| Principle | Grade | Report |
|---|---|---|
| **Plan = the how/when/where triad plus a distinct "I'm doing this" commit.** A vague goal gets no relief; a specific committed plan does | S | 21 |
| **Riemann drafts, Sam edits and commits.** Co-generated plans are favoured; an abandoned co-planning session may be worse than no plan | C (adjacent evidence) | 22 |
| **Adjustable step size.** No validated "right" chunk size exists; proximal subgoals beat distal goals (S, children); specific goals beat "do your best" (S) | S / M | 22 |
| **Time estimates from Sam's own history (outside view).** The planning fallacy is robust; thinking harder doesn't fix it | S | 22 |
| **Self-imposed deadlines: not evidence-backed.** The canonical Ariely & Wertenbroch 2002 study was **retracted on 2 Sep 2026** for data tampering (verified by the orchestrator via Retraction Watch), and the 2026 replication failed. Interim dates are a cheap structuring aid, not a proven booster | ✗ | 22 |
| **Checklists** are strong evidence, but only for routine, error-prone procedures (WHO surgical checklist). Don't claim they motivate starting | S (narrow) | 22 |
| **Next action is concrete and bounded.** To-do lists fail through vagueness and unbounded length, not format (Bellotti, CHI 2004). Suggestions are always declinable | M | 22 |
| **Monitor = change and exception detection, not summaries.** Gist errors are tolerable only for items correctly marked "no change" | M | 22 |
| **Decide = a table of options that differs only where they differ**, with neutral attribute wording, linked to Sam's stated priorities, delayed benefits made concrete (ADHD discounts delayed rewards steeply). Don't hide options by default (choice-overload meta-analyses conflict) | S / M | 23 |
| **Decision fatigue / ego depletion: myth.** It failed a 23-lab replication (d≈0.04). No "decision budget" model | ✗ | 23 |
| **Reference = full-text search + jump to highlighted source.** Not the tree | M (inferred) | 23 |
| **Communicate = a reply brief:** classify the message (needs action, FYI or archive) → pull out the ask, deadline, context and roles (generic summaries fail at "who asked whom") → note what the recipient already knows. **Sam writes and sends**; Riemann never drafts in Sam's voice | M | 23 |
| **The offload store must be trustworthy:** visible sync, no silent edits, source one tap away | M | 21 |

### 2.7 The spatial view (later)

| Principle | Grade | Report |
|---|---|---|
| The brain reuses its navigation systems for abstract concept spaces (✓fc) | S | 06 |
| **Overview + detail**, with a dismissible minimap showing landmark tags. It gave better synthesis but slower lookup (Hornbæk & Frøkjær; "~20% slower" unverified, ~fc) | S | 06, 12 |
| **2D or 2.5D**, never true 3D | S | 06 |
| **Local, per-document view**; no global "graph of everything" | M | 06, 12 |
| **Preserve the mental map** (stable relative positions); node identity independent of position | S / M | 06, 12 |
| **Lay out from tree structure**, not embeddings | S | 06 |
| **Landmarks** must be permanent, unique and identifiable at a glance: deterministic tags on L1 and heavily branching L2 nodes | M | 12 |
| A **consistent pre-built structure** beats emergent structure (ADHD spatial working-memory costs grow with difficulty) | M | 13 |
| The **home anchor never moves** (**hyp.**, extending habit-context research to UI layout) | M | 08 |

### 2.8 Borrowed from other fields (**hyp.**: design hypotheses, not findings)

The idea-generation workers failed (GPT hit its quota; Grok stalled; see `reports/09-lateral-NOTE.md`). These come from the orchestrator's knowledge of practitioner doctrine. Rows that contradicted the model's own rules were cut.

| Pattern (domain) | Riemann use |
|---|---|
| Commander's intent (military) | The *why* opens L1; at low capacity it's enough to act on |
| Estimative language (intelligence, ICD 203) | A fixed hedging vocabulary carried up the tree |
| Dark cockpit (aviation) | Monitor shows only exceptions; normal = quiet |
| Warning / caution / advisory (aviation) | The three interruption tiers, each with its own fixed channel |
| Sterile cockpit (aviation) | Focus mode; at low capacity Riemann asks nothing unprompted |
| SBAR/I-PASS "synthesis by receiver" (medicine) | The optional explain-back in learn mode; the reply brief's structure |
| "Previously on…" (TV) | The resume card |
| Cold open (film) | The curiosity-gap L0 variant (experiment) |
| Game onboarding without tutorials | The dial explains itself on first use |
| Map generalisation and zoom-banded labels (cartography) | Levels substitute content; landmark labels appear and disappear in fixed zoom bands |
| Transit line diagrams | Optional "route" view of a long argument |
| Legal headnotes | Numbered L2 gists linked into L3 |
| Speedrun routing | Objective-conditioned "you can skip §3–5 for this purpose, because…" |
| Short-form video hooks | Borrow the instant payoff; refuse infinite feed, autoplay and variable-reward loops |

---

## 3. What this changes in the v1 build

### 3a. Fits the approved plan as written
1. **`build.py`:**
   - A fast provisional L0 first; in the single-call path, stream L0 first in the JSON.
   - A claim-first L0 prompt.
   - Leaf-id citations on every L1/L2 sentence, with the reduce step getting the cited leaf spans.
   - A length check with one targeted retry.
   - Procedures and code kept verbatim.
   - Causal connectives kept.
2. **`chunk.py`:** mark procedure, code and equation blocks as atomic.
3. **`model.py`:** add `cites: list[leaf_id]` to `Node`.
4. **Frontend:**
   - Open at L1 with the L0 header.
   - Labelled detents with small read times.
   - A breadcrumb at L2/L3 plus a home control.
   - FLIP headings, crossfaded body text, and reduced motion respected.
   - The ARIA slider and live region.
   - A 60–75-character column.
   - Source hover showing real sentences.
   - Minimal-chrome mode.
   - The non-blocking start-choices row.
   - No progress bar.
   - The "gist coming" placeholder.
5. **Resume card and last level/position**, kept in **browser `localStorage`**, which doesn't break the plan's "no persistence beyond the tree cache" rule.
6. **Evaluation harness** (tests): 3–5 questions per test document, each tagged with its Kintsch level and the level expected to answer it.

### 3b. Plan changes that need Sam's OK
- **A local event log** (JSONL of dial moves, dwell per node, re-visits and idle gaps). It breaks the persistence rule, but it's the foundation for all adaptivity. If collection is unreliable, everything built on it fails (Li et al. personal-informatics stage model).
- **Objective chip**, with v1 limited to understand, learn and reference (reference = search plus a highlighted source).
- **A collapsed "leaves out" line.** It costs an extra generation pass per level.
- **Spacing controls.**

### 3c. Deferred to v1.x and later
- **v1.x:**
  - A faithfulness score, using a named method: an LLM check of whether each sampled claim is supported by its cited leaves, calibrated against the ~0.63 human agreement seen in report 16. Until then the field stays null, and v1 relies on citations plus hover.
  - `kind` routing: table, timeline or steps.
  - A density pass.
  - Map view.
  - The capacity/affect/motivation check-in.
  - Retrieval check and predict-before-reveal in learn mode.
  - TTS on L0/L1.
  - The rapid prior-knowledge check.
- **v2:**
  - The life-admin objectives:
    - plan breakdown and commit
    - next-action card
    - exception digest
    - decision table
    - reply brief
    - offload store with event cues
  - The contextual bandit with an open learner model.
  - Interruption tiers and batching.
  - Synced audio and RSVP experiments.
  - Spaced return.
- **v3:** the spatial view.

## 4. Experiments to run on Sam (n-of-1)

The literature can't settle these for one person, but Riemann can: randomise between sessions and measure the objective's own success signal.

1. Synced text+audio vs text alone.
2. RSVP vs normal reading, at L0 *and* at L3.
3. L0 as a claim vs L0 as a curiosity-gap question.
4. Default L0 vs L1, by capacity state.
5. Predict-before-reveal on vs off (learn mode).
6. Idle-threshold calibration; start generous.
7. **Riemann-drafted vs Sam-drafted vs co-drafted plans**, measured by follow-through. No study has compared these.
8. Event-cued vs time-cued reminders.
9. Paginated L3 vs scrolling.

## 5. Decisions only Sam can make

- **Scope of "execute."** Riemann surfaces the next action and removes friction, but never acts in the world. ChatGPT's brief imagines an "executive assistant" that does things on your behalf. That would be a change to Riemann's founding scope, not a feature.
- **Learning-mode friction:** how much effort study mode may ask for. The evidence says some; satisfaction says little.
- **Defaults vs control:** is "open at L1, reopen where I left off" right, or should it always reopen where you left off?
- **Four levels:** four labelled detents, with a three-level fallback (gist / sections / source) if they feel like a maze.
- **Stability vs novelty:** a fixed core, with novelty at the edges.
- **The event log** (§3b).

## 6. Myths to avoid building
- **Learning-styles matching** ✗ ✓fc
- **Bionic reading** ✗ ✓fc
- **Dyslexia fonts** ✗ ✓fc
- **Speed reading** at 2–3× with equal comprehension ✗
- **The 8-second goldfish attention span** ✗
- **Decision fatigue / ego depletion** ✗ (23)
- **Self-imposed deadlines as proven** ✗: retracted in 2026 (22)
- **The "Google effect"** as settled ✗: it failed a pre-registered replication (21)
- **Uniform white noise:** it helps some ADHD profiles and hurts others (✓fc), so opt-in only
- **Streaks and guilt mechanics**
- **Static "AI may be wrong" disclaimers:** only cheap verification works against automation bias
- **Body doubling as proven**
- **NotebookLM-style podcasts help learning:** marketing, not evidence

## 7. Where research runs out (Riemann's opportunities)

No published study covers:
- a zoom or abstraction dial tested with ADHD readers
- reading an AI summary vs the original, compared on later comprehension
- object-constancy transitions for text changing its level of detail
- ADHD-calibrated idle thresholds
- self-made vs given vs co-drafted plans, compared on follow-through
- whether a search-first reference mode beats summaries (inferred only)
- landmark selection for abstraction trees

The event log, the evaluation harness and the §4 experiments can generate this evidence.

## 8. Working with the research base

```bash
python3 research/ledger/ledger.py validate          # schema and ids
python3 research/ledger/ledger.py impact decide     # what holds or breaks for an objective, and the research queue
python3 research/ledger/ledger.py impact plan --set A32.plan=Y   # what-if without editing
python3 research/ledger/ledger.py features          # feature × objective table
python3 research/ledger/ledger.py render            # regenerate VIEWS.md
```

**To add a new objective or user group:**
1. Add a column in `assumptions.json`, using `?` where unsure.
2. Run `impact`.
3. Research only the queue it prints.

## 9. Report index

| # | Report | Engine |
|---|---|---|
| 00 | Brief and approved v1 plan | — |
| 01–08 | Abstraction · cognitive-load design · ADHD · modalities · speed to understanding · spatial · adaptive signals · fluctuation | Sonnet 5 |
| 09 | Cross-domain ideas: **failed** (see NOTE; §2.8) | GPT, then Grok |
| 10 | Skeptic's review (no web access) | Gemini 3.1 Pro |
| 11–18 | Illusion and trust · text zoom and canvases · ADHD deep dive · interruption · efficiency and longitudinal · generation formats · beyond ADHD · purpose and medium | Sonnet 5 |
| 19 | Fact-check of 28 claims | Sonnet 5 |
| 20 | Expert review of v1 synthesis (REVISE, 15 issues; all addressed in this version) | Opus 5.5 |
| 21–23 | Offload vs enhance · plan/execute/monitor · decide/reference/communicate | Sonnet 5 |
