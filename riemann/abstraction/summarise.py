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


class ModelError(RuntimeError):
    """A model failure whose message is fit to show to the reader as it stands
    (the build's error event and the loading screen use it verbatim)."""


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
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    # Fall back: grab the first {...} span (also rescues a non-object top level).
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"Could not parse JSON from summariser output: {text[:200]!r}")


class ClaudeSummariser:
    """Summariser backed by the local Claude Code login, via claude-agent-sdk.

    Never reads or requires an API key -- auth is whatever `claude` CLI is
    already logged in as on this machine.
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or default_model()

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


class ModelCooldownError(ModelError):
    pass


def default_model() -> str:
    return os.environ.get("RIEMANN_MODEL", "claude-sonnet-5-5")


# Never offered, whatever the proxy lists (Sam's standing rule: Opus 5.5 and
# Sonnet 5.5 replace these).
BLOCKED_MODELS = {"claude-opus-5", "claude-sonnet-5"}
# Not text chat models: image/video generators and single-purpose endpoints.
_NON_TEXT = re.compile(r"image|video|codex-auto-review")


async def list_models() -> list[dict]:
    """Text models the local proxy can serve, as [{id, provider}], for the
    model picker. Empty list if the proxy is unreachable (the picker then
    offers just the default)."""
    import httpx

    base = (os.environ.get("RIEMANN_PROXY_URL") or ProxySummariser.DEFAULT_URL).rstrip("/")
    key = os.environ.get("RIEMANN_PROXY_KEY") or _read_proxy_api_key()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base}/v1/models", headers=headers)
            resp.raise_for_status()
            data = resp.json().get("data", [])
    except Exception:  # noqa: BLE001 - the picker degrades to the default model
        return []
    out = []
    for m in data:
        mid = m.get("id")
        if not mid or mid in BLOCKED_MODELS or _NON_TEXT.search(mid):
            continue
        out.append({"id": mid, "provider": m.get("owned_by") or ""})
    return out


class ProxySummariser:
    """Summariser backed by Sam's local CLIProxyAPI (an OpenAI-compatible
    proxy), so summarisation doesn't spend Agent SDK credit.

    Talks to http://127.0.0.1:8317 by default (RIEMANN_PROXY_URL) --
    deliberately NOT the Headroom proxy on 8787, which compresses prompts
    and would alter source text, breaking faithfulness to the source.
    """

    DEFAULT_URL = "http://127.0.0.1:8317"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or default_model()
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

        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(self.MAX_ATTEMPTS):
                last = attempt == self.MAX_ATTEMPTS - 1
                try:
                    resp = await client.post(
                        f"{self.base_url}/v1/chat/completions", headers=headers, json=body
                    )
                except httpx.TimeoutException as exc:
                    # A call that already ran for two minutes will not do better on a third try.
                    if attempt == 0:
                        await self._backoff(attempt)
                        continue
                    raise ModelError(
                        "The model took too long to answer (over two minutes, twice). "
                        "Try again, or pick a faster model."
                    ) from exc
                except httpx.TransportError as exc:
                    if not last:
                        await self._backoff(attempt)
                        continue
                    raise ModelError(
                        "Could not reach the model service. Is the proxy running? Start it, then try again."
                    ) from exc

                self._raise_on_cooldown(resp)

                if resp.status_code == 429 or resp.status_code >= 500:
                    wait = self._retry_after(resp)
                    if wait is not None and wait > self.MAX_RETRY_AFTER:
                        raise ModelError(
                            f"The model is rate-limiting requests and asked for a wait of about "
                            f"{self._human_wait(wait)}. Try again after that, or pick another model."
                        )
                    if not last:
                        await self._backoff(attempt, wait)
                        continue
                    if resp.status_code == 429:
                        raise ModelError(
                            "The model is rate-limiting requests (too many at once or quota used up). "
                            "Wait a minute and try again, or pick another model."
                        )
                    raise ModelError(
                        f"The model service is having trouble (error {resp.status_code}). "
                        "Try again in a moment, or pick another model."
                    )

                if resp.status_code >= 400:
                    raise ModelError(
                        f"The model service refused the request (error {resp.status_code}). "
                        "Check the model choice and the proxy's settings."
                    )
                return self._content_of(resp)

        raise ModelError("The model service did not answer. Try again.")  # unreachable in practice

    MAX_ATTEMPTS = 3
    MAX_RETRY_AFTER = 30.0  # seconds; a longer wait is reported, not slept through

    @staticmethod
    def _human_wait(seconds: float) -> str:
        return f"{round(seconds)} seconds" if seconds < 120 else f"{round(seconds / 60)} minutes"

    @staticmethod
    def _retry_after(resp) -> float | None:
        raw = resp.headers.get("retry-after")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None  # absent, or an HTTP date: use the ordinary backoff
        return value if value >= 0 else None

    @staticmethod
    def _content_of(resp) -> str:
        """The reply text of a 200 response, or a ModelError if the body is not a chat completion.
        A null or empty content comes back as "" (the build retries once, then reports it)."""
        try:
            data = resp.json()
        except ValueError as exc:
            raise ModelError("The model service sent something that was not JSON (maybe an error page). Try again.") from exc
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            err = data.get("error") if isinstance(data, dict) else None
            said = err.get("message") if isinstance(err, dict) else err if isinstance(err, str) else None
            if isinstance(said, str) and said.strip():
                raise ModelError(f"The model service reported a problem: {said.strip()[:160]}")
            raise ModelError("The model service replied without any answer in it. Try again.")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        return content if isinstance(content, str) else ""

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
                f"Pick another model on the home page (e.g. 'gemini-3.8-flash-high') and try again."
            )

    async def _backoff(self, attempt: int = 0, retry_after: float | None = None) -> None:
        import asyncio

        await asyncio.sleep(retry_after if retry_after is not None else 0.5 * 2**attempt)


def get_summariser(model: str | None = None) -> Summariser:
    """Factory: pick the summariser implementation from RIEMANN_PROVIDER.

    "proxy" (default): ProxySummariser, via the local CLIProxyAPI.
    "agent-sdk": ClaudeSummariser, via the local Claude Code login.
    """
    provider = os.environ.get("RIEMANN_PROVIDER", "proxy")
    if provider == "agent-sdk":
        return ClaudeSummariser(model=model)
    return ProxySummariser(model=model)


_GOAL_RE = re.compile(r"Reader's goal: (\w+)")
_GOAL_TITLE_PREFIX = {
    "execute": "Do",
    "learn": "Learn",
    "decide": "Decide",
    "reference": "Ref",
    "plan": "Plan",
    "communicate": "Reply",
}

_TARGET_RE = re.compile(r"Target length: about (\d+) words")
_LEAF_BLOCK_RE = re.compile(r"^--- leaf (\S+) ---\n(.*?)(?=^--- leaf |\n\nLeaf ids you may cite)", re.MULTILINE | re.DOTALL)
_CHILD_IDS_RE = re.compile(r"^Child ids \(in order\): (.*)$", re.MULTILINE)
_SHORT_IDS_RE = re.compile(r"^Short-title node ids: (.*)$", re.MULTILINE)
_LEAF_IDS_RE = re.compile(r"^Leaf ids you may cite \(in order\): (.*)$", re.MULTILINE)


class FakeSummariser:
    """Deterministic summariser for tests. No network.

    Returns the first N words of the concatenated input as `text` (N taken
    from the "Target length: about N words" hint build.py embeds in the
    system prompt when there is one, else a fixed default), and cites all
    leaf ids build.py listed via the "Leaf ids you may cite (in order): ..."
    marker line in the prompt. This keeps the adaptive-depth math in
    build.py exercised deterministically without any network access.

    Also emits deterministic `title`, `hook`, `child_titles`, `key_points`
    and `steps` (derived from the same word list as `text`), so build.py's
    v2 macaron fields are exercised too. `key_fact` is always null here --
    tests that need to exercise the key-fact validation path construct
    their own minimal Summariser stub instead.
    """

    def __init__(self, words: int = 20) -> None:
        self.words = words

    def _overview(self, prompt: str, system: str) -> str:
        """Deterministic overview: title from the "Document title" line, values
        are the first alphabetic words of the first shown leaf (so the number
        validator never trips), cited to that leaf."""
        title_match = re.search(r"^Document title \(as extracted\): (.*)$", prompt, re.MULTILINE)
        doc_title = (title_match.group(1).strip() if title_match else "") or "Untitled"
        leaf_match = _LEAF_IDS_RE.search(prompt)
        leaf_ids = [x for x in leaf_match.group(1).split(", ") if x] if leaf_match else []
        blocks = [(m.group(1), m.group(2).strip()) for m in _LEAF_BLOCK_RE.finditer(prompt)]
        first_leaf = blocks[0] if blocks else None
        words = [w for w in (first_leaf[1].split() if first_leaf else []) if w.isalpha()]
        goal_match = _GOAL_RE.search(system)
        goal = goal_match.group(1) if goal_match else None
        genre_match = re.search(r"Document genre: (\w+)", system)
        genre = genre_match.group(1) if genre_match else None
        labels = ["Deliverables", "Due", "What you need to do"] if goal == "execute" else ["Main point", "Detail", "Context"]
        cites = leaf_ids[:1]
        essentials = [
            {"label": label, "value": " ".join(words[i * 4 : i * 4 + 4]) or "not stated", "cites": cites}
            for i, label in enumerate(labels)
        ]
        out = {
            "doc_title": doc_title,
            "doc_kind": "Assignment brief" if goal == "execute" else "Document",
            "what_it_is": "This is " + " ".join(words[:8]) + ".",
            "essentials": essentials,
        }
        if genre is None:
            from riemann.abstraction.genre import detect_genre

            out["genre"] = detect_genre(doc_title, "\n".join(t for _, t in blocks))[0] or "other"
        return json.dumps(out)

    async def summarise(self, prompt: str, system: str) -> str:
        combined = system + "\n" + prompt

        # Overview card (build.generate_overview).
        if "Task: overview" in prompt:
            return self._overview(prompt, system)

        # Provisional gist (build.make_provisional): {"text": ..., "genre": ...}.
        if system.startswith("You are producing a fast provisional"):
            from riemann.abstraction.genre import detect_genre

            title_match = re.match(r"Title: (.*)\n", prompt)
            guessed = detect_genre(title_match.group(1) if title_match else "", prompt)[0] or "other"
            body = " ".join(prompt.split()[:20]) or "(empty)"
            return json.dumps({"text": body, "genre": guessed})

        # Short-title backfill (build.backfill_short_titles): {node_id: label}.
        short_match = _SHORT_IDS_RE.search(prompt)
        if short_match:
            ids = [x for x in short_match.group(1).split(", ") if x]
            return json.dumps({nid: f"Part {nid[-4:]}" for nid in ids})

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

        goal_match = _GOAL_RE.search(system)
        goal = goal_match.group(1) if goal_match else None

        title = " ".join(words[:5]) if words else "Untitled"
        hook = " ".join(words[:15]) if words else ""
        child_titles = {cid: " ".join((f"About {cid}").split()[:8]) for cid in child_ids}
        short_title = " ".join(words[:2])[:24].strip() or None
        child_short_titles = {cid: f"Part {cid[-4:]}" for cid in child_ids}
        key_points = [chunk for chunk in (" ".join(words[i : i + 4]) for i in range(0, min(len(words), 8), 4)) if chunk]

        if goal in _GOAL_TITLE_PREFIX:
            prefix = _GOAL_TITLE_PREFIX[goal]
            title = f"{prefix}: {title}"
            child_titles = {cid: f"{prefix}: {t}" for cid, t in child_titles.items()}
        steps = (
            [chunk for chunk in (" ".join(words[i : i + 3]) for i in range(0, min(len(words), 9), 3)) if chunk]
            if goal in ("execute", "plan")
            else []
        )

        result = {
            "text": text,
            "cites": leaf_ids,
            "importance": importance,
            "title": title,
            "hook": hook,
            "child_titles": child_titles,
            "short_title": short_title,
            "child_short_titles": child_short_titles,
            "key_points": key_points,
            "key_fact": None,
            "steps": steps,
        }
        return json.dumps(result)
