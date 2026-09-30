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

    monkeypatch.setattr(server_module, "get_summariser", lambda model=None: FakeSummariser())
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


async def test_model_choice_is_a_separate_tree_and_recorded():
    text = "# Doc\n\n" + "word " * 200
    async with await _client() as client:
        a = (await client.post("/api/abstract", json={"text": text})).json()["tree_id"]
        b = (await client.post("/api/abstract", json={"text": text, "model": "gemini-3.8-flash-high"})).json()["tree_id"]
        assert a != b
        await _wait_for_done(b)
        tree = (await client.get(f"/api/tree/{b}")).json()
        assert tree["model"] == "gemini-3.8-flash-high"
        recent = {t["id"]: t for t in (await client.get("/api/recent")).json()}
        assert recent[b]["model"] == "gemini-3.8-flash-high"


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-sonnet-5"])
async def test_blocked_model_is_refused(model):
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "hello " * 50, "model": model})
        assert resp.status_code == 400


async def test_models_endpoint_filters(monkeypatch):
    import riemann.server as server_module

    async def fake_list():
        return [{"id": "claude-sonnet-5-5", "provider": "anthropic"}]

    monkeypatch.setattr(server_module, "list_models", fake_list)
    async with await _client() as client:
        data = (await client.get("/api/models")).json()
        assert data["default"]
        assert data["models"] == [{"id": "claude-sonnet-5-5", "provider": "anthropic"}]


async def test_short_titles_backfill_fills_missing_and_persists():
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "# Doc\n\n" + "word " * 1500})
        tree_id = resp.json()["tree_id"]
        await _wait_for_done(tree_id)
        build.BUILDS.clear()  # as after a server restart: the tree comes from the cache

        tree = cache.load_tree(tree_id)
        assert tree.sections
        for n in tree.nodes.values():
            n.short_title = None
        cache.save_tree(tree)

        resp = await client.post(f"/api/tree/{tree_id}/short-titles")
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] > 0
        assert set(tree.sections) <= set(body["titles"])
        for label in body["titles"].values():
            assert 0 < len(label.split()) <= 3 and len(label) <= 24

        saved = cache.load_tree(tree_id)
        for sid in tree.sections:
            assert saved.nodes[sid].short_title == body["titles"][sid]

        again = await client.post(f"/api/tree/{tree_id}/short-titles")
        assert again.json()["added"] == 0
        assert again.json()["titles"] == body["titles"]


async def test_short_titles_backfill_unknown_tree_is_404():
    async with await _client() as client:
        resp = await client.post("/api/tree/doesnotexist/short-titles")
        assert resp.status_code == 404


async def test_overview_backfill_builds_once_and_persists():
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "# Doc\n\n" + "word " * 1500})
        tree_id = resp.json()["tree_id"]
        await _wait_for_done(tree_id)
        build.BUILDS.clear()

        tree = cache.load_tree(tree_id)
        assert tree.overview is not None
        tree.overview = None
        cache.save_tree(tree)

        resp = await client.post(f"/api/tree/{tree_id}/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["added"] is True and body["overview"]["doc_title"]
        assert cache.load_tree(tree_id).overview is not None

        again = await client.post(f"/api/tree/{tree_id}/overview")
        assert again.json()["added"] is False
        assert again.json()["overview"] == body["overview"]


async def test_overview_backfill_unknown_tree_is_404():
    async with await _client() as client:
        assert (await client.post("/api/tree/doesnotexist/overview")).status_code == 404


async def test_older_cache_namespaces_still_open_and_list(tmp_path):
    async with await _client() as client:
        resp = await client.post("/api/abstract", json={"text": "# Doc\n\n" + "word " * 1500})
        tree_id = resp.json()["tree_id"]
        await _wait_for_done(tree_id)
        build.BUILDS.clear()

        # move the tree into an older build-version dir: read-only fallback
        current = cache.path_for(tree_id)
        old_dir = current.parent.parent / "r3-leaf120-gist25-stop34-schema3"
        old_dir.mkdir()
        current.rename(old_dir / current.name)
        assert not cache.exists(tree_id)
        assert cache.load_tree(tree_id) is not None
        assert (await client.get(f"/api/tree/{tree_id}")).status_code == 200
        assert tree_id in [t["id"] for t in (await client.get("/api/recent")).json()]

        # the backfill saves into the current namespace and leaves the old copy alone
        tree = cache.load_tree(tree_id)
        tree.overview = None
        (old_dir / current.name).write_text(tree.model_dump_json())
        before = (old_dir / current.name).read_text()
        resp = await client.post(f"/api/tree/{tree_id}/overview")
        assert resp.json()["added"] is True
        assert (old_dir / current.name).read_text() == before
        assert cache.exists(tree_id)


def test_clean_url_adds_scheme_and_trims():
    from riemann.abstraction.ingest import clean_url

    assert clean_url("  example.com/page ") == "https://example.com/page"
    assert clean_url("http://example.com") == "http://example.com"
    assert clean_url("HTTPS://Example.com") == "HTTPS://Example.com"


async def test_bad_url_gets_a_short_message():
    async with await _client() as client:
        r = await client.post("/api/abstract", json={"url": "http://127.0.0.1:1/x"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail.startswith("could not fetch that link:")
    assert "httpx" not in detail and "mozilla" not in detail


async def test_huge_paste_is_refused_before_any_build():
    async with await _client() as client:
        r = await client.post("/api/abstract", json={"text": "word " * 50_001})
    assert r.status_code == 400
    assert "50,000" in r.json()["detail"]
    assert not build.BUILDS


async def test_post_events_rejects_malformed_bodies_with_400():
    async with await _client() as client:
        bad_json = await client.post("/api/events", content=b"garbage", headers={"content-type": "application/json"})
        not_objects = await client.post("/api/events", json=[1, "x"])
        not_list = await client.post("/api/events", json={"a": 1})
    assert (bad_json.status_code, not_objects.status_code, not_list.status_code) == (400, 400, 400)
    assert not events_module.log_path().exists()


@pytest.mark.parametrize("body", [[1], "str", {"text": 123}, {"text": "hi", "model": ["a"]}, {"url": 5}])
async def test_abstract_rejects_wrongly_typed_bodies_with_400(body):
    async with await _client() as client:
        r = await client.post("/api/abstract", json=body)
    assert r.status_code == 400
    assert not build.BUILDS


async def test_failed_build_is_retried_not_replayed(monkeypatch):
    import riemann.server as server_module

    calls = {"n": 0}

    class Flaky(FakeSummariser):
        async def summarise(self, prompt, system):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("proxy down")
            return await super().summarise(prompt, system)

    monkeypatch.setattr(server_module, "get_summariser", lambda model=None: Flaky())
    text = "A paragraph about ponds. " * 40
    async with await _client() as client:
        first = (await client.post("/api/abstract", json={"text": text})).json()["tree_id"]
        await build.get_builder(first).task
        assert build.get_builder(first).tree.status == "error"
        second = (await client.post("/api/abstract", json={"text": text})).json()
        assert second["tree_id"] == first and second["cached"] is False
        await build.get_builder(first).task
        assert build.get_builder(first).tree.status == "done"


@pytest.mark.parametrize("bad", ["../x", "..", "a/b", "a\\b", "x.json", "", "a" * 65, "%2e%2e"])
def test_tree_ids_that_could_be_paths_are_refused(bad, tmp_path):
    from riemann.abstraction import cache

    (tmp_path / "cache").mkdir(exist_ok=True)
    (tmp_path / "x.json").write_text("{}")
    assert cache.is_safe_id(bad) is False
    assert cache.load_tree(bad) is None
    assert cache.exists(bad) is False
    with pytest.raises(ValueError):
        cache.path_for(bad)


async def test_tree_routes_answer_404_for_odd_ids():
    async with await _client() as client:
        for tid in ["x.json", "%2e%2e", "a" * 200]:
            assert (await client.get(f"/api/tree/{tid}")).status_code == 404
            assert (await client.post(f"/api/tree/{tid}/overview")).status_code == 404
            assert (await client.post(f"/api/tree/{tid}/short-titles")).status_code == 404
            assert (await client.get(f"/api/tree/{tid}/events")).status_code == 404
