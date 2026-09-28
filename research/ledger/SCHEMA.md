# Riemann research ledger: schema

The research base is **assumption-tracked**, so a change of objective or population re-opens only the findings it actually breaks.

```
OBSERVATION → EVIDENCE → ASSUMPTIONS → CLAIM → DESIGN IMPLICATION → FEATURE
                                ▲
             objectives.json × assumptions.json   (does assumption A hold for objective O?)
```

## Files
| File | Role | Who edits |
|---|---|---|
| `objectives.json` | The objective vocabulary (understand, learn, remember, decide, plan, execute, monitor, reference, communicate) and what each optimises | orchestrator / Sam |
| `assumptions.json` | Canonical assumptions. Each has a `holds` map of objective → `Y` (holds), `C` (conditional), `N` (fails) or `?` (unknown: needs research) | orchestrator / Sam |
| `features.json` | Canonical feature ids (design decisions or buildable features) | orchestrator |
| `findings/*.jsonl` | One finding per line (schema below) | extraction and research workers |
| `ledger.py` | Validate, query, stress-test and render | — |

## Finding record (one JSON object per line)
```json
{
  "id": "F03-07",                       // F<report><seq>; new research uses F<report>-<seq>
  "report": "03-adhd",
  "observation": "What was observed, in plain words (the raw result).",
  "claim": "The generalised claim the fleet draws from it.",
  "mechanism": "Why it works (or 'unknown').",
  "evidence": {
    "grade": "S|M|W|MYTH",              // strong / moderate / weak-preliminary / debunked
    "sources": ["https://…"],            // only URLs the report says were actually opened
    "factcheck": "confirmed|corrected|unverified|null"   // from 19-factcheck.md if covered
  },
  "population": "e.g. adults with ADHD; undergrads; general adult readers; K-12",
  "context": "e.g. lab, classroom, field RCT, practitioner consensus, product teardown",
  "assumptions": ["A01", "A12"],         // canonical ids ONLY; propose new ones in `new_assumptions`
  "new_assumptions": [],                 // [{"text": "...", "why": "..."}]; merged by the orchestrator
  "implications": [                      // design implications for Riemann
    {"text": "…", "features": ["FT-retrieval-check"], "effect": "supports|opposes|parameterises"}
  ],
  "contradictions": ["F11-04", "free text if no id"],
  "confidence": "high|medium|low"        // for *Riemann applying it*, not the study's internal validity
}
```

### Rules for writers
- **Assumptions are the point.** For each finding, list *every* canonical assumption that must hold for the implication to apply to Riemann, especially the objective ones (A01–A05, A23) and the transfer ones (A11–A13). If none fits, propose a new one.
- `confidence` is lower than the evidence grade whenever the transfer assumptions (A12, A13) are doing heavy lifting.
- One finding = one claim. Split compound findings.
- Myths get `grade: "MYTH"` and an implication with `effect: "opposes"`.
- Never invent sources. Leave `sources` empty if the report didn't cite an opened URL.

## Applicability rule (what `ledger.py` computes)
For a finding *f* and objective *o*:
- **N** if any assumption of *f* has `holds[o] = N`: the implication doesn't apply, and may invert.
- **?** if any assumption has `holds[o] = ?` (and none is N): **research target**.
- **C** if any assumption is `C`: applies with conditions.
- **Y** otherwise.

A feature's status for *o* follows from the findings that support or oppose it.

## Stress-testing a new objective (the workflow)
1. Add the objective to `objectives.json`.
2. Fill its column in `assumptions.json`, using `?` where unsure.
3. `python3 ledger.py impact <objective>` lists affected findings, affected features and the exact `?` assumptions to research.
4. Research **only** those assumptions. New findings go in `findings/`.
5. Update the `?` cells, then re-run. Unaffected evidence is untouched.
