"""Genre-aware summarisation: detection, prompts, and how the build uses them."""
import asyncio
import json
from pathlib import Path

import pytest

from riemann.abstraction import build, cache
from riemann.abstraction.build import start_build
from riemann.abstraction.genre import GENRE_ESSENTIALS, GENRE_FOCUS, GENRES, detect_genre, is_task_like, valid_genre
from riemann.abstraction.summarise import FakeSummariser

FIX = Path(__file__).parent / "fixtures"


def _doc(name: str) -> str:
    return (FIX / name).read_text()


# --- detection ------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,genre",
    [("assignment_brief.md", "assignment"), ("paper.md", "paper"), ("meeting.md", "meeting")],
)
def test_fixture_documents_are_detected_strongly(name, genre):
    text = _doc(name)
    title = text.splitlines()[0].lstrip("# ")
    assert detect_genre(title, text) == (genre, True)


def test_email_headers_are_decisive():
    text = "From: Dana <d@example.org>\nTo: Alex <s@example.com>\nSubject: Start date\n\nHi Alex, please confirm your start date by Friday."
    assert detect_genre("Start date", text) == ("email", True)


def test_legal_technical_and_news_samples():
    legal = (
        "# Acceptable Use Policy\n\nThis policy applies to all employees. The Company shall not be liable. Staff must not share passwords "
        "unless authorised in writing. Pursuant to section 4.2, a breach of this agreement may lead to termination. "
        "The governing law is that of Victoria."
    )
    assert detect_genre("Acceptable Use Policy", legal)[0] == "legal"
    tech = "# widgetctl\n\n## Installation\n\n```\npip install widgetctl\n```\n\n## Usage\n\nRun `widgetctl --verbose init`.\n\n## Configuration\n\nOptions: --port, --host."
    assert detect_genre("widgetctl", tech)[0] == "technical"
    news = (
        "LONDON (Reuters) - The government said on Tuesday that it would delay the vote, according to officials. "
        "A spokesperson said the decision followed talks. Police said no one was hurt."
    )
    assert detect_genre("Vote delayed", news)[0] == "news"


def test_plain_prose_has_no_detected_genre():
    assert detect_genre("Photosynthesis", "Plants turn light into sugar. " * 30) == (None, False)


def test_valid_genre_and_task_like():
    assert valid_genre("Meeting notes") == "meeting" and valid_genre("research paper") == "paper"
    assert valid_genre("banana") is None and valid_genre(None) is None and valid_genre({"x": 1}) is None
    assert set(GENRES) == {"assignment", "paper", "news", "email", "meeting", "legal", "technical", "article", "other"}
    assert is_task_like("assignment", None) and is_task_like("meeting", None) and is_task_like("paper", "execute")
    assert is_task_like(None, "plan") and not is_task_like("paper", None) and not is_task_like("email", "communicate")


# --- prompts ----------------------------------------------------------------------------------

def test_every_genre_but_other_has_a_focus_block_and_essentials_hint():
    assert set(GENRE_FOCUS) == set(GENRES) - {"other"} == set(GENRE_ESSENTIALS)
    for key, block in GENRE_FOCUS.items():
        assert block.startswith(f"Document genre: {key}\n")
        assert "never invent" in block  # the faithfulness rule is restated, as in the goal blocks


def test_genre_blocks_carry_what_the_review_asked_for():
    f = GENRE_FOCUS
    assert "command word" in f["assignment"] and "due date" in f["assignment"]
    assert "method and sample" in f["paper"] and "limits" in f["paper"]
    assert "inverted pyramid" in f["news"] and "attribution" in f["news"]
    assert "ask first" in f["email"] and "decided" in f["email"]
    assert "who will" in f["meeting"] and "decisions" in f["meeting"]
    assert "must" in f["legal"] and "unless" in f["legal"] and "Never soften" in f["legal"]
    assert "how-to" in f["technical"] and "order" in f["technical"]
    assert "Question" in GENRE_ESSENTIALS["paper"] and "Main result" in GENRE_ESSENTIALS["paper"]
    assert "Who" in GENRE_ESSENTIALS["news"] and "Reply by" in GENRE_ESSENTIALS["email"]


def test_with_focus_combines_genre_and_goal_and_degrades():
    base = "BASE"
    both = build.with_focus(base, "execute", "assignment")
    assert both.index("Document genre: assignment") < both.index("Reader's goal: execute")
    assert build.with_focus(base, None, None) == base
    assert build.with_focus(base, "learn", None) == build.with_objective(base, "learn")
    assert build.with_focus(base, None, "other") == base and build.with_focus(base, None, "nonsense") == base
    assert build.with_focus(base, "bogus", "paper").endswith(GENRE_FOCUS["paper"])


# --- the build -------------------------------------------------------------------------------

class Recording(FakeSummariser):
    def __init__(self, genre_reply=None, gist_delay=0.0):
        super().__init__()
        self.calls: list[tuple[str, str]] = []
        self.genre_reply = genre_reply
        self.gist_delay = gist_delay

    async def summarise(self, prompt, system):
        self.calls.append((prompt, system))
        if self.gist_delay and system.startswith("You are producing a fast provisional"):
            await asyncio.sleep(self.gist_delay)
        raw = await super().summarise(prompt, system)
        if system.startswith("You are producing a fast provisional") and self.genre_reply is not None:
            data = json.loads(raw)
            data["genre"] = self.genre_reply
            raw = json.dumps(data)
        return raw


async def _build(text, title, tid, summariser, objective=None):
    b = start_build(tid, title, text, summariser, objective=objective)
    await b.task
    assert b.tree.status == "done", b.history[-1]
    return b


async def test_a_strong_heuristic_genre_steers_every_prompt_and_is_stored():
    rec = Recording()
    b = await _build(_doc("assignment_brief.md"), "GEO2105 Assignment 2", "g-assign", rec)
    assert b.tree.genre == "assignment"
    node_calls = [s for p, s in rec.calls if "Children to summarise" in p]
    assert node_calls and all("Document genre: assignment" in s for s in node_calls)
    root_calls = [s for p, s in rec.calls if "Children to summarise" in p and "ROOT of the tree" in s]
    assert root_calls and all("Document genre: assignment" in s for s in root_calls)
    overview = [s for p, s in rec.calls if "Task: overview" in p]
    assert len(overview) == 1 and "Document genre: assignment" in overview[0]
    gist = [s for p, s in rec.calls if s.startswith("You are producing a fast provisional")]
    assert len(gist) == 1 and "genre" in gist[0]


async def test_the_goal_still_steers_alongside_the_genre():
    rec = Recording()
    await _build(_doc("paper.md"), "Walks and sleep", "g-paper-goal", rec, objective="decide")
    overview = [s for p, s in rec.calls if "Task: overview" in p][0]
    assert overview.index("Document genre: paper") < overview.index("Reader's goal: decide")


async def test_a_weak_heuristic_uses_the_model_genre_for_the_root_and_later_layers():
    rec = Recording(genre_reply="paper", gist_delay=0.3)
    text = "Plants turn light into sugar in the leaf. " * 400  # nothing for the heuristics
    b = await _build(text, "Plants", "g-weak", rec)
    assert b.tree.genre == "paper"
    root_calls = [s for p, s in rec.calls if "Children to summarise" in p and "ROOT of the tree" in s]
    assert root_calls and all("Document genre: paper" in s for s in root_calls)
    assert "Document genre: paper" in [s for p, s in rec.calls if "Task: overview" in p][0]
    # the first layer does not wait for the gist call, so it has no block; layers after it do
    node_calls = [s for p, s in rec.calls if "Children to summarise" in p]
    with_block = [s for s in node_calls if "Document genre: paper" in s]
    assert 0 < len(with_block) < len(node_calls)


async def test_a_strong_heuristic_beats_a_disagreeing_model():
    b = await _build(_doc("meeting.md"), "Project steering meeting", "g-strong", Recording(genre_reply="news"))
    assert b.tree.genre == "meeting"


async def test_an_invalid_or_missing_model_genre_falls_back_to_other():
    text = "Plants turn light into sugar in the leaf. " * 400
    assert (await _build(text, "Plants", "g-bad", Recording(genre_reply="banana"))).tree.genre == "other"
    assert (await _build(text, "Plants", "g-none", Recording())).tree.genre == "other"
    assert (await _build(text, "Plants", "g-obj", Recording(genre_reply={"x": 1}))).tree.genre == "other"


async def test_tiny_documents_still_get_a_genre():
    b = start_build("g-tiny", "Note", "Just a short note.", FakeSummariser())
    await b.task
    assert b.tree.genre == "other"


async def test_genre_is_saved_with_the_tree_and_old_trees_still_load():
    b = await _build(_doc("paper.md"), "Walks and sleep", "g-save", FakeSummariser())
    assert cache.load_tree("g-save").genre == "paper"
    raw = json.loads(cache.path_for("g-save").read_text())
    raw.pop("genre")
    cache.path_for("g-save").write_text(json.dumps(raw))
    assert cache.load_tree("g-save").genre is None


async def test_overview_essentials_hint_follows_the_genre():
    rec = Recording()
    await _build(_doc("paper.md"), "Walks and sleep", "g-ess", rec)
    overview = [s for p, s in rec.calls if "Task: overview" in p][0]
    assert GENRE_ESSENTIALS["paper"] in overview


async def test_backfill_detects_genre_for_an_old_tree():
    b = await _build(_doc("meeting.md"), "Project steering meeting", "g-old", FakeSummariser())
    tree = b.tree
    tree.genre, tree.overview = None, None
    rec = Recording()
    ov = await build.generate_overview(tree, rec)
    assert tree.genre == "meeting" and ov is not None
    system = [s for p, s in rec.calls if "Task: overview" in p][0]
    assert "Document genre: meeting" in system
