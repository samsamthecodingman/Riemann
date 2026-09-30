"""Randomised (fixed-seed, stdlib) tests of the zoom sequence over generated
tree shapes: deep chains, wide fans, single leaves and unbalanced trees.

Invariants, for every anchor of every tree:
  * every token names a real internal node, and the last step shows every leaf
  * visible words strictly increase from step to step
  * re-anchoring with keep_expanded leaves the current page unchanged
  * web/frontier.js (run under node) gives the identical sequence, the
    identical page at every k, and kToReveal reveals its target at the
    smallest k that does so
"""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from riemann.abstraction.frontier import (
    expansion_sequence,
    frontier_at,
    prose_at,
    visible_words,
)
from riemann.abstraction.model import Node, Tree

ROOT = Path(__file__).resolve().parent.parent
SEEDS = list(range(1, 21))
# Trees as build.py produces them have no pass-through levels (a non-root node
# with one child is collapsed away), so strict word growth is asserted on those
# shapes; "chain" and "ragged_pt" keep single-child levels to stress the merging
# rules and are checked for everything except strict growth.
REALISTIC = ["single", "fan", "balanced", "lopsided", "ragged"]
PASS_THROUGH = ["chain", "ragged_pt"]
KINDS = REALISTIC + PASS_THROUGH


def _words(n: int, tag: str) -> str:
    return " ".join(f"{tag}{i}" for i in range(n))


def make_tree(seed: int, kind: str, legacy_skim: bool = False) -> Tree:
    """legacy_skim=True lets some internal nodes lack a title / key points (trees
    cached before schema2); those are only checked for well-formedness."""
    rng = random.Random(f"{seed}:{kind}")
    shape: dict[str, list[str]] = {}  # id -> child ids
    parent: dict[str, str | None] = {}
    counter = [0]

    def new(par: str | None) -> str:
        nid = f"n{counter[0]}"
        counter[0] += 1
        shape[nid] = []
        parent[nid] = par
        if par is not None:
            shape[par].append(nid)
        return nid

    root = new(None)
    if kind == "single":
        pass
    elif kind == "fan":
        for _ in range(rng.randint(2, 14)):
            new(root)
    elif kind == "chain":
        cur = root
        for _ in range(rng.randint(2, 7)):
            cur = new(cur)  # single-child chain
        for _ in range(rng.randint(2, 4)):
            new(cur)
    elif kind == "balanced":
        def grow(nid, depth):
            if depth == 0:
                return
            for _ in range(rng.randint(2, 3)):
                grow(new(nid), depth - 1)
        grow(root, rng.randint(2, 3))
    elif kind == "lopsided":
        cur = root
        for _ in range(rng.randint(3, 6)):
            for _ in range(rng.randint(1, 3)):
                new(cur)
            cur = new(cur)
        for _ in range(rng.randint(2, 3)):
            new(cur)
    else:  # ragged (ragged_pt adds the occasional pass-through node)
        choices = [1, 2, 2, 3, 4, 5] if kind == "ragged_pt" else [2, 2, 3, 4, 5]

        def grow(nid, depth):
            if depth == 0 or rng.random() < 0.3:
                return
            for _ in range(rng.choice(choices)):
                grow(new(nid), depth - 1)
        grow(root, rng.randint(2, 5))
        if not shape[root]:
            new(root)
            new(root)

    # depth and spans: leaves take consecutive spans in document order
    order: list[str] = []

    def walk(nid):
        order.append(nid)
        for c in shape[nid]:
            walk(c)

    walk(root)
    leaf_words = {nid: rng.randint(20, 120) for nid in order if not shape[nid]}
    span: dict[str, tuple[int, int]] = {}
    pos = [0]

    def assign(nid):
        if not shape[nid]:
            span[nid] = (pos[0], pos[0] + leaf_words[nid] * 6)
            pos[0] = span[nid][1]
        else:
            for c in shape[nid]:
                assign(c)
            span[nid] = (span[shape[nid][0]][0], span[shape[nid][-1]][1])

    assign(root)

    def depth_of(nid):
        d = 0
        while parent[nid] is not None:
            nid = parent[nid]
            d += 1
        return d

    # A summary is shorter than what it summarises (build.RATIO is 3: about a third), so
    # internal word counts are set bottom-up as a fraction of the children's.
    size: dict[str, int] = {}
    for nid in reversed(order):
        if not shape[nid]:
            size[nid] = leaf_words[nid]
        else:
            size[nid] = max(8, int(sum(size[c] for c in shape[nid]) * rng.uniform(0.28, 0.4)))

    nodes: dict[str, Node] = {}
    for nid in order:
        leaf = not shape[nid]
        w = size[nid]
        has_skim = (not leaf) and (not legacy_skim or rng.random() < 0.85)
        nodes[nid] = Node(
            id=nid, depth=depth_of(nid), text=_words(w, nid), words=w, children=shape[nid], parent=parent[nid],
            is_leaf=leaf, source_span=span[nid], importance=rng.random(),
            title=f"Title {nid}" if has_skim else None,
            key_points=[_words(rng.randint(4, 14), nid + "k") for _ in range(rng.randint(2, 4) if not legacy_skim else rng.randint(0, 3))] if has_skim else [],
            hook=_words(rng.randint(5, 18), nid + "h") if (not leaf and rng.random() < 0.9) else None,
        )
    total = sum(leaf_words.values())
    return Tree(id=f"t{seed}", title="T", source_text="x" * pos[0], source_words=total, root=root,
                nodes=nodes, max_depth=max(n.depth for n in nodes.values()), status="done")


CASES = [(s, k) for s in SEEDS for k in KINDS]


def _anchors(tree: Tree, seed: int, limit: int = 10) -> list[str]:
    """Every node of a small tree; for a big one the root, a leaf and a seeded sample."""
    ids = sorted(tree.nodes)
    if len(ids) <= limit:
        return ids
    rng = random.Random(seed)
    leaf = next(n for n in ids if tree.nodes[n].is_leaf)
    return sorted({tree.root, leaf, *rng.sample(ids, limit - 2)})


def _leaves_in_order(tree: Tree) -> list[str]:
    return sorted((n for n in tree.nodes if tree.nodes[n].is_leaf), key=lambda n: tree.nodes[n].source_span[0])


@pytest.mark.parametrize("seed,kind", CASES)
def test_sequences_are_well_formed_grow_and_end_on_every_leaf(seed, kind):
    tree = make_tree(seed, kind)
    for anchor in _anchors(tree, seed):
        seq = expansion_sequence(tree, anchor)
        internal = {n for n, v in tree.nodes.items() if not v.is_leaf}
        for tok in seq:
            assert tok.lstrip("~") in internal, (seed, kind, anchor, tok)
        assert len(set(seq)) == len(seq), "a token repeats"
        # the last step shows everything
        assert sorted(frontier_at(tree, seq, len(seq))) == sorted(_leaves_in_order(tree)), (seed, kind, anchor)
        # words strictly increase
        words = [visible_words(tree, frontier_at(tree, seq, k), prose_at(seq, k)) for k in range(len(seq) + 1)]
        if kind in REALISTIC:
            for k in range(1, len(words)):
                assert words[k] > words[k - 1], (seed, kind, anchor, k, words)


def _keep_for(tree, frontier, prose):
    keep = set()
    on_page = set(frontier)
    for nid in frontier:
        p = tree.nodes[nid].parent
        while p is not None and p not in keep:
            keep.add(p)
            p = tree.nodes[p].parent
    keep |= {"~" + n for n in prose if n in on_page and n != tree.root and not tree.nodes[n].is_leaf}
    return keep


@pytest.mark.parametrize("seed,kind", CASES)
def test_keep_expanded_preserves_the_page(seed, kind):
    tree = make_tree(seed, kind)
    rng = random.Random(seed)
    ids = sorted(tree.nodes)
    for _ in range(6):
        old_anchor = rng.choice(ids)
        old_seq = expansion_sequence(tree, old_anchor)
        k = rng.randint(0, len(old_seq))
        frontier, prose = frontier_at(tree, old_seq, k), prose_at(old_seq, k)
        keep = _keep_for(tree, frontier, prose)
        on_page = set(frontier)
        new_anchor = rng.choice(ids)
        seq = expansion_sequence(tree, new_anchor, keep_expanded=keep)
        assert frontier_at(tree, seq, len(keep)) == frontier, (seed, kind, old_anchor, k, new_anchor)
        assert {n for n in prose_at(seq, len(keep)) if n in on_page} == {n for n in prose if n in on_page}


NODE = shutil.which("node")

JS_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const trees = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const F = window.Frontier;
const out = trees.map((tree) => {
  const res = {};
  const ids = Object.keys(tree.nodes).filter((_, i) => i % Math.max(1, Math.ceil(Object.keys(tree.nodes).length / 10)) === 0);
  for (const anchor of ids) {
    const seq = F.buildExpansionSequence(tree, anchor);
    const pages = [];
    for (let k = 0; k <= seq.length; k++) pages.push([F.frontierAtK(tree, seq, k), [...F.proseAtK(seq, k)].sort()]);
    // kToReveal: smallest k at which every ancestor of the node is open
    const reveal = {};
    for (const nid of Object.keys(tree.nodes)) reveal[nid] = F.kToReveal(tree, seq, nid);
    res[anchor] = { seq, pages, reveal };
  }
  return res;
});
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_js_matches_python_on_random_trees_and_ktoreveal_reveals(tmp_path):
    trees = [make_tree(s, k) for s in SEEDS[:6] for k in KINDS]
    path = tmp_path / "trees.json"
    path.write_text(json.dumps([json.loads(t.model_dump_json()) for t in trees]))
    js = json.loads(subprocess.run(
        [NODE, "-e", JS_SCRIPT, str(ROOT / "web" / "frontier.js"), str(path)],
        capture_output=True, text=True, check=True,
    ).stdout)
    for tree, res in zip(trees, js):
        for anchor, r in res.items():
            py_seq = expansion_sequence(tree, anchor)
            assert r["seq"] == py_seq, (tree.id, anchor)
            for k, (jf, jp) in enumerate(r["pages"]):
                assert jf == frontier_at(tree, py_seq, k), (tree.id, anchor, k)
                assert jp == sorted(prose_at(py_seq, k)), (tree.id, anchor, k)
            for nid, k in r["reveal"].items():
                front = frontier_at(tree, py_seq, k)
                if tree.nodes[nid].children and nid not in front:
                    # a pass-through level is never shown itself; its content is on the page
                    # as the descendants that replace it
                    lo, hi = tree.nodes[nid].source_span
                    assert any(tree.nodes[f].source_span[0] < hi and tree.nodes[f].source_span[1] > lo for f in front), (
                        tree.id, anchor, nid, k)
                else:
                    assert nid in front, (tree.id, anchor, nid, k)
                if k > 0 and nid in front:
                    assert nid not in frontier_at(tree, py_seq, k - 1), (tree.id, anchor, nid, k)
