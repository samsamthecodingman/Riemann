#!/usr/bin/env python3
"""Retag pass 2026-09-28: apply the necessity test (SCHEMA.md) to `assumptions`
on the 8 pre-rule findings files. Edits ONLY the `assumptions` array of each
record; every other field is passed through unchanged.

Rule (SCHEMA.md): tag an assumption only if "if this assumption were false,
would this implication stop applying (or invert)?" is yes. Objective-axis
assumptions (A01-A05, A15, A18, A20, A23, A29-A32) apply only to findings
specifically about: learning/retention (A01,A03,A31), effortful/generative
processing (A04,A32), wanting a mental model or reading the content (A02,A05),
learner control (A18), proactivity (A20), detail/compression (A29,A30), error
tolerance (A15), external outcomes (A23). They are dropped from findings about
faithfulness/hallucination, citations/attribution, typography/layout,
accessibility, orientation/anchoring, forgiving/shame-free design, general ADHD
attention/variability, and reading-rate calibration -- these are universal.
Content/modality/population/transfer assumptions (A06-A13, A16, A17, A19, A21,
A22, A24-A28) are left untouched throughout: this pass only reconsiders the
objective-axis set.

DECISIONS below is the full audit trail: only ids present are changed; every
other record in the 8 files is left byte-for-byte identical (module ordering
of dict keys aside -- json.dumps below preserves insertion order per record).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = [
    "01-abstraction.jsonl",
    "02-cogload-design.jsonl",
    "03-adhd.jsonl",
    "04-modalities.jsonl",
    "05-speed-to-understanding.jsonl",
    "21-offload-enhance.jsonl",
    "22-plan-execute-monitor.jsonl",
    "23-decide-reference-communicate.jsonl",
]

# id -> new `assumptions` list. Only ids listed here are touched.
DECISIONS = {
    # --- 01-abstraction.jsonl ---
    # F01-01, F01-02, F01-04, F01-14, F01-15, F01-16: no change (no objective-axis ids,
    # or the objective ids already pass necessity -- left out of this dict).
    "F01-03": ["A30"],          # density/readability tradeoff is a compression question (A30); not tied to wanting a mental model (A02) or effort (A04)
    "F01-05": ["A29", "A30"],   # fixed word-count risking wrong-content-dropped is squarely detail/compression
    "F01-06": ["A29"],          # aspect-focused re-summarisation is a detail-slicing feature scoping call
    "F01-07": [],               # n-gram overlap as faithfulness proxy: general faithfulness finding, applies to every objective
    "F01-08": ["A14"],          # hallucination rate is a universal design constraint; A14 (faithfulness) is content/scope, not objective
    "F01-09": [],               # error-compounding architecture risk: universal faithfulness finding
    "F01-10": ["A14"],          # SummaC faithfulness signal: universal
    "F01-11": ["A14"],          # QAGS faithfulness method: universal
    "F01-12": ["A14"],          # atomic-fact faithfulness method: universal
    "F01-13": ["A14"],          # clickable citation building trust: universal (citations/attribution)
    "F01-17": [],               # "L0 states the central claim" is a universal bottom-line-up-front finding, not learning/effort/detail-specific -- the 12-assumption over-tag SCHEMA.md warns about
    "F01-18": ["A14"],          # extractive highlighting as lower-hallucination-risk alternative: universal
    "F01-19": [],               # dual-pane summary/source switching cost: orientation/anchoring, universal
    "F01-20": [],               # wpm calibration: reading-rate calibration, universal
    "F01-21": [],               # claim-seeking not topic-seeking prompt guidance: universal writing guidance
    "F01-22": ["A02"],          # whether an abstraction level delivers understanding-in-time is about wanting a mental model now

    # --- 02-cogload-design.jsonl ---
    "F02-01": [],                # extraneous-load/comprehension lever: general cogload finding
    "F02-02": ["A08"],           # fixed-vs-continuous detail dial miscalibration: general design finding (A08 kept, non-objective)
    "F02-03": [],                # contiguity/signalling/seductive-detail effects: general cogload finding
    "F02-04": ["A10", "A21"],    # preattentive vocabulary for zoom level: general layout finding (A10/A21 kept, non-objective)
    "F02-05": [],                # visual clutter as measurable quantity: general
    "F02-06": [],                # data-ink ratio not universally optimal: general
    "F02-07": ["A10"],           # prose column width cap: general layout (A10 kept, non-objective)
    "F02-09": ["A22"],           # L2 headed blocks with front-loaded claim: general layout (A22 kept, non-objective)
    "F02-10": ["A10", "A21"],    # colour-coding depth: general layout (A10/A21 kept, non-objective)
    "F02-11": [],                # zoom-dial transition animation: general layout/anchoring
    "F02-12": ["A08"],           # default dial position keyed to familiarity: general (A08 kept, non-objective)
    "F02-14": ["A10"],           # theme default: general (A10 kept, non-objective)
    # F02-08: no change (A08, A10 only -- non-objective already).
    # F02-13: no change -- notification/interruption design is specifically about
    #   proactivity (A20) and steering navigation (A18); both pass necessity.

    # --- 03-adhd.jsonl ---
    "F03-03": ["A11", "A12", "A16"],  # instant L0 render to reduce wait-aversion: not tied to proactive surfacing (A20) -- applies regardless
    "F03-16": ["A11"],                # shame-free RSD-aware UI design: universal forgiving-design finding, not proactivity-specific
    "F03-17": ["A11"],                # L0-as-low-stakes-preview framing: universal task-initiation/shame finding, not proactivity-specific
    "F03-18": ["A11"],                # body-doubling lack of evidence: the "don't prioritize" implication holds regardless of A20
    # F03-04: no change -- novelty/interest weighting IN SURFACING/NOTIFICATION design is specifically a proactivity (A20) claim.
    # F03-07: no change -- synced text+audio helping readers is tied to A02 (reading the content).
    # All other 03-adhd records: no objective-axis ids were tagged, or none needed reconsideration.

    # --- 04-modalities.jsonl ---
    "F04-01": [],                      # visual+text redundancy: general modality-pairing finding
    "F04-02": ["A06"],                 # decorative icon expectation: general (A06 kept, non-objective)
    "F04-03": [],                      # audio vs text for long/complex content: general modality finding
    "F04-04": [],                      # read-aloud captioning UX: general modality finding
    "F04-05": ["A18"],                 # never lock a fixed modality preference: about user steering choice (A18)
    "F04-06": ["A09"],                 # audio not inherently inferior: general (A09 kept, non-objective)
    "F04-07": [],                      # playback-speed dial: general modality control
    "F04-08": ["A04", "A05", "A32"],   # navigable/editable tree map explicitly claims a "constructing beats viewing" boost (A32, A04); engaging with content itself (A05)
    "F04-09": ["A22"],                 # content-type-aware auto-formatting: general (A22 kept, non-objective)
    "F04-10": [],                      # infographic as composite of primitives: general
    "F04-11": ["A14"],                 # LLM-diagram trust/validation: universal faithfulness finding
    "F04-12": [],                      # Congruence Principle for zoom animation: general layout finding
    "F04-13": ["A18"],                 # modality as sticky, separate-from-dial control: about user steering (A18)
    "F04-14": ["A29"],                 # preserve causal/narrative connectives: a detail-preservation-under-compression call (A29)
    "F04-15": ["A08", "A29"],          # protect procedural passages near-verbatim: detail-preservation call (A29); A08 kept, non-objective
    "F04-16": ["A14"],                 # faithfulness risk of narrative-connectives prompting: universal faithfulness finding

    # --- 05-speed-to-understanding.jsonl ---
    "F05-01": [],                      # speed-reading debunked / don't oversell: universal honesty claim, not tied to wanting a mental model
    "F05-02": ["A15", "A30"],          # skimming as legitimate lower target: detail/compression (A30) + error/gist tolerance (A15)
    "F05-03": [],                      # wpm calibration: reading-rate calibration, universal
    "F05-04": ["A01"],                 # Bloom vs abstraction-depth distinction: about learning/capability targets
    "F05-05": ["A01"],                 # SOLO depth-level mapping to "target depth": about learning targets
    "F05-06": ["A01", "A02", "A04"],   # Kintsch situation-model design for L0-L3: learning (A01), wanting a mental model (A02), effortful processing (A04)
    "F05-07": ["A01", "A03", "A31"],   # L0/L1 as durable-retention target: learning/retention (A01,A31) + own-memory (A03)
    "F05-08": ["A02"],                 # L2 as graphic pre-organiser before L3: wanting a mental model before committing to detail
    "F05-09": ["A04", "A32"],          # prequestion as germane-load/generation technique: effortful+generative processing
    "F05-10": ["A01", "A03", "A31"],   # retrieval/spaced practice behind an explicit "remember later" toggle: learning/retention
    "F05-11": ["A08"],                 # adapt scaffolding to prior knowledge: general adaptive finding (A08 kept, non-objective)
    "F05-12": ["A24"],                 # target-depth + time-budget allocation model: general (A24 kept, non-objective)
    "F05-13": ["A01", "A03", "A31"],   # Dunlosky ratings answer a retention question, not a fast-comprehension one: learning/retention

    # --- 21-offload-enhance.jsonl ---
    "F21-01": ["A03", "A11", "A12"],   # offloading rationality is squarely about own-memory-vs-external (A03); effort (A04) not necessary
    "F21-03": ["A03"],                 # over-offloading failure mode: own-memory question
    "F21-07": ["A03"],                 # offloading trades immediate performance for unaided memory: own-memory question
    "F21-10": ["A03"],                 # Masicampo: relief comes from commitment, not holding the goal in mind -- exactly A03's territory
    "F21-11": ["A03"],                 # GTD externalization philosophy: own-memory question
    # F21-02, F21-04, F21-05, F21-06, F21-08, F21-09, F21-12: no change --
    #   A03 already necessary where tagged, or no objective-axis ids present.

    # --- 22-plan-execute-monitor.jsonl ---
    "F22-01": ["A12", "A13"],                 # subgoal decomposition improving performance/motivation: not specifically about self-generation (A32) or effort (A04) -- the structure helps regardless of who authored it
    "F22-06": ["A32", "A12", "A13"],          # self-generated artifacts valued more: exactly A32's claim; A03/A04 not necessary
    "F22-08": ["A32", "A18", "A12", "A13"],   # co-constructing plan drives commitment: self-generation (A32) + user steering the construction (A18)
    # F22-02..05, F22-07, F22-09..13: no change -- no objective-axis ids, or (F22-07: A18 autonomy,
    #   F22-12: A23 external-outcome, F22-13: A15+A30 diff-vs-compression) already pass necessity.

    # --- 23-decide-reference-communicate.jsonl ---
    "F23-11": ["A18"],   # known-item lookup via search-plus-jump: about user steering own navigation (A18); not about wanting a mental model (A02)
    "F23-18": ["A27"],   # recipient-context field for briefing: applies regardless of A05 (engaging with content itself)
    # F23-09 (resolves A29xdecide), F23-10 (resolves A20xdecide), F23-12 (A02+A23
    #   distinguishing orientation vs lookup), F23-13 (A23 external outcome): no change --
    #   these are exactly the findings the objective assumptions are meant to gate.
}


def main():
    findings_dir = os.path.join(HERE, "findings")
    total_records = 0
    total_changed = 0
    before_total_assumptions = 0
    after_total_assumptions = 0

    for fn in FILES:
        path = os.path.join(findings_dir, fn)
        records = []
        with open(path) as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                records.append(json.loads(line))

        changed_here = 0
        for rec in records:
            total_records += 1
            before = rec.get("assumptions", [])
            before_total_assumptions += len(before)
            if rec["id"] in DECISIONS:
                new = DECISIONS[rec["id"]]
                if new != before:
                    changed_here += 1
                    total_changed += 1
                rec["assumptions"] = new
            after_total_assumptions += len(rec.get("assumptions", []))

        with open(path, "w") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(f"{fn}: {len(records)} records, {changed_here} changed")

    print(f"\nTotal: {total_records} records, {total_changed} changed")
    print(f"Average assumptions/record: before={before_total_assumptions/total_records:.2f} "
          f"after={after_total_assumptions/total_records:.2f}")


if __name__ == "__main__":
    main()
