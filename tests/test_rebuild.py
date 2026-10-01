"""Rebuild a tree under the current schema, and survive a server restart mid-build."""
import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from riemann.abstraction import build, cache
from riemann.abstraction.summarise import FakeSummariser, ModelError

DOC = "# Notes\n\n" + "\n\n".join(f"## Part {i}\n\n" + ("The tide moved sand along the beach while the team measured it. " * 12) for i in range(4))


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    import riemann.server as server

    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "get_summariser", lambda model=None: FakeSummariser())
    build.BUILDS.clear()
    yield
    build.BUILDS.clear()


async def _client():
    import riemann.server as server

    return AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")


async def _build_via_api(client, text=DOC, **extra):
    r = await client.post("/api/abstract", json={"text": text, **extra})
    tid = r.json()["tree_id"]
    await build.get_builder(tid).task
    return tid


def _move_to_old_namespace(tid):
    """Make a tree look like it was built under an older schema (read-only fallback)."""
    src = cache.path_for(tid)
    old = src.parent.parent / "r3-leaf120-gist25-stop34-schema4"
    old.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text())
    data.pop("genre", None)
    (old / src.name).write_text(json.dumps(data))
    src.unlink()
    build.BUILDS.clear()  # as after a restart


# --- rebuild --------------------------------------------------------------------------------

async def test_rebuild_starts_a_fresh_build_from_the_stored_source_and_keeps_the_old_tree():
    async with await _client() as c:
        old_id = await _build_via_api(c, objective="learn", model="fake-model")
        _move_to_old_namespace(old_id)
        assert not cache.exists(old_id) and cache.load_tree(old_id) is not None  # opens read-only, as before

        r = await c.post(f"/api/tree/{old_id}/rebuild")
        assert r.status_code == 200
        body = r.json()
        new_id = body["tree_id"]
        assert body["cached"] is False
        await build.get_builder(new_id).task

        new = cache.load_tree(new_id)
        old = cache.load_tree(old_id)
        assert old is not None and old.id == old_id  # the old tree stays
        assert new_id == cache.tree_id_for(old.source_text, "fake-model", "learn")  # same text, model and goal
        assert new.model == "fake-model" and new.objective == "learn" and new.genre is not None
        assert cache.exists(new_id)  # under the current schema


async def test_rebuild_renormalises_the_stored_source(monkeypatch):
    async with await _client() as c:
        tid = await _build_via_api(c)
        tree = cache.load_tree(tid)
        tree.source_text = "Subject: Re: x\nFrom: a@b.c\n\nThe new reply says the report is due Friday and needs the appendix attached.\n\nOn Tue, 14 Oct 2025 at 09:15, Sam <s@x.org> wrote:\n> old quoted text here that should go away\n"
        cache.path_for(tid).write_text(tree.model_dump_json())
        build.BUILDS.clear()  # as after a restart
        r = await c.post(f"/api/tree/{tid}/rebuild")
        new_id = r.json()["tree_id"]
        await build.get_builder(new_id).task
        text = cache.load_tree(new_id).source_text
        assert "old quoted text" not in text and "due Friday" in text


async def test_rebuild_of_a_tree_already_current_does_not_rebuild_it():
    async with await _client() as c:
        tid = await _build_via_api(c, model="fake-model")
        r = await c.post(f"/api/tree/{tid}/rebuild")
        assert r.json() == {"tree_id": r.json()["tree_id"], "cached": True}
        assert r.json()["tree_id"] == tid or cache.exists(r.json()["tree_id"])


async def test_rebuild_unknown_or_unsafe_ids():
    async with await _client() as c:
        assert (await c.post("/api/tree/0123456789abcdef/rebuild")).status_code == 404
        assert (await c.post("/api/tree/bad.id/rebuild")).status_code == 404


async def test_rebuild_while_the_new_build_is_running_does_not_start_a_second_one():
    async with await _client() as c:
        old_id = await _build_via_api(c, model="fake-model")
        _move_to_old_namespace(old_id)
        a = (await c.post(f"/api/tree/{old_id}/rebuild")).json()
        first = build.get_builder(a["tree_id"])
        b = (await c.post(f"/api/tree/{old_id}/rebuild")).json()
        assert a["tree_id"] == b["tree_id"] and build.get_builder(b["tree_id"]) is first
        await first.task


async def test_rebuild_uses_the_default_model_for_a_tree_without_one(monkeypatch):
    async with await _client() as c:
        tid = await _build_via_api(c)
        tree = cache.load_tree(tid)
        tree.model = None
        cache.path_for(tid).write_text(tree.model_dump_json())
        build.BUILDS.clear()
        _move_to_old_namespace(tid)
        r = await c.post(f"/api/tree/{tid}/rebuild")
        await build.get_builder(r.json()["tree_id"]).task
        from riemann.abstraction.summarise import default_model

        assert cache.load_tree(r.json()["tree_id"]).model == default_model()


# --- the "building" marker ------------------------------------------------------------------

class Slow(FakeSummariser):
    def __init__(self):
        super().__init__()
        self.gate = asyncio.Event()

    async def summarise(self, prompt, system):
        await self.gate.wait()
        return await super().summarise(prompt, system)


async def test_a_marker_is_written_at_build_start_and_removed_when_done():
    slow = Slow()
    b = build.start_build("mark1", "Notes", DOC, slow, objective="learn")
    b.tree.model = "fake-model"
    marker = cache.load_marker("mark1")
    assert marker["source_text"] == DOC and marker["title"] == "Notes" and marker["objective"] == "learn"
    slow.gate.set()
    await b.task
    assert b.tree.status == "done" and cache.load_marker("mark1") is None


async def test_the_marker_records_the_model_even_though_it_is_set_after_start():
    import riemann.server as server

    async with await _client() as c:
        slow = Slow()
        server.get_summariser = lambda model=None: slow
        r = await c.post("/api/abstract", json={"text": DOC, "model": "fake-model"})
        tid = r.json()["tree_id"]
        assert cache.load_marker(tid)["model"] == "fake-model"
        slow.gate.set()
        await build.get_builder(tid).task


async def test_the_marker_is_removed_when_the_build_fails():
    class Boom(FakeSummariser):
        async def summarise(self, prompt, system):
            raise ModelError("nope")

    b = build.start_build("mark2", "Notes", DOC, Boom())
    await b.task
    assert b.tree.status == "error" and cache.load_marker("mark2") is None


async def test_a_cancelled_build_leaves_its_marker_behind():
    slow = Slow()
    b = build.start_build("mark3", "Notes", DOC, slow)
    await asyncio.sleep(0.05)
    b.task.cancel()
    await asyncio.gather(b.task, return_exceptions=True)
    assert cache.load_marker("mark3") is not None


# --- interrupted builds ---------------------------------------------------------------------

def _orphan_marker(tid="abcdef0123456789", model="fake-model", objective="plan"):
    cache.save_marker(tid, title="Notes", source_text=DOC, objective=objective, model=model)
    return tid


async def test_a_tree_with_a_marker_and_no_live_builder_is_interrupted():
    tid = _orphan_marker()
    async with await _client() as c:
        r = await c.get(f"/api/tree/{tid}")
        assert r.status_code == 409
        body = r.json()
        assert body["state"] == "interrupted" and body["tree_id"] == tid and body["title"] == "Notes" and body["message"]
        assert (await c.get(f"/api/tree/{tid}/events")).status_code == 409


async def test_a_live_builder_or_a_cached_tree_wins_over_the_marker():
    async with await _client() as c:
        tid = await _build_via_api(c)
        cache.save_marker(tid, title="Notes", source_text=DOC, objective=None, model="m")  # stale marker
        r = await c.get(f"/api/tree/{tid}")
        assert r.status_code == 200 and r.json()["status"] == "done"
        build.BUILDS.clear()
        r = await c.get(f"/api/tree/{tid}")
        assert r.status_code == 200
        assert cache.load_marker(tid) is None  # the stale marker was swept


async def test_resume_build_restarts_from_the_marker_with_the_same_settings():
    tid = _orphan_marker()
    async with await _client() as c:
        r = await c.post(f"/api/tree/{tid}/resume-build")
        assert r.status_code == 200 and r.json() == {"tree_id": tid}
        b = build.get_builder(tid)
        assert b.tree.objective == "plan" and b.tree.model == "fake-model" and b.tree.source_text == DOC
        again = await c.post(f"/api/tree/{tid}/resume-build")  # a double press does not start a second build
        assert build.get_builder(tid) is b and again.json() == {"tree_id": tid}
        await b.task
        assert cache.exists(tid) and cache.load_marker(tid) is None
        assert (await c.get(f"/api/tree/{tid}")).json()["status"] == "done"


async def test_resume_build_without_a_marker_is_404_and_a_finished_tree_is_a_no_op():
    async with await _client() as c:
        assert (await c.post("/api/tree/0123456789abcdef/resume-build")).status_code == 404
        tid = await _build_via_api(c)
        assert (await c.post(f"/api/tree/{tid}/resume-build")).json() == {"tree_id": tid}


async def test_posting_the_same_document_again_after_a_restart_just_builds_it():
    async with await _client() as c:
        r = await c.post("/api/abstract", json={"text": DOC})
        tid = r.json()["tree_id"]
        await build.get_builder(tid).task
        cache.path_for(tid).unlink()
        build.BUILDS.clear()
        cache.save_marker(tid, title="Notes", source_text=DOC, objective=None, model="x")
        r2 = await c.post("/api/abstract", json={"text": DOC})
        assert r2.json() == {"tree_id": tid, "cached": False}
        await build.get_builder(tid).task


def test_marker_ids_are_never_paths():
    with pytest.raises(ValueError):
        cache.save_marker("../x", title="t", source_text="s", objective=None, model=None)
    assert cache.load_marker("../x") is None
