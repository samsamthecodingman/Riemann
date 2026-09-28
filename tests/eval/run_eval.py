#!/usr/bin/env python3
"""Manual evaluation runner. Uses the REAL summariser (network / local
Claude Code login or local proxy) -- not run in CI, not part of pytest.

For each doc + question in questions.yaml: builds the abstraction tree,
computes the frontier at the question's expected_z, and asks the
summariser a rough yes/no question -- "given only this frontier's text,
can you answer this question?" -- printing the verdict per question.

This is a rough check, not a rigorous eval: the judge is the same kind of
model doing the summarising, on a frontier of paraphrased/compressed text,
so treat "NO" verdicts as a signal worth a closer look, not proof of a bug,
and "YES" verdicts as a sanity check, not a guarantee of quality.

Usage:
    uv run python tests/eval/run_eval.py
    uv run python tests/eval/run_eval.py --doc 150-photosynthesis.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from riemann.abstraction.build import start_build
from riemann.abstraction.frontier import expansion_sequence, frontier_at, k_for_z
from riemann.abstraction.summarise import get_summariser

DOCS_DIR = Path(__file__).parent / "docs"
QUESTIONS_PATH = Path(__file__).parent / "questions.yaml"

JUDGE_SYSTEM = """You are a strict yes/no judge. You will be given some excerpts of a document
(possibly compressed summaries mixed with verbatim text) and a question.
Answer ONLY "YES" or "NO" on the first line, based on whether the excerpts
given actually contain enough information to answer the question -- then
one short sentence of reasoning on the second line. Do not use outside
knowledge; judge only by what is in the excerpts."""


async def build_doc_tree(doc_path: Path):
    text = doc_path.read_text(encoding="utf-8")
    summariser = get_summariser()
    tree_id = f"eval-{doc_path.stem}-{int(time.time())}"
    builder = start_build(tree_id, doc_path.stem, text, summariser)
    await builder.task
    return builder.tree, summariser


async def judge(summariser, frontier_text: str, question: str) -> tuple[str, str]:
    prompt = f"Excerpts:\n---\n{frontier_text}\n---\n\nQuestion: {question}"
    raw = await summariser.summarise(prompt, JUDGE_SYSTEM)
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    verdict = lines[0].upper() if lines else "?"
    reason = lines[1] if len(lines) > 1 else ""
    return verdict, reason


async def run_doc(doc_name: str, questions: list[dict]) -> None:
    doc_path = DOCS_DIR / doc_name
    if not doc_path.exists():
        print(f"!! missing doc: {doc_path}")
        return

    print(f"\n=== {doc_name} ===")
    t0 = time.time()
    tree, summariser = await build_doc_tree(doc_path)
    elapsed = time.time() - t0
    print(f"built in {elapsed:.1f}s: max_depth={tree.max_depth}, nodes={len(tree.nodes)}")

    sequence = expansion_sequence(tree)
    total = len(sequence)

    for q in questions:
        z = q["expected_z"]
        k = k_for_z(z, total)
        frontier_ids = frontier_at(tree, sequence, k)
        frontier_text = "\n\n".join(tree.nodes[nid].text for nid in frontier_ids)

        verdict, reason = await judge(summariser, frontier_text, q["question"])
        mark = "OK " if verdict.startswith("YES") else "MISS"
        print(f"  [{mark}] (kintsch={q['kintsch']}, z={z}, k={k}/{total}) {q['question']}")
        if reason:
            print(f"         judge: {verdict} -- {reason}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", help="only run this doc filename (e.g. 150-photosynthesis.md)")
    args = parser.parse_args()

    spec = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))

    print("Rough eval check -- not a rigorous benchmark; see module docstring.")
    for entry in spec:
        if args.doc and entry["doc"] != args.doc:
            continue
        await run_doc(entry["doc"], entry["questions"])


if __name__ == "__main__":
    asyncio.run(main())
