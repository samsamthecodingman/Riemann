"""URL ingest must not be a way to reach local services (the SSRF class)."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from riemann.abstraction import ingest


class _Dummy(BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self):  # noqa: N802
        _Dummy.hits.append(self.path)
        if self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:%d/secret" % self.server.server_port)
            self.end_headers()
            return
        body = b"<html><head><title>Hi</title></head><body><article><p>" + b"Hello world. " * 60 + b"</p></article></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture()
def dummy():
    _Dummy.hits = []
    srv = HTTPServer(("127.0.0.1", 0), _Dummy)  # an ephemeral scratch port, never :8317 or :8787
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:9/x",
        "http://localhost:9/x",
        "http://[::1]:9/x",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://0.0.0.0:9/",
        "http://[::ffff:127.0.0.1]:9/",
        "http://100.64.0.1/",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://127.0.0.1/",
    ],
)
async def test_private_and_odd_urls_are_refused_before_any_connection(url):
    with pytest.raises(ValueError):
        await ingest.check_public_url(url)


async def test_dummy_server_is_never_contacted_for_a_loopback_link(dummy):
    url = f"http://127.0.0.1:{dummy.server_port}/page"
    with pytest.raises(ValueError):
        await ingest.from_url(url)
    with pytest.raises(ValueError):
        await ingest.from_url(f"http://localhost:{dummy.server_port}/page")
    assert _Dummy.hits == []


async def test_redirect_hops_are_checked_too(dummy, monkeypatch):
    # The first hop is allowed (pretend it is public); the redirect target is loopback.
    real = ingest.check_public_url
    calls = []

    async def first_hop_ok(url):
        calls.append(url)
        if len(calls) == 1:
            return
        await real(url)

    monkeypatch.setattr(ingest, "check_public_url", first_hop_ok)
    with pytest.raises(ValueError):
        await ingest.from_url(f"http://127.0.0.1:{dummy.server_port}/redir")
    assert _Dummy.hits == ["/redir"]  # never followed to /secret
    assert len(calls) == 2


async def test_opt_in_allows_local_addresses(dummy, monkeypatch):
    monkeypatch.setenv("RIEMANN_ALLOW_PRIVATE_URLS", "1")
    title, text = await ingest.from_url(f"http://127.0.0.1:{dummy.server_port}/page")
    assert "Hello world" in text
    assert _Dummy.hits == ["/page"]


async def test_server_reports_a_blocked_link_as_400(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    import riemann.server as server_module

    async with AsyncClient(transport=ASGITransport(app=server_module.app), base_url="http://test") as client:
        r = await client.post("/api/abstract", json={"url": "http://169.254.169.254/latest"})
    assert r.status_code == 400
    assert "private or local" in r.json()["detail"]
