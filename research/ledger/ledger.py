#!/usr/bin/env python3
"""Riemann research ledger: validate, query and stress-test the assumption-tracked research base.

  python3 ledger.py validate                      check every findings/*.jsonl against the canonical ids
  python3 ledger.py matrix                        assumption x objective table
  python3 ledger.py impact <objective> [--set A03.plan=N ...]
                                                  which findings/features hold, break or need research for an objective
  python3 ledger.py features                      feature x objective status table
  python3 ledger.py finding <id>                  one finding with its per-objective applicability
  python3 ledger.py todo                          every '?' cell and the findings waiting on it (the research queue)
  python3 ledger.py render                        regenerate VIEWS.md

`--set` overrides assumption cells for a what-if run without editing assumptions.json,
e.g. to preview what adding a population or changing a judgement would invalidate.
See SCHEMA.md for the data model and the applicability rule.
"""
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RANK = {"Y": 0, "C": 1, "?": 2, "N": 3}   # worse status wins when combining assumptions
GRADES = {"S", "M", "W", "MYTH"}


def load():
    objectives = json.load(open(os.path.join(HERE, "objectives.json")))
    assumptions = {a["id"]: a for a in json.load(open(os.path.join(HERE, "assumptions.json")))}
    features = set(json.load(open(os.path.join(HERE, "features.json"))))
    findings, errors = [], []
    for path in sorted(glob.glob(os.path.join(HERE, "findings", "*.jsonl"))):
        for n, line in enumerate(open(path), 1):
            if not line.strip():
                continue
            try:
                f = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{os.path.basename(path)}:{n}: bad JSON ({e})")
                continue
            f["_file"] = os.path.basename(path)
            findings.append(f)
    return objectives, assumptions, features, findings, errors


def apply_overrides(assumptions, sets):
    for s in sets:
        key, val = s.split("=")
        aid, obj = key.split(".")
        assumptions[aid]["holds"][obj] = val


def status(finding, obj, assumptions):
    """Applicability of a finding to an objective: worst status across its assumptions."""
    worst, blockers = "Y", []
    for aid in finding.get("assumptions", []):
        a = assumptions.get(aid)
        if not a:
            continue
        s = a["holds"].get(obj, "?")
        if RANK[s] > RANK["Y"]:
            blockers.append(f"{aid}={s}")
        if RANK[s] > RANK[worst]:
            worst = s
    return worst, blockers


def feature_status(findings, obj, assumptions):
    """Per feature: best status among supporting findings, plus opposing findings that still apply."""
    sup, opp = defaultdict(list), defaultdict(list)
    for f in findings:
        st, _ = status(f, obj, assumptions)
        for imp in f.get("implications", []):
            for ft in imp.get("features", []):
                (opp if imp.get("effect") == "opposes" else sup)[ft].append((st, f["id"]))
    out = {}
    for ft in set(sup) | set(opp):
        s = min((x[0] for x in sup[ft]), key=RANK.get, default="-")
        o = [fid for st, fid in opp[ft] if st in ("Y", "C")]
        out[ft] = (s, o, sup[ft])
    return out


def cmd_validate(objectives, assumptions, features, findings, errors):
    ids = defaultdict(int)
    proposals = []
    for f in findings:
        ids[f.get("id")] += 1
        where = f"{f['_file']}:{f.get('id')}"
        for k in ("id", "report", "claim", "evidence", "assumptions", "implications", "confidence"):
            if k not in f:
                errors.append(f"{where}: missing '{k}'")
        g = (f.get("evidence") or {}).get("grade")
        if g not in GRADES:
            errors.append(f"{where}: bad grade {g!r}")
        for aid in f.get("assumptions", []):
            if aid not in assumptions:
                errors.append(f"{where}: unknown assumption {aid}")
        for imp in f.get("implications", []):
            for ft in imp.get("features", []):
                if ft not in features:
                    errors.append(f"{where}: unknown feature {ft}")
        for na in f.get("new_assumptions", []) or []:
            proposals.append((where, na.get("text") if isinstance(na, dict) else na))
    for i, c in ids.items():
        if c > 1:
            errors.append(f"duplicate id {i} x{c}")
    by_file = defaultdict(int)
    for f in findings:
        by_file[f["_file"]] += 1
    print(f"{len(findings)} findings in {len(by_file)} files")
    for k, v in sorted(by_file.items()):
        print(f"  {k}: {v}")
    print(f"\n{len(errors)} errors")
    for e in errors[:200]:
        print("  " + e)
    if proposals:
        print(f"\n{len(proposals)} proposed new assumptions (merge into assumptions.json by hand):")
        for w, t in proposals:
            print(f"  {w}: {t}")
    return 1 if errors else 0


def cmd_matrix(objectives, assumptions, *_):
    objs = list(objectives)
    print("| id | assumption | axis | " + " | ".join(o[:5] for o in objs) + " |")
    print("|---|---|---|" + "---|" * len(objs))
    for a in assumptions.values():
        print(f"| {a['id']} | {a['text']} | {a['axis']} | " + " | ".join(a["holds"].get(o, "?") for o in objs) + " |")


def cmd_impact(objectives, assumptions, features, findings, obj):
    if obj not in objectives:
        sys.exit(f"unknown objective {obj}; known: {', '.join(objectives)}")
    groups = defaultdict(list)
    for f in findings:
        st, blockers = status(f, obj, assumptions)
        groups[st].append((f, blockers))
    print(f"# Impact for objective: {obj} ({objectives[obj]['optimises']})\n")
    print("Findings: " + ", ".join(f"{k}={len(groups[k])}" for k in ("Y", "C", "?", "N")) + "\n")
    q = defaultdict(list)
    for f, b in groups["?"]:
        for x in b:
            if x.endswith("=?"):
                q[x[:-2]].append(f["id"])
    if q:
        print("## Research queue ('?' assumptions blocking findings)")
        for aid, fids in sorted(q.items(), key=lambda kv: -len(kv[1])):
            print(f"- **{aid}** {assumptions[aid]['text']}: blocks {len(fids)} findings ({', '.join(fids[:8])}{'…' if len(fids) > 8 else ''})")
        print()
    print("## Findings that do NOT apply (an assumption fails)")
    for f, b in groups["N"]:
        print(f"- {f['id']} [{f['evidence']['grade']}] {f['claim'][:110]} ← {', '.join(x for x in b if x.endswith('=N'))}")
    print("\n## Feature status")
    for ft, (s, opp, sup) in sorted(feature_status(findings, obj, assumptions).items(), key=lambda kv: RANK.get(kv[1][0], 9)):
        flag = f"  ⚠ opposed by {', '.join(opp)}" if opp else ""
        print(f"- {ft}: {s} ({len(sup)} supporting){flag}")


def cmd_features(objectives, assumptions, features, findings, *_):
    objs = list(objectives)
    table = {o: feature_status(findings, o, assumptions) for o in objs}
    print("| feature | " + " | ".join(o[:5] for o in objs) + " |")
    print("|---|" + "---|" * len(objs))
    for ft in sorted(features):
        cells = []
        for o in objs:
            s, opp, _ = table[o].get(ft, ("-", [], []))
            cells.append(s + ("!" if opp else ""))
        print(f"| {ft} | " + " | ".join(cells) + " |")
    print("\nY applies · C conditional · ? needs research · N doesn't apply · - no evidence · ! an applicable finding opposes it")


def cmd_finding(objectives, assumptions, features, findings, fid):
    f = next((x for x in findings if x["id"] == fid), None)
    if not f:
        sys.exit(f"no finding {fid}")
    print(json.dumps({k: v for k, v in f.items() if not k.startswith("_")}, indent=1))
    print("\napplicability:")
    for o in objectives:
        st, b = status(f, o, assumptions)
        print(f"  {o:12s} {st}  {' '.join(b)}")


def cmd_todo(objectives, assumptions, features, findings, *_):
    for a in assumptions.values():
        for o, s in a["holds"].items():
            if s == "?":
                n = sum(1 for f in findings if a["id"] in f.get("assumptions", []))
                print(f"{a['id']}×{o}: {a['text']}  ({n} findings depend on {a['id']})")


def cmd_render(objectives, assumptions, features, findings, *_):
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("# Ledger views (generated by `ledger.py render`; do not edit)\n")
        print("## Assumption × objective\n")
        cmd_matrix(objectives, assumptions)
        print("\n## Feature × objective\n")
        cmd_features(objectives, assumptions, features, findings)
        print("\n## Open research cells\n")
        cmd_todo(objectives, assumptions, features, findings)
    open(os.path.join(HERE, "VIEWS.md"), "w").write(buf.getvalue())
    print(f"wrote VIEWS.md ({len(findings)} findings)")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    sets = []
    while "--set" in argv:
        i = argv.index("--set")
        sets.append(argv[i + 1])
        del argv[i:i + 2]
    objectives, assumptions, features, findings, errors = load()
    apply_overrides(assumptions, sets)
    cmd, args = argv[0], argv[1:]
    if cmd == "validate":
        sys.exit(cmd_validate(objectives, assumptions, features, findings, errors))
    fn = {"matrix": cmd_matrix, "impact": cmd_impact, "features": cmd_features,
          "finding": cmd_finding, "todo": cmd_todo, "render": cmd_render}.get(cmd)
    if not fn:
        sys.exit(__doc__)
    fn(objectives, assumptions, features, findings, *args)


if __name__ == "__main__":
    main(sys.argv[1:])
