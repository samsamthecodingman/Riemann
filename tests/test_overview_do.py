"""The "Do it" overview data: start_here, size_of_job, deadline, actions, and the act-first order."""
import datetime
import json
from pathlib import Path

import pytest

from riemann.abstraction import build, checks
from riemann.abstraction.build import _clean_overview, _sort_essentials, start_build
from riemann.abstraction.model import Essential, Node, Tree
from riemann.abstraction.summarise import FakeSummariser

FIX = Path(__file__).parent / "fixtures"
TODAY = datetime.date(2025, 10, 1)

BRIEF = (
    "Submit the report as a single PDF through Moodle. The report is due at 5 pm on Friday 14 November 2025.\n\n"
    "The word limit is 1,800 words, plus a notebook and 3 sites of data. Start by downloading the dataset from Moodle."
)


def _tree(text=BRIEF, genre="assignment", objective=None) -> Tree:
    parts = text.split("\n\n")
    nodes = {f"l{i}": Node(id=f"l{i}", depth=1, text=t, source_span=(0, len(t)), is_leaf=True, words=len(t.split())) for i, t in enumerate(parts)}
    root = Node(id="root", depth=0, text="r", source_span=(0, 1), words=1, children=list(nodes))
    nodes["root"] = root
    return Tree(id="t", title="T", source_text=text, source_words=len(text.split()), root="root", nodes=nodes, max_depth=1, status="done", genre=genre, objective=objective)


def _ov(extra, tree=None, essentials=None):
    raw = {"doc_title": "Brief", "doc_kind": "Assignment brief", "what_it_is": "This is a brief.", "essentials": essentials or []}
    raw.update(extra)
    return _clean_overview(raw, tree or _tree(), today=TODAY)


# --- start_here -----------------------------------------------------------------------------

def test_start_here_is_kept_with_its_cites_and_capped_at_25_words():
    ov = _ov({"start_here": {"text": "Download the dataset from Moodle", "cites": ["l1"]}})
    assert ov.start_here.text == "Download the dataset from Moodle" and ov.start_here.cites == ["l1"]
    long = " ".join(["download"] * 40)
    assert len(_ov({"start_here": {"text": long, "cites": ["l1"]}}).start_here.text.split()) == 25


@pytest.mark.parametrize(
    "bad",
    [
        {"text": "Download the dataset", "cites": []},  # no cites
        {"text": "Download the dataset", "cites": ["nope"]},
        {"text": "Open 7 files today", "cites": ["l1"]},  # 7 is not in the leaf
        {"text": "Kangaroos jump fences nightly", "cites": ["l1"]},  # shares nothing
        {"text": "Email the tutor on Tuesday", "cites": ["l0"]},  # Tuesday is not in the leaf
        {"text": "", "cites": ["l1"]},
        "Download the dataset",
        None,
    ],
)
def test_start_here_failures_become_none(bad):
    assert _ov({"start_here": bad}).start_here is None


def test_do_it_fields_only_appear_for_task_like_documents():
    paper = _tree(genre="paper")
    ov = _ov({"start_here": {"text": "Download the dataset from Moodle", "cites": ["l1"]}}, tree=paper)
    assert ov.start_here is None and ov.deadline is None and ov.size_of_job is None
    goal = _tree(genre="paper", objective="execute")
    assert _ov({"start_here": {"text": "Download the dataset from Moodle", "cites": ["l1"]}}, tree=goal).start_here is not None
    assert _ov({"start_here": {"text": "Download the dataset from Moodle", "cites": ["l1"]}}, tree=_tree(genre=None, objective="plan")).start_here is not None


# --- size_of_job ----------------------------------------------------------------------------

def test_size_of_job_needs_a_basis_from_the_source_and_keeps_its_own_estimate():
    ok = _ov({"size_of_job": {"text": "About 3 sessions of 2 hours", "basis": "a 1,800 words report and 3 sites", "cites": ["l1"]}})
    # the estimate's own numbers (3, 2) are the model's, so only the basis is matched against the source
    assert ok.size_of_job.text == "About 3 sessions of 2 hours" and ok.size_of_job.basis.startswith("a 1,800") and ok.size_of_job.cites == ["l1"]


@pytest.mark.parametrize(
    "bad",
    [
        {"text": "About 3 sessions", "basis": "a 2,500 words report", "cites": ["l1"]},  # 2,500 is not in the source
        {"text": "About 3 sessions", "basis": "", "cites": ["l1"]},
        {"text": "About 3 sessions", "basis": "a 1,800 words report", "cites": []},
        {"text": "", "basis": "a 1,800 words report", "cites": ["l1"]},
        {"text": "About 3 sessions", "cites": ["l1"]},
        "about 3 sessions",
    ],
)
def test_size_of_job_failures_become_none(bad):
    assert _ov({"size_of_job": bad}).size_of_job is None


def test_size_of_job_estimate_is_capped_at_20_words():
    est = " ".join(["session"] * 30)
    ov = _ov({"size_of_job": {"text": est, "basis": "a 1,800 words report", "cites": ["l1"]}})
    assert len(ov.size_of_job.text.split()) == 20


# --- deadline -------------------------------------------------------------------------------

def _dl(**kw):
    d = {"iso": "2025-11-14", "time": "17:00", "label": "Report due", "cites": ["l0"]}
    d.update(kw)
    return _ov({"deadline": d}).deadline


def test_deadline_with_year_time_and_label():
    d = _dl()
    assert (d.iso, d.time, d.label, d.cites, d.year_inferred) == ("2025-11-14", "17:00", "Report due", ["l0"], False)


@pytest.mark.parametrize(
    "kw",
    [
        {"iso": "2025-11-15"},  # 15 is not in the cited leaf
        {"iso": "2025-12-14"},  # December is not in the cited leaf
        {"iso": "2025-02-30"},  # not a date
        {"iso": "tomorrow"},
        {"iso": "2026-11-14"},  # the source says 2025
        {"cites": []},
        {"cites": ["l1"]},  # the date is not in that leaf
        {"label": "Due Monday"},  # weekday not in the cited leaf
        {"label": ""},
    ],
)
def test_deadline_that_the_source_does_not_support_is_dropped(kw):
    assert _dl(**kw) is None


def test_unverifiable_time_is_dropped_but_the_deadline_stays():
    d = _dl(time="09:30")
    assert d is not None and d.time is None
    assert _dl(time="not a time").time is None
    assert _dl(time="17:00").time == "17:00"


def test_a_source_with_no_year_marks_the_year_as_inferred():
    tree = _tree("The report is due at 5 pm on Friday 14 November.\n\nSubmit it on Moodle.")
    d = _ov({"deadline": {"iso": "2025-11-14", "time": "17:00", "label": "Report due", "cites": ["l0"]}}, tree=tree).deadline
    assert d.iso == "2025-11-14" and d.year_inferred is True


def test_a_year_less_iso_becomes_the_next_occurrence():
    tree = _tree("The report is due at 5 pm on Friday 14 November.\n\nSubmit it on Moodle.")
    for iso in ("11-14", "----11-14", "????-11-14"):
        d = _ov({"deadline": {"iso": iso, "label": "Report due", "cites": ["l0"]}}, tree=tree).deadline
        assert (d.iso, d.year_inferred) == ("2025-11-14", True)
    past = _clean_overview({"doc_title": "B", "doc_kind": "K", "what_it_is": "This is K.", "deadline": {"iso": "11-14", "label": "x", "cites": ["l0"]}}, tree, today=datetime.date(2025, 12, 1))
    assert past.deadline.iso == "2026-11-14"


def test_a_year_less_iso_takes_the_year_the_source_states():
    d = _dl(iso="11-14")
    assert (d.iso, d.year_inferred) == ("2025-11-14", False)


def test_numeric_source_dates_and_other_time_forms():
    tree = _tree("Due 14/11/2025 by 17:00.\n\nThen submit.")
    d = _ov({"deadline": {"iso": "2025-11-14", "time": "17:00", "label": "Due", "cites": ["l0"]}}, tree=tree).deadline
    assert d is not None and d.time == "17:00"
    for text, hhmm in (("by 5 pm", "17:00"), ("at 5:30pm", "17:30"), ("by midnight", "00:00"), ("at noon", "12:00"), ("23:59", "23:59"), ("11.59 pm", "23:59")):
        assert checks.time_in_source(hhmm, text), text
    for text, hhmm in (("by 5 pm", "05:00"), ("at 6 pm", "17:00"), ("nothing", "09:00")):
        assert not checks.time_in_source(hhmm, text), text


# --- act-first order ------------------------------------------------------------------------

def _e(label):
    return Essential(label=label, value="v", cites=[])


def test_essentials_are_sorted_deadline_then_deliverables_then_first_step_then_reference():
    labels = ["Weight", "Assessed on", "Submit how", "Deliverables", "First step", "Due", "Not allowed"]
    out = [e.label for e in _sort_essentials([_e(x) for x in labels])]
    assert out == ["Due", "Deliverables", "First step", "Weight", "Assessed on", "Submit how", "Not allowed"]


def test_sort_is_stable_and_leaves_other_genres_alone():
    labels = ["Question", "Method and sample", "Main result", "Limits"]
    assert [e.label for e in _sort_essentials([_e(x) for x in labels])] == labels
    assert [e.label for e in _sort_essentials([_e(x) for x in ["Reply by", "The ask", "From"]])] == ["Reply by", "The ask", "From"]
    assert [e.label for e in _sort_essentials([_e(x) for x in ["From", "Reply by", "The ask"]])] == ["Reply by", "The ask", "From"]
    for label in ("When", "Date of meeting"):
        assert [e.label for e in _sort_essentials([_e("Who"), _e(label)])] == ["Who", label]


def test_clean_overview_applies_the_sort():
    ess = [
        {"label": "Weight", "value": "worth a lot", "cites": []},
        {"label": "Due", "value": "not stated", "cites": []},
        {"label": "Deliverables", "value": "not stated", "cites": []},
    ]
    assert [e.label for e in _ov({}, essentials=ess).essentials] == ["Due", "Deliverables", "Weight"]


# --- actions --------------------------------------------------------------------------------

MEETING = (
    "Tom Becker to finish the data reload by Friday 24 October.\n\n"
    "Aisha Rahman to chase Dr Malik about the ethics check by Wednesday 15 October. Luis Ortega to phone the ethics office on Thursday 16 October.\n\n"
    "Priya Nair to send the correction note to dashboard users on the day the dashboard is republished."
)


def _meeting_ov(actions):
    tree = _tree(MEETING, genre="meeting")
    return _ov({"actions": actions}, tree=tree).actions


def A(who, what, due=None, due_iso=None, cites=("l0",)):
    return {"who": who, "what": what, "due": due, "due_iso": due_iso, "cites": list(cites)}


def test_actions_sort_earliest_first_and_undated_last():
    acts = _meeting_ov(
        [
            A("Priya Nair", "send the correction note to dashboard users", cites=["l2"]),
            A("Tom Becker", "finish the data reload", "Friday 24 October", "2025-10-24", ["l0"]),
            A("Luis Ortega", "phone the ethics office", "Thursday 16 October", "2025-10-16", ["l1"]),
            A("Aisha Rahman", "chase Dr Malik about the ethics check", "Wednesday 15 October", "2025-10-15", ["l1"]),
        ]
    )
    assert [a.who for a in acts] == ["Aisha Rahman", "Luis Ortega", "Tom Becker", "Priya Nair"]
    assert acts[0].due == "Wednesday 15 October" and acts[0].due_iso == "2025-10-15" and acts[-1].due is None and acts[-1].due_iso is None
    assert acts[0].cites == ["l1"]


def test_actions_only_for_meetings():
    tree = _tree(MEETING, genre="assignment")
    assert _ov({"actions": [A("Tom Becker", "finish the data reload")]}, tree=tree).actions == []


@pytest.mark.parametrize(
    "bad",
    [
        A("Tom Becker", "finish the data reload", cites=[]),  # no cites
        A("Zed Quill", "finish the data reload"),  # who is not in the cited leaf
        A("Tom Becker", "paint the shed with kangaroos"),  # what shares nothing
        A("Tom Becker", "finish the data reload", "Monday 24 October", "2025-10-24"),  # weekday not in the leaf
        A("Tom Becker", "finish the data reload", "Friday 25 October", "2025-10-25"),  # day not in the leaf
        A("Tom Becker", "finish the data reload", "Friday 24 November", "2025-11-24"),  # month not in the leaf
        {"who": "Tom Becker", "cites": ["l0"]},
        "Tom to finish",
    ],
)
def test_actions_the_source_does_not_support_are_dropped(bad):
    good = A("Tom Becker", "finish the data reload", "Friday 24 October", "2025-10-24")
    assert [a.who for a in _meeting_ov([bad, good])] == ["Tom Becker"]
    assert len(_meeting_ov([bad, good])) == 1


def test_an_unsupported_due_iso_is_dropped_but_the_action_stays():
    acts = _meeting_ov([A("Tom Becker", "finish the data reload", "Friday 24 October", "2025-10-30")])
    assert len(acts) == 1 and acts[0].due == "Friday 24 October" and acts[0].due_iso is None


def test_a_year_less_action_date_gets_an_inferred_year():
    acts = _meeting_ov([A("Tom Becker", "finish the data reload", "Friday 24 October", "10-24")])
    assert acts[0].due_iso == "2025-10-24" and acts[0].year_inferred is True


def test_at_most_12_actions_and_no_duplicates():
    acts = _meeting_ov([A("Tom Becker", "finish the data reload")] * 3 + [A("Tom Becker", f"finish the data reload item {i}") for i in range(20)])
    assert len(acts) <= 12 and len({(a.who, a.what) for a in acts}) == len(acts)


# --- the fake summariser emits examples through a real build ---------------------------------

async def _build(name, title, tid, objective=None):
    b = start_build(tid, title, (FIX / name).read_text(), FakeSummariser(), objective=objective)
    await b.task
    assert b.tree.status == "done", b.history[-1]
    return b.tree


async def test_fake_build_of_the_assignment_brief_has_the_do_it_fields():
    tree = await _build("assignment_brief.md", "GEO2105 Assignment 2", "do-assign")
    ov = tree.overview
    assert tree.genre == "assignment"
    assert ov.start_here and len(ov.start_here.text.split()) <= 25 and ov.start_here.cites
    assert ov.size_of_job and ov.size_of_job.basis and len(ov.size_of_job.text.split()) <= 20
    assert ov.deadline and ov.deadline.iso == "2025-11-14" and ov.deadline.time == "17:00" and ov.deadline.year_inferred is False
    assert ov.actions == []


async def test_fake_build_of_the_meeting_notes_has_sorted_actions():
    tree = await _build("meeting.md", "Project steering meeting", "do-meet")
    acts = tree.overview.actions
    assert tree.genre == "meeting" and len(acts) >= 4
    dated = [a.due_iso for a in acts if a.due_iso]
    assert dated == sorted(dated) and [a.due_iso is None for a in acts] == sorted(a.due_iso is None for a in acts)
    assert all(a.who and a.what and a.cites for a in acts)
    assert tree.overview.start_here is not None  # meeting notes are task-like too


async def test_fake_build_of_a_paper_has_no_do_it_fields():
    tree = await _build("paper.md", "Walks and sleep", "do-paper")
    ov = tree.overview
    assert tree.genre == "paper" and ov.start_here is None and ov.size_of_job is None and ov.deadline is None and ov.actions == []


async def test_the_execute_goal_makes_any_document_task_like():
    tree = await _build("paper.md", "Walks and sleep", "do-paper-exec", objective="execute")
    assert tree.overview.start_here is not None
