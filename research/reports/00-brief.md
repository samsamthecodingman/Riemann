# Fleet brief: Riemann research (shared by all workers)

## What Riemann is
Riemann is a personal assistant that Sam is building. Sam is an engineering student and has ADHD. The assistant aggregates email, calendar, tasks and notes, and presents information adaptively, with voice as a background channel. Principles:
- zero-to-useful setup
- works within the user's cognitive load: it only asks for what they have capacity to give, and is useful with zero input
- load capacity and emotional state are two separate, fluctuating signals
- it processes and presents information and never takes real-world actions

It will eventually have a **spatial view**, where proximity means relatedness, there is a stable home anchor, and depth encodes importance.

## The first feature: rolling abstraction ("zoom dial")
Any large chunk of content (text, file, URL) becomes an abstraction tree:
- L0: a one-line gist
- L1: a summary readable in 1–2 minutes
- L2: section gists
- L3: the original text

One continuous dial zooms between levels, and the passage at the centre of the viewport stays anchored while you zoom. v1 renders plain markdown on a local web page; later the same tree drives the spatial view. See 00-plan.md for the full plan.

**Sam's ultimate goal:** take any large chunk of content and reach *any chosen level of understanding in the shortest possible time*, in a way that flexes with fluctuating attention, motivation and energy (ADHD). It should also work for other people later.

## Baseline research already done (do not just repeat it; go deeper and challenge it)
- **Cognitive Load Theory:** minimise extraneous load, keep intrinsic load to what the task needs, and spend spare capacity on germane load.
- **Method of loci:** spatial placement recruits hippocampal navigation and memory systems. Spatial layout can also hurt if poorly structured.
- **Interface implications:**
  - depth encodes importance
  - one fixed home anchor
  - distinct visual landmarks, not just labels
  - layered depth instead of flat or deep menus
  - consistent structure over time
  - new features attach to familiar regions
- **Split attention:** keep related items co-located. Progressive disclosure has to be balanced against the need to compare things. Prior familiarity changes load. Feedback should be fast and unambiguous.
- **Adaptive load scaling:** dense views when energised, the bare minimum at a low point. This is controlled in the moment and through learned patterns.

## Output contract (every worker)
Write your report to `research/<your-slug>.md` in this directory, as markdown, with these sections:
1. **TL;DR:** 5–10 bullets.
2. **Findings.** Each finding has a claim, an evidence-strength tag and sources:
   - The tag is one of STRONG (meta-analyses or replicated work), MODERATE, WEAK/PRELIMINARY, or MYTH/DEBUNKED.
   - Give real URLs or DOIs you actually opened. Never invent citations; if you're unsure, say so.
3. **Design implications for Riemann.** These should be concrete and buildable, tied to the zoom dial, the abstraction tree, the spatial view, or adaptivity.
4. **Signals Riemann could measure.** Implicit or explicit, and low-friction.
5. **Contradictions and caveats**, including where the evidence conflicts or doesn't transfer to one adult user.
6. **Gaps.** Adjacent topics you think the fleet should research next, and why. This drives a second wave, so be specific.

Aim for depth: primary papers, meta-analyses, HCI venues (CHI, UIST, VIS, IUI, UMAP), cognitive science, and practitioner knowledge (designers, teachers, ADHD coaches). Look past the first page of results. Flag pop-science claims explicitly.

## Fleet protocol (Redis, 127.0.0.1)
- On start: `redis-cli XADD fleet:events '*' agent <your-name> action claimed detail "<slug>"`
- On finish: `redis-cli XADD fleet:events '*' agent <your-name> action completed detail "<slug> written"`, or use `action failed` with a reason.
- To contact another worker directly: `redis-cli RPUSH agent:<their-name>:inbox "<msg>"`. The worker names are in 00-roster.md. Use this if you find something squarely in their area.
