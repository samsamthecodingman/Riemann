"""Zoom goes where the pointer is (docs/v2-macaron-spec.md, "zoom at the pointer").

`Reader` below is the page state machine of web/app.js in miniature: the page, the
dial position k, the sequence and the passage it was built around, and the rule in
setZ that a change of direction rebuilds the sequence (keeping the page as it is).
A gesture is a run of steps over one passage P (the node under the pointer).

  in : each step changes only P's own subtree, for as long as P has something left
       to open; only then does it move on to P's nearest neighbours.
  out: when P is shown as its summary, the first step folds that (back to the skim)
       before any other passage is touched.

The same property is checked end to end in a browser by tests/e2e (runner.js,
zoom_goes_where_the_pointer_is). The expansion order itself is shared with
web/frontier.js, which tests/test_frontier_parity.py keeps identical."""
import random

import pytest

from riemann.abstraction.frontier import expansion_sequence, frontier_at, prose_at
from riemann.abstraction.model import Node, Tree
from tests.test_frontier_random import KINDS, SEEDS, make_tree


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


class Reader:
    def __init__(self, tree: Tree):
        self.tree = tree
        self.seq = expansion_sequence(tree)
        self.seq_anchor = tree.root
        self.direction = 0
        self.k = 0

    # the page
    def frontier(self):
        return frontier_at(self.tree, self.seq, self.k)

    def prose(self):
        return {n for n in prose_at(self.seq, self.k) if n in set(self.frontier())}

    def shown(self):
        return {n: (n in self.prose()) for n in self.frontier()}

    def _rebuild(self, anchor):
        keep = _keep_for(self.tree, self.frontier(), self.prose())
        self.seq = expansion_sequence(self.tree, anchor, keep_expanded=keep)
        self.seq_anchor = anchor
        self.direction = 0
        self.k = len(keep)

    # beginPointerGesture: a new passage under the pointer rebuilds the sequence around it
    def begin(self, anchor):
        if anchor != self.seq_anchor:
            self._rebuild(anchor)

    # setZ: step +-1 along the dial, rebuilding first if the dial turns round
    def step(self, d):
        d = 1 if d > 0 else -1
        k_to = max(0, min(len(self.seq), self.k + d))
        if k_to == self.k:
            return
        if self.direction and d != self.direction:
            self._rebuild(self.seq_anchor)
            k_to = max(0, min(len(self.seq), self.k + d))
        self.direction = d
        self.k = k_to


def _changed(before: dict, after: dict) -> set:
    return {n for n in set(before) | set(after) if before.get(n) != after.get(n)}


def _in_subtree(tree, nid, root) -> bool:
    while nid is not None:
        if nid == root:
            return True
        nid = tree.nodes[nid].parent
    return False


def _run_gesture(reader: Reader, anchor: str, dirs: list[int]) -> list[str]:
    """Run one gesture and return what, if anything, broke the two rules."""
    tree = reader.tree
    reader.begin(anchor)
    problems = []
    prev = 0
    for i, d in enumerate(dirs):
        before = reader.shown()
        before_prose = {n for n, is_prose in before.items() if is_prose}
        open_in_p = any(_in_subtree(tree, n, anchor) and not tree.nodes[n].is_leaf for n in before)
        reader.step(d)
        after = reader.shown()
        changed = _changed(before, after)
        if d > 0 and open_in_p:
            outside = {n for n in changed if not _in_subtree(tree, n, anchor)}
            if outside:
                problems.append(f"step {i + 1} (in) changed {sorted(outside)} outside {anchor}")
        if d < 0 and d != prev and changed and anchor in before_prose and anchor in before:
            # P is shown as its summary: folding it back to the skim is its own detail, and goes first
            if changed != {anchor}:
                problems.append(f"step {i + 1} (out) changed {sorted(changed)} before {anchor}'s own summary")
        if changed:
            prev = d
    return problems


@pytest.mark.parametrize("seed", SEEDS[:12])
@pytest.mark.parametrize("kind", KINDS)
def test_zoom_in_opens_the_passage_under_the_pointer_first_and_out_folds_it_first(seed, kind):
    tree = make_tree(seed, kind)
    rng = random.Random(f"gestures:{seed}:{kind}")
    reader = Reader(tree)
    for g in range(40):
        anchor = rng.choice(reader.frontier())
        dirs = [rng.choice([1, 1, 1, -1]) if rng.random() < 0.3 else (1 if g % 3 else -1) for _ in range(rng.randint(1, 6))]
        problems = _run_gesture(reader, anchor, dirs)
        assert not problems, (seed, kind, g, anchor, dirs, problems)


def _brief_tree() -> Tree:
    """A page shaped like an assignment brief: root -> a1 -> a2 -> a3 -> hub (a pass-through
    chain), then five sections of three passages of three paragraphs."""
    nodes: dict[str, Node] = {}
    pos = [0]

    def words(n, tag):
        return " ".join(f"{tag}{i}" for i in range(n))

    def add(nid, parent, depth, n, children, span, leaf=False):
        nodes[nid] = Node(
            id=nid, depth=depth, text=words(n, nid), words=n, children=children, parent=parent, is_leaf=leaf,
            source_span=span, importance=0.5, title=None if leaf else words(4, nid + "T"),
            key_points=[] if leaf else [words(8, nid + "a"), words(8, nid + "b"), words(8, nid + "c")],
            hook=None if leaf else words(8, nid + "h"),
        )

    secs = []
    for s in range(1, 6):
        mids = []
        sec_lo = pos[0]
        for m in range(1, 4):
            mid_lo = pos[0]
            leaves = []
            for lf in range(1, 4):
                lid = f"s{s}m{m}l{lf}"
                add(lid, f"s{s}m{m}", 6, 60, [], (pos[0], pos[0] + 360), leaf=True)
                pos[0] += 362
                leaves.append(lid)
            add(f"s{s}m{m}", f"s{s}", 5, 45, leaves, (mid_lo, pos[0] - 2))
            mids.append(f"s{s}m{m}")
        add(f"s{s}", "hub", 4, 60, mids, (sec_lo, pos[0] - 2))
        secs.append(f"s{s}")
    end = pos[0]
    add("hub", "a3", 3, 120, secs, (0, end))
    add("a3", "a2", 2, 70, ["hub"], (0, end))
    add("a2", "a1", 1, 40, ["a3"], (0, end))
    add("a1", "root", 0, 20, ["a2"], (0, end))
    add("root", None, 0, 18, ["a1"], (0, end))
    nodes["a1"].depth, nodes["a2"].depth, nodes["a3"].depth, nodes["hub"].depth = 1, 2, 3, 4
    return Tree(id="brief", title="Brief", source_text="x" * end, source_words=45 * 60, root="root",
                nodes=nodes, max_depth=6, status="done")


def _page_of(reader: Reader):
    return set(reader.frontier())


def _open_sections(reader: Reader, *sections):
    """Open each section at the pointer (a few steps in, so it is on the page as its parts)."""
    for s in sections:
        anchor = next(n for n in reader.frontier() if _in_subtree(reader.tree, n, s))
        assert not _run_gesture(reader, anchor, [1] * 5)


def _gist_with_sections(reader: Reader):
    """Fold to the gist, then step in at the middle until the five sections are on the page, collapsed."""
    reader.seq = expansion_sequence(reader.tree, "s3")
    reader.seq_anchor = "s3"
    reader.k = 0
    reader.direction = 0
    while not {"s1", "s2", "s3", "s4", "s5"} <= _page_of(reader):
        reader.step(1)


def test_the_page_as_sam_found_it_in_then_out_then_in_over_another_section():
    """Section 3 open, the others collapsed. Zoom out over section 4, then in again over it:
    section 4 opens before anything of section 3 or the rest comes back."""
    tree = _brief_tree()
    reader = Reader(tree)
    _gist_with_sections(reader)
    _open_sections(reader, "s3")
    assert "s3" not in _page_of(reader) and "s4" in _page_of(reader)
    problems = _run_gesture(reader, "s4", [-1, -1, -1, -1] + [1] * 8)
    assert not problems, problems
    # and in again as a separate gesture over the (now collapsed) section 4
    reader2 = Reader(tree)
    _gist_with_sections(reader2)
    _open_sections(reader2, "s3")
    assert not _run_gesture(reader2, "s4", [-1, -1, -1])
    first_in = []
    reader2.begin("s4")
    for _ in range(3):
        before = reader2.shown()
        reader2.step(1)
        first_in.append(_changed(before, reader2.shown()))
    assert all(_in_subtree(tree, n, "s4") for c in first_in for n in c), first_in


def test_zoom_in_from_a_mixed_page_finishes_the_passage_before_its_neighbours():
    tree = _brief_tree()
    reader = Reader(tree)
    _gist_with_sections(reader)
    _open_sections(reader, "s3", "s2")
    reader.begin("s4")
    seen_outside = False
    for _ in range(8):
        before = reader.shown()
        reader.step(1)
        changed = _changed(before, reader.shown())
        inside = [n for n in changed if _in_subtree(tree, n, "s4")]
        outside = [n for n in changed if not _in_subtree(tree, n, "s4")]
        s4_open = any(_in_subtree(tree, n, "s4") and not tree.nodes[n].is_leaf for n in before)
        if s4_open:
            assert not outside and inside, (changed, s4_open)
        seen_outside = seen_outside or bool(outside)
    # ... and once section 4 is all paragraphs, the next steps go to its neighbours
    assert not any(not tree.nodes[n].is_leaf for n in reader.frontier() if _in_subtree(tree, n, "s4"))
    assert seen_outside


def test_the_kept_page_is_peeled_nearest_the_pointer_first():
    """Out from a page with two sections open, at a paragraph of the second: its own
    paragraphs fold before anything of the first section."""
    tree = _brief_tree()
    reader = Reader(tree)
    _gist_with_sections(reader)
    _open_sections(reader, "s1", "s4")
    anchor = next(n for n in reader.frontier() if _in_subtree(tree, n, "s4") and tree.nodes[n].is_leaf)
    reader.begin(anchor)
    for _ in range(3):
        before = reader.shown()
        reader.step(-1)
        changed = _changed(before, reader.shown())
        assert changed and all(_in_subtree(tree, n, "s4") for n in changed), changed
