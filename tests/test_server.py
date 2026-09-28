import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from riemann import events as events_module
from riemann.abstraction import build, cache
from riemann.abstraction.summarise import FakeSummariser


@pytest.fixture(autouse=True)
def _riemann_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    yield


@pytest.fixture(autouse=True)
def _fake_summariser(monkeypatch):
    import riemann.server as server_module

    monkeypatch.setattr(server_module, "get_summariser", lambda: FakeSummariser())
    yield


@pytest.fixture(autouse=True)
def _clear_builds():
    build.BUILDS.clear()
    yield
    build.BUILDS.clear()


async def _client():
    import riemann.server as server_module

    transport = ASGITransport(app=server_module.app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _wait_for_done(tree_id: str, timeout: float = 10.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        builder = build.get_builder(tree_id)
        if builder is not None and builder.task is not None:
            await builder.task
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("build did not start/finish in time")


async def test_post_text_returns_tree_id_and_builds():
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "# Doc\n\n" + "word " * 200})
        assert resp.status_code == 200
        data = resp.json()
        assert "tree_id" in data
        assert data["cached"] is False

        await _wait_for_done(data["tree_id"])

        tree_resp = await client.get(f"/api/tree/{data['tree_id']}")
        assert tree_resp.status_code == 200
        tree = tree_resp.json()
        assert tree["status"] == "done"


async def test_sse_completes_with_done():
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "# Doc\n\n" + "word " * 200})
        tree_id = resp.json()["tree_id"]

        events_seen = []
        async with client.stream("GET", f"/api/tree/{tree_id}/events") as stream:
            event_name = None
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and event_name:
                    events_seen.append(event_name)
                    if event_name == "done":
                        break
                    event_name = None

        assert "done" in events_seen


async def test_post_events_appends_to_log():
    async with await _client() as client:
        payload = [{"type": "open", "tree_id": "abc", "resumed": False}]
        resp = await client.post("/api/events", json=payload)
        assert resp.status_code == 204

    log_path = events_module.log_path()
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["type"] == "open"
    assert "ts" in record


async def test_caching_second_post_is_cached():
    text = "# Doc\n\n" + "word " * 200
    async with await _client() as client:
        resp1 = await client.post("/api/abstract", json={"text": text})
        tree_id = resp1.json()["tree_id"]
        assert resp1.json()["cached"] is False
        await _wait_for_done(tree_id)

        resp2 = await client.post("/api/abstract", json={"text": text})
        assert resp2.json()["tree_id"] == tree_id
        assert resp2.json()["cached"] is True


async def test_recent_trees():
    text = "# Doc\n\n" + "word " * 200
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": text})
        tree_id = resp.json()["tree_id"]
        await _wait_for_done(tree_id)

        recent = await client.get("/api/recent")
        assert recent.status_code == 200
        ids = [t["id"] for t in recent.json()]
        assert tree_id in ids


def test_cache_same_text_same_id(tmp_path, monkeypatch):
    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    text = "hello world, this is a cache test."
    id1 = cache.tree_id_for(text)
    id2 = cache.tree_id_for(text)
    assert id1 == id2
