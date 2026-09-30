"""Local-only guard, request limits, and zip-bomb defence."""


import pytest
from httpx import ASGITransport, AsyncClient

import riemann.server as server_module


def _client(host="test"):
    return AsyncClient(transport=ASGITransport(app=server_module.app), base_url=f"http://{host}")


async def test_unknown_host_header_is_refused_dns_rebinding():
    async with _client("evil.example.com") as c:
        assert (await c.get("/api/recent")).status_code == 403
    async with _client("localhost:8765") as c:
        assert (await c.get("/api/recent")).status_code == 200
    async with _client("127.0.0.1") as c:
        assert (await c.get("/api/recent")).status_code == 200


@pytest.mark.parametrize("origin", ["https://evil.example.com", "null", "http://localhost.evil.com"])
async def test_cross_site_posts_are_refused(origin):
    async with _client() as c:
        r = await c.post("/api/abstract", json={"text": "hello world " * 30}, headers={"Origin": origin})
        assert r.status_code == 403
        r = await c.post("/api/events", json=[{"type": "x"}], headers={"Origin": origin})
        assert r.status_code == 403
        r = await c.post("/api/abstract", json={"text": "hi"}, headers={"Sec-Fetch-Site": "cross-site"})
        assert r.status_code == 403


async def test_same_origin_post_is_allowed():
    async with _client() as c:
        r = await c.post("/api/events", json=[{"type": "x"}], headers={"Origin": "http://localhost:8765"})
        assert r.status_code == 204


async def test_json_endpoints_require_a_json_content_type():
    async with _client() as c:
        r = await c.post("/api/abstract", content=b'{"text":"hello world"}', headers={"content-type": "text/plain"})
        assert r.status_code == 415
        r = await c.post("/api/events", content=b"[]", headers={"content-type": "text/plain"})
        assert r.status_code == 415


async def test_oversized_bodies_are_refused():
    async with _client() as c:
        big = b'{"text":"' + b"a" * (server_module.MAX_JSON_BYTES + 10) + b'"}'
        r = await c.post("/api/abstract", content=big, headers={"content-type": "application/json"})
        assert r.status_code == 413
        r = await c.post("/api/events", content=b"[" + b"{}," * 400_000 + b"{}]", headers={"content-type": "application/json"})
        assert r.status_code == 413
