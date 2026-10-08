"""Zoom goes where the pointer is (docs/v2-macaron-spec.md, "Zoom is local to a section").

Two layers. The first half is the *unscoped* order (a global zoom, and the order a scoped zoom
is built from): `Reader` below is the page state machine of web/app.js in miniature. The second
half (from "Scoped zoom") is the rule Sam asked for: a pointer zoom is confined to the top-level
section under the pointer, and never changes anything outside it.

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


# ---------------------------------------------------------------------------------------------
# Scoped zoom: a pointer zoom only ever changes the top-level section under the pointer
# ---------------------------------------------------------------------------------------------

def _sections_of(tree: Tree) -> list[str]:
    cur = tree.root
    while len(tree.nodes[cur].children) == 1:
        cur = tree.nodes[cur].children[0]
    return list(tree.nodes[cur].children)


def _scope_of(tree: Tree, nid: str, sections: list[str]):
    secs = set(sections)
    while nid is not None:
        if nid in secs:
            return nid
        nid = tree.nodes[nid].parent
    return None


def _shown(tree: Tree, frontier, prose) -> dict:
    """What the reader can see: which passages are on the page, and whether a skimmable
    one is shown as its summary rather than its key points."""
    out = {}
    for n in frontier:
        node = tree.nodes[n]
        skimmable = not node.is_leaf and n != tree.root and (node.key_points or node.hook)
        out[n] = bool(skimmable and n in prose)
    return out


def _page_after(tree, seq, k):
    fr = frontier_at(tree, seq, k)
    return _shown(tree, fr, prose_at(seq, k))


def _scoped_build(tree, shown: dict, anchor, scope):
    """What app.js does when a pointer gesture starts: rebuild around the page as it is,
    confined to `scope`. Returns (sequence, floor) with k == len(keep) the current page."""
    prose = {n for n, p in shown.items() if p}
    keep = _keep_for(tree, list(shown), prose)
    seq = expansion_sequence(tree, anchor, keep_expanded=keep, scope_id=scope)
    floor = sum(1 for t in keep if not _in_subtree(tree, t.lstrip("~"), scope))
    assert len(keep) <= len(seq)
    assert _page_after(tree, seq, len(keep)) == shown, "re-anchoring must not change the page"
    return seq, floor, len(keep)


def _random_page(tree, rng):
    seq = expansion_sequence(tree, rng.choice(sorted(tree.nodes)))
    k = rng.randint(0, len(seq))
    return _page_after(tree, seq, k)


def _check_scoped_walk(tree, shown, anchor, scope, what):
    """From this page, walk the scoped sequence in to its end and back out to its floor."""
    seq, floor, k0 = _scoped_build(tree, shown, anchor, scope)
    outside = {n: v for n, v in shown.items() if not _in_subtree(tree, n, scope)}

    def inside_of(page):
        return {n: v for n, v in page.items() if _in_subtree(tree, n, scope)}

    def check_step(k_from, k_to):
        a, b = _page_after(tree, seq, k_from), _page_after(tree, seq, k_to)
        assert {n: v for n, v in b.items() if not _in_subtree(tree, n, scope)} == outside, (what, k_from, k_to, "outside changed")
        assert inside_of(a) != inside_of(b), (what, k_from, k_to, "dead step")

    for k in range(k0, len(seq)):
        check_step(k, k + 1)
    # the scope is fully open at the end: every leaf of the section is showing
    end = _page_after(tree, seq, len(seq))
    assert all(tree.nodes[n].is_leaf for n in end if _in_subtree(tree, n, scope)), (what, "scope not fully open")
    for k in range(k0, floor, -1):
        check_step(k, k - 1)
    # the floor: the section is as compact as it gets (skim, not summary), and nothing outside moved
    low = _page_after(tree, seq, floor)
    assert scope in low and not low[scope], (what, "floor is not the section's skim form")
    assert {n: v for n, v in low.items() if not _in_subtree(tree, n, scope)} == outside
    return seq, floor, k0


@pytest.mark.parametrize("seed", SEEDS[:10])
@pytest.mark.parametrize("kind", KINDS)
def test_scoped_zoom_only_changes_the_section_and_every_step_shows_it(seed, kind):
    tree = make_tree(seed, kind)
    sections = _sections_of(tree)
    if not sections:
        pytest.skip("a single passage has no sections")
    rng = random.Random(f"scoped:{seed}:{kind}")
    checked = 0
    for g in range(25):
        shown = _random_page(tree, rng)
        anchor = rng.choice(sorted(shown))
        scope = _scope_of(tree, anchor, sections)
        if scope is None:
            continue
        seq, floor, k0 = _check_scoped_walk(tree, shown, anchor, scope, (seed, kind, g, anchor, scope))
        # stop part-way, then start a new gesture there (what a change of direction does)
        k = rng.randint(floor, len(seq))
        mid = _page_after(tree, seq, k)
        anchor2 = rng.choice([n for n in mid if _in_subtree(tree, n, scope)])
        _check_scoped_walk(tree, mid, anchor2, scope, (seed, kind, g, "mid", k, anchor2, scope))
        checked += 1
    assert checked, "no gesture landed in a section"


def test_scoped_zoom_on_the_brief_leaves_the_open_section_alone():
    """Section 3 open, section 4 collapsed. Zoom in over section 4: only section 4 changes, all
    the way to its paragraphs; zoom out: only section 4, down to its skim; section 3 never moves."""
    tree = _brief_tree()
    reader = Reader(tree)
    _gist_with_sections(reader)
    _open_sections(reader, "s3")
    shown = reader.shown()
    s3_before = {n: v for n, v in shown.items() if _in_subtree(tree, n, "s3")}
    assert s3_before and "s4" in shown
    anchor = "s4"
    seq, floor, k0 = _check_scoped_walk(tree, shown, anchor, "s4", "brief")
    assert len(seq) - k0 >= 3, "section 4 has real depth to open"
    assert k0 == floor, "section 4 starts at its floor: it is collapsed"
    final = _page_after(tree, seq, len(seq))
    assert {n: v for n, v in final.items() if _in_subtree(tree, n, "s3")} == s3_before
    # and at the end of the scope there is nothing further: other sections stay shut
    assert all(n in final for n in ("s1", "s2", "s5"))


def test_scoped_zoom_out_never_folds_sections_into_the_gist():
    tree = _brief_tree()
    reader = Reader(tree)
    _gist_with_sections(reader)
    _open_sections(reader, "s3", "s4")
    shown = reader.shown()
    anchor = next(n for n in shown if _in_subtree(tree, n, "s4"))
    seq, floor, k0 = _scoped_build(tree, shown, anchor, "s4")
    low = _page_after(tree, seq, floor)
    assert "s4" in low and not low["s4"]
    assert all(s in low for s in ("s1", "s2", "s5"))
    assert {n for n in low if _in_subtree(tree, n, "s3")} == {n for n in shown if _in_subtree(tree, n, "s3")}


def test_scope_none_is_the_unscoped_order():
    tree = make_tree(3, "balanced")
    for anchor in sorted(tree.nodes)[:6]:
        assert expansion_sequence(tree, anchor, scope_id=None) == expansion_sequence(tree, anchor)
