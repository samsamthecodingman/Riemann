"""Summarisers: turn a prompt into JSON text.

`Summariser` is the Protocol build.py depends on. `ClaudeSummariser` talks
to the local Claude Code login via claude-agent-sdk (no API key, ever).
`FakeSummariser` is deterministic and used by all tests -- no network.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol


class Summariser(Protocol):
    async def summarise(self, prompt: str, system: str) -> str:
        """Return raw JSON text (the caller parses and validates it)."""
        ...


def strip_code_fence(text: str) -> str:
    """Strip a ```json ... ``` or ``` ... ``` wrapper if present."""
    stripped = text.strip()
    match = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def parse_json_robustly(text: str) -> dict:
    """Parse JSON text, stripping code fences and trimming stray prose."""
    candidate = strip_code_fence(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fall back: grab the first {...} span.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(candidate[start : end + 1])
    raise ValueError(f"Could not parse JSON from summariser output: {text[:200]!r}")


class ClaudeSummariser:
    """Summariser backed by the local Claude Code login, via claude-agent-sdk.

    Never reads or requires an API key -- auth is whatever `claude` CLI is
    already logged in as on this machine.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("RIEMANN_MODEL", "claude-sonnet-5")

    async def summarise(self, prompt: str, system: str) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, query

        options = ClaudeAgentOptions(
            system_prompt=system,
            model=self.model,
            max_turns=1,
            allowed_tools=[],
        )

        chunks: list[str] = []
        async for message in query(prompt=prompt, options=options):
            block_content = getattr(message, "content", None)
            if not block_content:
                continue
            for block in block_content:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks)


_PROXY_CONFIG_PATH = os.path.expanduser("~/.cli-proxy-api/config.yaml")


def _read_proxy_api_key() -> str | None:
    """Read the first entry under `api-keys:` in the CLIProxyAPI config,
    with a tiny line parser (no PyYAML dependency). Returns None if the
    file or the key can't be found. Never logs the key."""
    try:
        with open(_PROXY_CONFIG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None

    in_api_keys = False
    for line in lines:
        stripped = line.strip()
        if not in_api_keys:
            if stripped == "api-keys:":
                in_api_keys = True
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"').strip("'")
            if value:
                return value
            continue
        # Any non "- " line (that isn't blank/comment) ends the list.
        if stripped and not stripped.startswith("#"):
            break
    return None


class ModelCooldownError(RuntimeError):
    pass


class ProxySummariser:
    """Summariser backed by Sam's local CLIProxyAPI (an OpenAI-compatible
    proxy), so summarisation doesn't spend Agent SDK credit.

    Talks to http://127.0.0.1:8317 by default (RIEMANN_PROXY_URL) --
    deliberately NOT the Headroom proxy on 8787, which compresses prompts
    and would alter source text, breaking faithfulness to the source.
    """

    DEFAULT_URL = "http://127.0.0.1:8317"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("RIEMANN_MODEL", "claude-sonnet-5")
        self.base_url = (base_url or os.environ.get("RIEMANN_PROXY_URL") or self.DEFAULT_URL).rstrip("/")
        self._api_key = os.environ.get("RIEMANN_PROXY_KEY") or _read_proxy_api_key()

    async def summarise(self, prompt: str, system: str) -> str:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(2):
                try:
                    resp = await client.post(
                        f"{self.base_url}/v1/chat/completions", headers=headers, json=body
                    )
                except (httpx.ConnectError, httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = exc
                    if attempt == 0:
                        await self._backoff()
                        continue
                    raise

                self._raise_on_cooldown(resp)

                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = RuntimeError(
                        f"ProxySummariser: {resp.status_code} from {self.base_url}"
                    )
                    if attempt == 0:
                        await self._backoff()
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

        raise last_error or RuntimeError("ProxySummariser: request failed")

    def _raise_on_cooldown(self, resp) -> None:
        if resp.status_code < 400:
            return
        try:
            payload = resp.json()
        except ValueError:
            return
        error = payload.get("error") if isinstance(payload, dict) else None
        code = error.get("code") if isinstance(error, dict) else payload.get("code") if isinstance(payload, dict) else None
        if code == "model_cooldown":
            raise ModelCooldownError(
                f"Model '{self.model}' is in cooldown on the proxy. "
                f"Set RIEMANN_MODEL to another model (e.g. 'gemini-3.8-flash-high') and retry."
            )

    async def _backoff(self) -> None:
        import asyncio

        await asyncio.sleep(0.5)


def get_summariser(model: str | None = None) -> Summariser:
    """Factory: pick the summariser implementation from RIEMANN_PROVIDER.

    "proxy" (default): ProxySummariser, via the local CLIProxyAPI.
    "agent-sdk": ClaudeSummariser, via the local Claude Code login.
    """
    provider = os.environ.get("RIEMANN_PROVIDER", "proxy")
    if provider == "agent-sdk":
        return ClaudeSummariser(model=model)
    return ProxySummariser(model=model)


_TARGET_RE = re.compile(r"Target length: about (\d+) words")
_CHILD_IDS_RE = re.compile(r"^Child ids \(in order\): (.*)$", re.MULTILINE)
_LEAF_IDS_RE = re.compile(r"^Leaf ids you may cite \(in order\): (.*)$", re.MULTILINE)


class FakeSummariser:
    """Deterministic summariser for tests. No network.

    Returns the first N words of the concatenated input as `text` (N taken
    from the "Target length: about N words" hint build.py embeds in the
    system prompt when there is one, else a fixed default), and cites all
    leaf ids build.py listed via the "Leaf ids you may cite (in order): ..."
    marker line in the prompt. This keeps the adaptive-depth math in
    build.py exercised deterministically without any network access.
    """

    def __init__(self, words: int = 20) -> None:
        self.words = words

    async def summarise(self, prompt: str, system: str) -> str:
        combined = system + "\n" + prompt

        leaf_match = _LEAF_IDS_RE.search(prompt)
        leaf_ids = [x for x in leaf_match.group(1).split(", ") if x] if leaf_match else []
        child_match = _CHILD_IDS_RE.search(prompt)
        child_ids = [x for x in child_match.group(1).split(", ") if x] if child_match else []

        target_match = _TARGET_RE.search(combined)
        target_words = int(target_match.group(1)) if target_match else self.words

        body_lines = [
            line
            for line in prompt.splitlines()
            if not line.startswith("Child ids (in order):")
            and not line.startswith("Leaf ids you may cite (in order):")
        ]
        body = " ".join(" ".join(body_lines).split())
        words = [w for w in body.split(" ") if w]
        n = max(1, target_words)
        text = " ".join(words[:n])
        if not text:
            text = "(empty)"

        importance = {cid: 0.5 for cid in child_ids}
        result = {"text": text, "cites": leaf_ids, "importance": importance}
        return json.dumps(result)
