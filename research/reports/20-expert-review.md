VERDICT: REVISE

Reviewer: claude-opus-5-5. Reviewed: /home/samroberts/Projects/riemann/research/RIEMANN-ABSORPTION-MODEL.md (including the §2.7 cross-domain table added during review) against 00-brief, 00-plan, reports 01–18 and 19-factcheck.

Overall: the model is well structured. Most grades and citations are faithful, and the core shape (depth dial, grounding, orientation, shame-neutral design, explicit input before inference) is right for Sam. It is not ready to hand over as the build basis for three reasons. §3 claims "no scope widening" but does widen scope. The v1 pipeline cannot deliver the "instant L0" the model calls *the* anti-avoidance mechanism. Several grades are inflated from M to S, or carry a ⚑ the fact-check did not grant. All of the fixes below are edits to the synthesis. None needs new research.

## Issues (most important first)

1. **§3 contradicts itself on scope: "These additions fit v1 without widening its scope."** 00-plan's out-of-scope list includes "persistence beyond the tree cache". §3 items 5 and 6 (a JSONL event log, and a resume card saved on close and shown on reopen) are exactly that. Other additions are also new work beyond the plan:
   - `kind` (prose/procedure/comparison/timeline). Format-by-content is graded W/M in §2.4 and nothing in v1 renders by kind.
   - A faithfulness score (see #4).
   - A two-pass density step.
   - Spacing controls.
   - Paged levels (see #6).

   **Fix:** delete the "without widening its scope" sentence and split §3 into (a) *fits the plan as written* and (b) *proposed plan amendments needing Sam's OK*.
   - (a) Claim-first L0 prompt, length check with one retry, verbatim code/procedure leaves, atomic code/equation chunks, labelled detents, persistent L0 header, reduced-motion handling, ARIA slider, source-span hover (it reuses the existing `source_span`), no progress bar, and the eval harness as a test fixture.
   - (b) Event log, resume card, `leaves_out`, spacing controls.
   - Defer to v1.x: `kind`, faithfulness scoring, the density pass and paging.
   - The resume card can live in browser storage, which avoids amending the persistence rule.

2. **Internal contradiction: "instant L0" versus a pipeline that produces L0 last.** L1 item 5 says "an instant, low-commitment L0 is *the* anti-avoidance mechanism". The Low-capacity row defaults to L0. Yet §2.2 says "Show L3 immediately and stream the levels in", and 00-plan builds leaves → L2 → L1 → L0, so on the map-reduce path L0 arrives *last*. The two-pass density step in §3 item 1 delays L0 further. At low capacity, Sam would open a document and see 5k words of source, which is the opposite of the intent (03 F3 delay aversion).
   - **Fix:** add to §3 a cheap, fast *provisional* L0 call made first (on the title plus the first ~2k tokens), shown in the L0 header and replaced when the grounded L0 arrives.
   - In the single-call path, order the JSON so L0 streams first.
   - Drop the density pass from v1, or run it after the first render.
   - Say explicitly that until L0 exists the page shows a one-line "gist coming" placeholder, not a wall of L3, whenever the default level is L0.

3. **Motivation, which the brief makes a primary axis, is missing from the model.** Sam's goal names "attention, motivation and energy". 08's TL;DR says "Motivation is not a single dial. SDT … curiosity/information-gap … interest development … pullable independent of raw energy level." 03 flags interest/novelty (PINCH, heuristic grade). The model's STATE box has only capacity × affect. Motivation shows up only as a curiosity-gap L0 experiment and a utility-value prompt.
   - **Fix:** add an INTEREST/MOTIVATION input (low/neutral/pulled) with its own levers:
     - curiosity-gap L0 and the "skip map" when interest is low
     - bounded choice (13, Dunlap) for autonomy
     - immediate visible payoff (13, novelty with fast feedback)
     - the self-generated relevance prompt (18)
   - Add a row to the §1.2 table for "capacity fine, motivation low". This is the classic ADHD "can't make myself start" state, and it differs from low capacity.

4. **The faithfulness score is under-specified and risky to build first.** §2.1 says "Store a cheap faithfulness score per node (NLI/SummaC-style, or n-gram overlap)", and §3 adds `faithfulness: float | None`. SummaC needs an NLI model, i.e. a heavy torch dependency that 00-plan's pyproject doesn't have. N-gram overlap penalises good abstractive L0/L1 text (01 notes overlap *predicts* unfaithfulness, not that low overlap proves it). 16 notes an LLM judge correlates only ~0.63 with humans.
   - **Fix:** in v1, keep the field nullable and unset. Rely on L2 gists citing leaf ids (already in the plan) plus source-span hover.
   - Make the score a v1.x item with a named method.
   - Also state how "ground L1/L0 against leaf spans" works on the >120k map-reduce path: whole leaves don't fit in one call there, so ground via cited leaf ids and spot-check.

5. **Grades inflated beyond the source reports (criterion 1):**
   - "Interruption tiers map to channels … | S | 14". In 14, breakpoints are S, but Fitz batching is M–S, and calm tech and the ADHD angle are M or W/M. The three-tier mapping itself is a fleet design, so it should be **M**.
   - "Persistent L0 header plus a breadcrumb … | S | 06, 12". 12 grades the Workflowy/Logseq pattern MODERATE (practitioner convergence), so this should be **M**.
   - "The home anchor never moves … (habit-context binding) | S | 08". Wood's habit findings are S, but the transfer to UI layout is an inference (08 design implication 9), so this should be **M**.
   - "Source-span hover … under ~5 s … | S (mechanism)". The ~5 s threshold does not appear in 11 or anywhere in the fleet, and Vasconcelos's numeric effects weren't extracted (11: "PDF didn't parse"). Either drop the number or label it "design target, unsourced".
   - L1 item 2, "Easy summaries create an *illusion of understanding* (S)". 11 grades the illusion of explanatory depth as S *for explanatory knowledge*, and grades the summary-specific claim (finding 4) as **MODERATE, mixed**. §7 of the synthesis itself says nobody has compared "reading an AI summary vs the original for later comprehension". Reword to "the illusion of explanatory depth is S; that AI summaries trigger it is a strong inference, not yet measured".

6. **"Discrete, paged levels rather than endless scroll" conflicts with the plan's anchoring mechanism and overreaches 18.** 18's paging evidence (M, older studies) compares scrolling with paging *within one text*. 00-plan's anchoring is scroll-based ("the view scrolls to keep it anchored"). Paging L3 (the full source) changes the anchor model, the "flat walk" renderer and the tests. It is also unclear what a "page" means at L0 or L1.
   - **Fix:** in v1, make each *level* a distinct view (it already is) and keep scrolling within a level.
   - Move "paginate L3" to a v1.x n-of-1 experiment (§4) rather than a v1 principle.

7. **Fact-check flags misused (⚑ implies confirmation the fact-check didn't give):**
   - "Kalyuga-style rapid true/false check … correlates well with full tests ⚑". 19 marks this CORRECTED (the r=.66 and the 3.8× time saving are not confirmed as one study). 15 also says it was "validated on well-defined procedural/STEM domains, not open-ended reading material". Downgrade to W for reading and drop the ⚑.
   - "Khan Academy built a graph-shaped knowledge map and replaced it with a simple ladder ⚑". 19 confirms only *that* it was retired. The UX reason rests on a fan wiki, and Google Maps API deprecation is an alternative explanation. Say "retired (reason unclear)" and treat it as product precedent (15 caveat), not evidence.
   - "Progressive disclosure beyond 2 levels confuses people unless every level is labelled ⚑". Nielsen's warning is what was checked, and only via a search snippet. The clause "unless every level is labelled" is the fleet's own mitigation (12), not a checked claim, so move the ⚑ to the first clause only.
   - L1 item 2 cites "20–45% of multi-document summaries". Riemann is single-document, and the single-document figure (28.6%) was the fact-check's one real correction. Add a phrase saying the single-document rate is unverified but non-trivial (01, 19 #24).

8. **The strongest-evidence claim is misapplied.** L1 item 4 reads: "The strongest lever in education is fast, low-stakes feedback loops (S, 0.4–0.7) … Every dial movement should respond instantly." Black & Wiliam's formative assessment (07) means feedback on *the learner's own performance*, not UI latency. 07 itself notes effect-size heterogeneity. From outside the fleet, I'd add that later re-analyses such as Kingston & Nash 2011 put it nearer ~0.2.
   - **Fix:** split the two ideas. UI responsiveness is justified by delay aversion (03) and direct manipulation. Formative feedback is the retrieval check, which in the synthesis only arrives in v1.x.
   - Grade the 0.4–0.7 as "S for direction, effect size contested".

9. **§2.7 breaks the document's provenance contract and cites a file that doesn't exist.** The header says "every claim here traces to one of them [the reports]". §2.7 says it is "curated from that output plus the orchestrator's own knowledge" and points to `09-lateral-grok-partial.md`, but only `09.log` exists. The synthesis also cites `reports/…` paths, and `/home/samroberts/Projects/riemann/research/reports/` does not exist.
   - **Fix:** copy reports 00–19 into `research/reports/` (converting 09.log to the partial .md it names).
   - Mark §2.7 rows as "orchestrator, unsourced hypothesis", or remove "every claim traces" from the header.
   - Also fix the worker count: the index shows 16 web-research reports (01–08, 11–18) plus 09, 10 and 19, not "17 web-research workers".

10. **§2.7 introduces completion and backlog framing that contradicts FORGIVING.**
    - "Fog of war / minimap … shows explored vs unexplored. A quest log lists open loops" is a completion display. §2.2 bans "% read", and 13 explains why: progress reveals remaining effort, and shame after unfinished tasks increases avoidance.
    - "Log silently … decays, never a growing backlog" (§2.3) also conflicts with a quest log of open loops.
    - **Fix:** restate these as "explored regions shown positively (what you've seen), never an unexplored or remaining count, and no persistent open-loop list". Alternatively, cut them.
    - Similarly, "L0 carries the *why* ('so that…')" conflicts with "L0 is a claim … ≤25 words". Pick one, or make "intent" an L1 opener.

11. **The v1 page is dense, which contradicts the Low-capacity row, and "bounded choices at open" adds a decision at the moment of avoidance.** The Low-capacity row says "one thing on screen". §3's v1 frontend puts on screen at once:
    - an L0 header, breadcrumb, home control and dial
    - read-time labels
    - a "leaves out" line
    - spacing controls
    - a "get unstuck" control (§2.2, and not actually listed in §3)

    Separately, §2.3 "bounded choices at open ('start at L0 / jump to section / let Riemann pick')" puts a choice before any content, against "instant L0" and "useful with zero input" (brief).
    - **Fix:** specify a minimal chrome mode in which everything but the text and dial is hidden until hover or focus.
    - Open immediately at the default, with the bounded options as a non-blocking row underneath.
    - Decide whether "get unstuck" is in v1 and say what it does.

12. **v1 has no answer to "what level does it open at?", which is the one adaptive decision v1 must make.** State inputs are all v1.x or later, and §5 leaves "open where it thinks best vs last level" open. A v1 serving fluctuating capacity needs one zero-input rule.
    - **Fix:** in v1, open at L1 with L0 always visible in the header, which gives Sam the gist and the 2-min read with no taps. Reopening a document returns to the last level and anchor via the resume card.
    - Record this as the v1 default, and feed §4 experiment 4 from it.

13. **The "chosen level of understanding" goal is conflated with the depth of the text.** Sam's goal is to reach "*any chosen level of understanding* in the shortest possible time". 05's TL;DR says levels of understanding are "not one dial" (Kintsch surface/textbase/situation model), and frames the problem as budget allocation (time budget plus target depth → path plus active techniques). The model's DEPTH dial is text granularity, and only the eval harness gestures at understanding.
    - **Fix:** add a short §1.5 that maps purpose × target understanding (gist / explain / apply / recall) to a recommended path, e.g. "explain" = L1 + L2 + one retrieval check.
    - Make the eval harness tag each question with its Kintsch level, so Riemann's own logs produce the gain-per-minute table that 15 says the literature lacks.

14. **Dropped findings that would change decisions:**
    - (a) Screen inferiority for expository text is **worsened by time pressure** (18, Delgado g≈−0.21 to −0.27). Prominent "~1:50" read-time labels may create exactly that pressure. Show time estimates on the dial detent only, and add "time-label on/off" to §4.
    - (b) Report 17 says personalisation dimensions whose effects *reverse between individuals* (noise, motion, audio pairing, literalness) "should be explicit settings, not inferred". The LOOP applies a contextual bandit broadly. Restrict the bandit to the default *depth* and keep those dimensions explicit.
    - (c) Monotropism (17): unanticipated interruption is "truly, if briefly, catastrophic" for autistic users, which is a stricter constraint than ADHD's. §1.2 mentions only ME/CFS for others. Add monotropism to the "other people later" note and make "never interrupt" a first-class tier setting.
    - (d) Report 15 says RSVP is an "L0-gist-only tool, never an L2/L3 substitute", while 13 proposes it for L3. §4 experiment 2 tests RSVP "at L2/L3" without noting the conflict. Say so, and note that the ADHD study was a single study in young adults.

15. **Minor internal inconsistencies to clean up:**
    - The L0 line says "two dials" (depth, activity), but the diagram has three (MODALITY too).
    - The purpose sets disagree. The diagram lists "gist · decide · reply/act · study · remember". §1.1 lists "study, decide, reply/act, curiosity, look-up" and then says "Reference and decide modes". Use one closed list everywhere.
    - "Breadcrumb ≤3" is trivially true for a four-level tree and duplicates the L0 header. Say the breadcrumb shows L1 › L2 section only.
    - The Bastani citation should note the correction notice (19 #7) before any numbers are quoted.

## Criterion 5 summary (ADHD fit and generality)

The *principles* genuinely serve an adult with ADHD and fluctuating capacity: re-entry at any level, a safe floor, no shame mechanics, explicit input before inference, hyperfocus protection, and the medication non-goal. The *v1 as specified* does not yet deliver them, for four reasons:
- L0 isn't instant (#2).
- There is no open-level rule (#12).
- The page is dense (#11).
- Motivation, which is distinct from capacity, is absent (#3).

Generality is reasonable because the §2.2 accessibility work and the ME/CFS note are there. It would be solid once #14b and #14c are added.
