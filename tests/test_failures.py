"""Model-failure handling: what the build does when the summariser fails."""

import asyncio

import pytest

from riemann.abstraction import build
from riemann.abstraction.build import start_build
from riemann.abstraction.summarise import FakeSummariser, ModelError, parse_json_robustly


def _doc(sections: int = 8) -> str:
    parts = ["# Doc"]
    for s in range(sections):
        parts += ["", f"## Section {s}"]
        for p in range(3):
            parts += ["", " ".join(f"w{s}_{p}_{i}" for i in range(110)) + "."]
    return "\n".join(parts)


class FailingOnNth(FakeSummariser):
    """Fake that raises on its nth call and counts calls (slowly, so a level's
    groups overlap)."""

    def __init__(self, fail_on: int, delay: float = 0.05):
        super().__init__()
        self.fail_on = fail_on
        self.delay = delay
        self.calls = 0

    async def summarise(self, prompt, system):
        self.calls += 1
        n = self.calls
        if n == self.fail_on:
            raise ModelError("the model is unavailable")
        await asyncio.sleep(self.delay)
        return await super().summarise(prompt, system)


async def test_failed_build_stops_issuing_model_calls():
    s = FailingOnNth(fail_on=3)
    b = start_build("fail-stop", "T", _doc(), s)
    await b.task
    assert b.tree.status == "error"
    at_error = s.calls
    await asyncio.sleep(0.4)
    assert s.calls == at_error, "sibling groups kept calling the model after the build failed"
    # The provisional gist, then about one wave of concurrent groups (8 are queued): the rest must not start.
    assert s.calls <= build.MAX_CONCURRENCY + 2, f"{s.calls} calls for a build that failed on its third"


async def test_error_event_carries_the_clear_message():
    s = FailingOnNth(fail_on=2)
    b = start_build("fail-msg", "T", _doc(), s)
    await b.task
    name, data = b.history[-1]
    assert name == "error"
    assert data["message"] == "the model is unavailable"


async def test_failed_build_is_not_cached():
    from riemann.abstraction import cache

    s = FailingOnNth(fail_on=4)
    b = start_build("fail-nocache", "T", _doc(), s)
    await b.task
    assert not cache.exists("fail-nocache")


class Stub:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    async def summarise(self, prompt, system):
        self.calls += 1
        return self.replies.pop(0) if self.replies else self.replies_last

    replies_last = "[]"


async def test_non_object_json_is_retried_then_a_clear_error():
    # A JSON array (or number) is not a summary; treat it like bad JSON: retry once, then fail clearly.
    s = Stub(["[1, 2, 3]", "42"])
    b = start_build("fail-array", "T", _doc(), s)
    await b.task
    assert b.tree.status == "error"
    assert s.calls == 2
    msg = b.history[-1][1]["message"]
    assert "'list' object" not in msg and "AttributeError" not in msg
    assert "not a usable reply" in msg or "usable" in msg


async def test_unusable_reply_message_does_not_quote_the_document():
    s = Stub(["Sure! Here is a summary.", "Sorry, no."])
    b = start_build("fail-prose", "T", _doc(), s)
    await b.task
    msg = b.history[-1][1]["message"]
    assert "w0_1" not in msg and "Title:" not in msg


def test_parse_json_robustly_rejects_non_objects():
    with pytest.raises(ValueError):
        parse_json_robustly("[1, 2]")
    with pytest.raises(ValueError):
        parse_json_robustly("7")


async def test_unexpected_exception_gets_a_plain_message():
    class Boom(FakeSummariser):
        async def summarise(self, prompt, system):
            raise KeyError("choices")

    b = start_build("fail-keyerror", "T", _doc(), Boom())
    await b.task
    msg = b.history[-1][1]["message"]
    assert msg != "'choices'"
    assert "try again" in msg.lower()


# ---------------------------------------------------------------------------
# ProxySummariser: retries, Retry-After, and plain messages
# ---------------------------------------------------------------------------
import httpx

from riemann.abstraction.summarise import ProxySummariser


@pytest.fixture
def proxy(monkeypatch):
    """A ProxySummariser whose HTTP goes to a handler list; sleeps are recorded, not waited."""
    state = {"calls": 0, "sleeps": [], "handler": None}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        return state["handler"](state["calls"], request)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))

    async def fake_sleep(seconds):
        state["sleeps"].append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setenv("RIEMANN_PROXY_KEY", "dummy")
    state["s"] = ProxySummariser(model="m", base_url="http://127.0.0.1:1")
    return state


def _ok(text="{}"):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


async def test_429_waits_for_retry_after_then_succeeds(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(429, headers={"Retry-After": "3"}) if n == 1 else _ok("hi")
    assert await proxy["s"].summarise("p", "s") == "hi"
    assert proxy["sleeps"] == [3.0]


async def test_persistent_429_fails_clearly_after_three_attempts(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(429)
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert proxy["calls"] == 3
    assert "rate" in str(e.value).lower()
    assert "developer.mozilla" not in str(e.value) and "127.0.0.1" not in str(e.value)


async def test_huge_retry_after_fails_fast_with_the_wait(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(429, headers={"Retry-After": "600"})
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert proxy["calls"] == 1 and proxy["sleeps"] == []
    assert "10 minutes" in str(e.value) or "600" in str(e.value)


async def test_500_then_ok_retries(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(500) if n < 3 else _ok("fine")
    assert await proxy["s"].summarise("p", "s") == "fine"
    assert proxy["calls"] == 3


async def test_persistent_500_message(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(502, text="<html>Bad gateway</html>")
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert "502" in str(e.value) and "<html>" not in str(e.value) and "127.0.0.1" not in str(e.value)


async def test_timeout_retries_once_then_says_too_slow(proxy):
    def h(n, r):
        raise httpx.ReadTimeout("slow", request=r)

    proxy["handler"] = h
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert proxy["calls"] == 2
    assert "too long" in str(e.value) or "slow" in str(e.value)


async def test_proxy_down_says_so(proxy):
    def h(n, r):
        raise httpx.ConnectError("refused", request=r)

    proxy["handler"] = h
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert "reach" in str(e.value).lower() and "proxy" in str(e.value).lower()


async def test_auth_error_is_not_retried(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(401, json={"error": {"message": "bad key sk-SECRET"}})
    with pytest.raises(ModelError) as e:
        await proxy["s"].summarise("p", "s")
    assert proxy["calls"] == 1
    assert "401" in str(e.value) and "sk-SECRET" not in str(e.value)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json at all"),
        httpx.Response(200, json={"id": "x"}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"error": {"message": "upstream exploded"}}),
        httpx.Response(200, json=[1, 2]),
        httpx.Response(200, json={"choices": ["nope"]}),
    ],
)
async def test_malformed_200_replies_become_model_errors(proxy, response):
    proxy["handler"] = lambda n, r: response
    with pytest.raises(ModelError):
        await proxy["s"].summarise("p", "s")


async def test_null_content_is_returned_empty_for_the_build_to_retry(proxy):
    proxy["handler"] = lambda n, r: httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
    assert await proxy["s"].summarise("p", "s") == ""
