"""FastAPI app: the Riemann API, plus serving web/ statically at /.

See docs/v1-build-spec.md, "API (server.py)" for the contract. web/ is
owned by a separate worker (the frontend); this module only mounts it if
present, and creates an empty web/ dir so the server still starts if it
isn't there yet.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from riemann import events
from riemann.abstraction import build, cache, ingest
from riemann.abstraction.chunk import word_count
from riemann.abstraction.summarise import BLOCKED_MODELS, default_model, get_summariser, list_models

app = FastAPI(title="Riemann")

# Each ~120 words is a model call or more; refuse a runaway paste up front.
MAX_SOURCE_WORDS = 50_000
# Request size limits: a pasted document is well under 1 MB; uploads are PDFs and Word files.
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_EVENTS_BYTES = 1024 * 1024

def _allowed_hosts() -> set[str]:
    extra = {h.strip().lower() for h in os.environ.get("RIEMANN_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return {"localhost", "127.0.0.1", "::1"} | extra


def _host_of(value: str) -> str:
    """Hostname of a Host header or an Origin URL, without port or brackets."""
    value = value.strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1].split("/", 1)[0]
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    """This is a personal app on localhost that spends the user's model quota
    and reads their disk cache, so a web page open in another tab must not be
    able to drive it: (1) the Host header must be a local name (defeats DNS
    rebinding), (2) a state-changing request whose Origin is another site is
    refused (defeats cross-site form posts and fetch)."""
    allowed = _allowed_hosts()
    if _host_of(request.headers.get("host", "")) not in allowed:
        return Response("bad host", status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin is not None and _host_of(origin) not in allowed:
            return Response("cross-site request refused", status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return Response("cross-site request refused", status_code=403)
    return await call_next(request)


_OVERVIEW_TASKS: dict[str, asyncio.Future] = {}

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.post("/api/abstract")
async def api_abstract(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")

    model: str | None = None
    objective: str | None = None
    declared = request.headers.get("content-length")
    limit = MAX_UPLOAD_BYTES if content_type.startswith("multipart/form-data") else MAX_JSON_BYTES
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, f"that is too large; the limit is {limit // (1024 * 1024)} MB")
    if content_type.startswith("multipart/form-data"):
        if declared is None:
            raise HTTPException(411, "content-length is required for uploads")
        form = await request.form()
        model = form.get("model") or None
        objective = form.get("objective") or None
        upload = form.get("file")
        if upload is None:
            raise HTTPException(400, "expected a 'file' field")
        content = await upload.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"that file is too large; the limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        try:
            title, text = ingest.from_file(upload.filename or "upload", content)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    else:
        if not content_type.startswith("application/json"):
            raise HTTPException(415, "content-type must be application/json")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_JSON_BYTES:
                raise HTTPException(413, f"that is too large; the limit is {MAX_JSON_BYTES // (1024 * 1024)} MB")
        try:
            body = json.loads(bytes(raw).decode("utf-8"))
        except ValueError:  # bad JSON or bad UTF-8
            raise HTTPException(400, "expected JSON body with 'text' or 'url'")
        if body is not None and not isinstance(body, dict):
            raise HTTPException(400, "expected a JSON object with 'text' or 'url'")
        body = body or {}
        model = body.get("model") or None
        objective = body.get("objective") or None
        url = body.get("url")
        raw_text = body.get("text")
        for field in (model, url, raw_text):
            if field is not None and not isinstance(field, str):
                raise HTTPException(400, "'text', 'url' and 'model' must be strings")
        url = url.strip() if url else None
        if url:
            try:
                title, text = await ingest.from_url(url)
            except Exception as exc:
                raise HTTPException(400, f"could not fetch that link: {ingest.fetch_error_message(exc)}") from exc
        elif raw_text:
            title, text = ingest.from_text(raw_text)
        else:
            raise HTTPException(400, "expected 'text' or 'url' in the JSON body, or a 'file' upload")

    if not text.strip():
        raise HTTPException(400, "no content to abstract")
    n_words = word_count(text)
    if n_words > MAX_SOURCE_WORDS:
        raise HTTPException(
            400,
            f"that is {n_words:,} words; Riemann handles up to {MAX_SOURCE_WORDS:,} at a time. Try one chapter or section.",
        )

    model = model or default_model()
    if model in BLOCKED_MODELS:
        raise HTTPException(400, f"model '{model}' is not allowed")
    if objective is not None:
        objective = str(objective).strip().lower()
        if objective not in build.OBJECTIVE_FOCUS:
            raise HTTPException(400, f"unknown objective '{objective}'")
    tree_id = cache.tree_id_for(text, model, objective)

    if cache.exists(tree_id):
        return {"tree_id": tree_id, "cached": True}

    existing = build.get_builder(tree_id)
    if existing is not None and existing.tree.status == "error":
        # A failed build must not be replayed forever: drop it so this
        # request retries the same document.
        build.BUILDS.pop(tree_id, None)
        existing = None
    if existing is None:
        summariser = get_summariser(model=model)
        builder = build.start_build(tree_id, title, text, summariser, objective=objective)
        builder.tree.model = model

    return {"tree_id": tree_id, "cached": False}


@app.post("/api/tree/{tree_id}/retry")
async def api_retry(tree_id: str) -> dict:
    """Restart a build that failed, from the source and settings the failed one
    had (the loading screen's "Try again"). Nothing to do for a build that is
    running or finished, so a double press is harmless."""
    builder = build.get_builder(tree_id)
    if builder is None:
        if cache.is_safe_id(tree_id) and cache.exists(tree_id):
            return {"tree_id": tree_id}
        raise HTTPException(404, "no such build")
    if builder.tree.status == "error":
        old = builder.tree
        model = old.model or default_model()
        build.BUILDS.pop(tree_id, None)
        fresh = build.start_build(tree_id, old.title, old.source_text, get_summariser(model=model), objective=old.objective)
        fresh.tree.model = model
    return {"tree_id": tree_id}


@app.get("/api/tree/{tree_id}")
async def api_tree(tree_id: str) -> dict:
    builder = build.get_builder(tree_id)
    if builder is not None:
        return builder.tree.model_dump()
    tree = cache.load_tree(tree_id)
    if tree is not None:
        return tree.model_dump()
    raise HTTPException(404, "no such tree")


@app.post("/api/tree/{tree_id}/short-titles")
async def api_short_titles(tree_id: str) -> dict:
    """Backfill short_title for trees built before the field existed: one
    batched model call for every node from the section level down that lacks
    one. Writes the tree back to the cache; returns every short title now set
    below the sections, as {"titles": {node_id: label}, "added": n}."""
    builder = build.get_builder(tree_id)
    if builder is not None and builder.tree.status == "building":
        raise HTTPException(409, "tree is still building")
    tree = builder.tree if builder is not None else cache.load_tree(tree_id)
    if tree is None:
        raise HTTPException(404, "no such tree")
    added: dict[str, str] = {}
    if build.nodes_missing_short_title(tree):
        try:
            added = await build.backfill_short_titles(tree, get_summariser(model=default_model()))
        except Exception as exc:  # noqa: BLE001 - the map falls back to heuristic titles
            raise HTTPException(502, f"could not generate short titles: {type(exc).__name__}") from exc
        if added:
            cache.save_tree(tree)
    return {"titles": build.short_titles_below_sections(tree), "added": len(added)}


@app.post("/api/tree/{tree_id}/overview")
async def api_overview(tree_id: str) -> dict:
    """Backfill the overview card for trees built before it existed: one model
    call from the root/section summaries plus the source's first ~4000 words.
    Once per tree: returns the stored overview if there is one. The tree is
    saved into the current cache namespace (older ones stay read-only).
    Returns {"overview": {...} | null, "added": bool}."""
    builder = build.get_builder(tree_id)
    if builder is not None and builder.tree.status == "building":
        raise HTTPException(409, "tree is still building")
    tree = builder.tree if builder is not None else cache.load_tree(tree_id)
    if tree is None:
        raise HTTPException(404, "no such tree")
    if tree.overview is not None:
        return {"overview": tree.overview.model_dump(), "added": False}
    # One generation per tree at a time: a second request awaits the first.
    task = _OVERVIEW_TASKS.get(tree_id)
    if task is None:
        task = asyncio.ensure_future(build.generate_overview(tree, get_summariser(model=default_model())))
        _OVERVIEW_TASKS[tree_id] = task
    try:
        overview = await task
    except Exception as exc:  # noqa: BLE001 - the reader simply shows no overview card
        raise HTTPException(502, f"could not generate overview: {type(exc).__name__}") from exc
    finally:
        if _OVERVIEW_TASKS.get(tree_id) is task:
            del _OVERVIEW_TASKS[tree_id]
    if tree.overview is not None:
        return {"overview": tree.overview.model_dump(), "added": False}
    if overview is not None:
        tree.overview = overview
        cache.save_tree(tree)
    return {"overview": overview.model_dump() if overview else None, "added": overview is not None}


@app.get("/api/tree/{tree_id}/events")
async def api_tree_events(tree_id: str) -> EventSourceResponse:
    builder = build.get_builder(tree_id)

    if builder is None:
        tree = cache.load_tree(tree_id)
        if tree is None:
            raise HTTPException(404, "no such tree")

        async def replay():
            yield {"event": "done", "data": json.dumps({"tree": tree.model_dump()})}

        return EventSourceResponse(replay())

    async def stream():
        queue = builder.subscribe()
        try:
            while True:
                name, data = await queue.get()
                yield {"event": name, "data": json.dumps(data)}
                if name in ("done", "error"):
                    break
        finally:
            builder.unsubscribe(queue)

    return EventSourceResponse(stream())


@app.post("/api/events", status_code=204)
async def api_events(request: Request) -> Response:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "content-type must be application/json")
    raw = await request.body()
    if len(raw) > MAX_EVENTS_BYTES:
        raise HTTPException(413, "too many events at once")
    try:
        body = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise HTTPException(400, "expected a JSON array of events")
    if not isinstance(body, list) or not all(isinstance(e, dict) for e in body):
        raise HTTPException(400, "expected a JSON array of event objects")
    events.append_events(body)
    return Response(status_code=204)


@app.get("/api/models")
async def api_models() -> dict:
    return {"default": default_model(), "models": await list_models()}


@app.get("/api/recent")
async def api_recent() -> list[dict]:
    return cache.recent_trees(20)


WEB_DIR.mkdir(parents=True, exist_ok=True)
class RevalidatingStaticFiles(StaticFiles):
    """Static files the browser must revalidate on every load. Without this the
    browser kept serving stale app.js/style.css after edits, which made fixed
    bugs look unfixed. Local-only app, so the extra 304 round-trips cost nothing."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", RevalidatingStaticFiles(directory=str(WEB_DIR), html=True), name="web")
