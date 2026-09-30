import json

import httpx
import pytest

from riemann.abstraction.summarise import (
    ClaudeSummariser,
    ModelCooldownError,
    ProxySummariser,
    get_summariser,
    parse_json_robustly,
    strip_code_fence,
)


def test_strip_code_fence_removes_json_fence():
    raw = '```json\n{"text": "hi"}\n```'
    assert strip_code_fence(raw) == '{"text": "hi"}'


def test_strip_code_fence_removes_plain_fence():
    raw = '```\n{"text": "hi"}\n```'
    assert strip_code_fence(raw) == '{"text": "hi"}'


def test_parse_json_robustly_handles_fenced_and_plain():
    assert parse_json_robustly('{"a": 1}') == {"a": 1}
    assert parse_json_robustly('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_robustly_extracts_embedded_object():
    raw = 'Sure, here you go:\n{"a": 1}\nHope that helps!'
    assert parse_json_robustly(raw) == {"a": 1}


async def test_proxy_summariser_request_shape_and_parsing():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"text": "a summary"}'}}]},
        )

    summariser = ProxySummariser(model="claude-sonnet-5-5")
    summariser._api_key = "test-key-123"

    async def fake_summarise(prompt, system):
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, timeout=120.0) as client:
            headers = {"Content-Type": "application/json", "Authorization": "Bearer test-key-123"}
            body = {
                "model": summariser.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
            resp = await client.post(f"{summariser.base_url}/v1/chat/completions", headers=headers, json=body)
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    result = await fake_summarise("summarise this", "system prompt")
    assert result == '{"text": "a summary"}'


async def test_proxy_summariser_end_to_end_with_mock_transport(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "claude-sonnet-5-5"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        assert body["temperature"] == 0.2
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"text": "hello"}'}}]},
        )

    summariser = ProxySummariser(model="claude-sonnet-5-5", base_url="http://127.0.0.1:8317")
    summariser._api_key = None

    import riemann.abstraction.summarise as summarise_module

    original_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    try:
        result = await summariser.summarise("prompt text", "system text")
    finally:
        monkeypatch.setattr(httpx, "AsyncClient", original_async_client)

    assert result == '{"text": "hello"}'


async def test_proxy_summariser_model_cooldown_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"code": "model_cooldown", "message": "cooling down"}},
        )

    summariser = ProxySummariser(model="claude-sonnet-5-5")
    summariser._api_key = None

    import httpx as httpx_module

    original_async_client = httpx_module.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx_module, "AsyncClient", client_factory)
    try:
        with pytest.raises(ModelCooldownError) as exc_info:
            await summariser.summarise("prompt", "system")
    finally:
        monkeypatch.setattr(httpx_module, "AsyncClient", original_async_client)

    assert "claude-sonnet-5-5" in str(exc_info.value)
    assert "another model" in str(exc_info.value)


def test_get_summariser_factory_defaults_to_proxy(monkeypatch):
    monkeypatch.delenv("RIEMANN_PROVIDER", raising=False)
    assert isinstance(get_summariser(), ProxySummariser)


def test_get_summariser_factory_agent_sdk(monkeypatch):
    monkeypatch.setenv("RIEMANN_PROVIDER", "agent-sdk")
    assert isinstance(get_summariser(), ClaudeSummariser)


async def test_list_models_drops_blocked_and_non_text(monkeypatch):
    import httpx

    from riemann.abstraction import summarise

    payload = {"data": [
        {"id": "claude-sonnet-5-5", "owned_by": "anthropic"},
        {"id": "claude-opus-5", "owned_by": "anthropic"},
        {"id": "claude-sonnet-5", "owned_by": "anthropic"},
        {"id": "gpt-image-2", "owned_by": "openai"},
        {"id": "grok-imagine-video", "owned_by": "xai"},
        {"id": "gemini-3.8-flash-high", "owned_by": "antigravity"},
    ]}

    def handler(request):
        return httpx.Response(200, json=payload)

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    ids = [m["id"] for m in await summarise.list_models()]
    assert ids == ["claude-sonnet-5-5", "gemini-3.8-flash-high"]
