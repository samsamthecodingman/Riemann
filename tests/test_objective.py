"""Reader-goal ("objective") plumbing: tree id, prompt focus, fake summariser,
server round-trip, and the front-end suggestion heuristic (run under node)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from riemann.abstraction import build, cache
from riemann.abstraction.build import OBJECTIVE_FOCUS, start_build, with_objective
from riemann.abstraction.summarise import FakeSummariser

DOC = "# Assignment 2\n\n" + " ".join(f"Submit item {i} by Friday for marks." for i in range(60))


def test_objective_in_tree_id():
    base = cache.tree_id_for("text", "m")
    assert cache.tree_id_for("text", "m", "execute") != base
    assert cache.tree_id_for("text", "m", "execute") != cache.tree_id_for("text", "m", "learn")
    assert cache.tree_id_for("text", "m", "execute") == cache.tree_id_for("text", "m", "execute")
    # No objective keeps the old id, so existing caches stay valid.
    assert cache.tree_id_for("text", "m", None) == base
    assert cache.tree_id_for("text", None, None) == cache.tree_id_for("text")


def test_schema_version_not_bumped():
    assert cache.SCHEMA_VERSION == "schema4"


def test_focus_block_in_prompt_and_faithfulness_kept():
    for key in OBJECTIVE_FOCUS:
        system = with_objective(build.SYSTEM_SUMMARY_TEMPLATE, key)
        assert f"Reader's goal: {key}" in system
        assert "Never add causation that isn't in the source." in system
        assert "never invent" in system
    do = with_objective(build.SYSTEM_SUMMARY_TEMPLATE, "execute")
    for word in ("marking criteria", "deadlines", "steps", "key_fact"):
        assert word in do
    assert with_objective(build.SYSTEM_SUMMARY_TEMPLATE, None) == build.SYSTEM_SUMMARY_TEMPLATE
    assert with_objective(build.SYSTEM_SUMMARY_TEMPLATE, "bogus") == build.SYSTEM_SUMMARY_TEMPLATE


class _Spy(FakeSummariser):
    def __init__(self):
        super().__init__()
        self.systems = []

    async def summarise(self, prompt, system):
        self.systems.append(system)
        return await super().summarise(prompt, system)


async def test_build_sends_focus_and_records_objective():
    spy = _Spy()
    builder = start_build("obj1", "T", DOC, spy, objective="execute")
    await builder.task
    assert builder.tree.objective == "execute"
    assert spy.systems and all("Reader's goal: execute" in s for s in spy.systems)


async def test_fake_summariser_reflects_objective():
    do = start_build("obj-do", "T", DOC, FakeSummariser(), objective="execute")
    await do.task
    plain = start_build("obj-none", "T", DOC, FakeSummariser())
    await plain.task
    root_do = do.tree.nodes[do.tree.root]
    root_plain = plain.tree.nodes[plain.tree.root]
    assert root_do.title.startswith("Do: ")
    assert root_do.steps  # Do fills steps
    assert not root_plain.title.startswith("Do: ")
    assert root_plain.steps == []
    assert plain.tree.objective is None


async def test_server_accepts_objective_and_rejects_unknown(monkeypatch):
    import riemann.server as server_module
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(server_module, "get_summariser", lambda model=None: FakeSummariser())
    build.BUILDS.clear()
    transport = ASGITransport(app=server_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        a = (await client.post("/api/abstract", json={"text": DOC})).json()["tree_id"]
        b = (await client.post("/api/abstract", json={"text": DOC, "objective": "execute"})).json()["tree_id"]
        assert a != b
        await build.get_builder(b).task
        tree = (await client.get(f"/api/tree/{b}")).json()
        assert tree["objective"] == "execute"
        bad = await client.post("/api/abstract", json={"text": DOC, "objective": "nope"})
        assert bad.status_code == 400
        recent = (await client.get("/api/recent")).json()
        assert any(r["id"] == b and r["objective"] == "execute" for r in recent)
    build.BUILDS.clear()


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize(
    "title,format,text,expected",
    [
        ("Assignment 2 brief", "file", "Submit via Moodle. Due 5pm Friday. Worth 30% of your marks. See rubric.", "execute"),
        ("Untitled", "paste", "This assessment task is due on 12 Oct. Submit a report. Marking criteria below.", "execute"),
        ("Re: catching up", "paste", "From: Ana\nTo: Sam\nSubject: Re: catching up\n\nHi Sam,\nPlease let me know if you can make it.\nRegards, Ana", "communicate"),
        ("Attention is all you need", "paste", "Abstract. We propose... et al. arXiv 2017", "learn"),
        ("Which laptop: pros and cons", "paste", "Compare the options and trade-offs.", "decide"),
        ("Product roadmap", "paste", "Milestones and timeline for Q4.", "plan"),
        ("Widget API reference", "url", "Documentation: parameters and returns.", "reference"),
        ("Shopping list", "paste", "milk eggs bread", None),
        # "due to" and the name "Mark" are not deadlines and marks
        ("Flooding hits the coast", "paste", "Mark Lee said delays were due to heavy rain, and the road closed due to floods.", None),
        ("A Brief History of Time", "paste", "It was long.", None),
    ],
)
def test_suggest_objective_heuristic(title, format, text, expected):
    js = Path(__file__).resolve().parent.parent / "web" / "objective.js"
    script = (
        f"const o=require({json.dumps(str(js))});"
        f"console.log(JSON.stringify(o.suggestObjective({json.dumps({'title': title, 'format': format, 'text': text})})));"
    )
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == expected
