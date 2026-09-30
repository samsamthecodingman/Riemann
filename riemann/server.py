"""FastAPI app: the Riemann API, plus serving web/ statically at /.

See docs/v1-build-spec.md, "API (server.py)" for the contract. web/ is
owned by a separate worker (the frontend); this module only mounts it if
present, and creates an empty web/ dir so the server still starts if it
isn't there yet.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from riemann import events
from riemann.abstraction import build, cache, ingest
from riemann.abstraction.summarise import BLOCKED_MODELS, default_model, get_summariser, list_models

app = FastAPI(title="Riemann")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.post("/api/abstract")
async def api_abstract(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")

    model: str | None = None
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        model = form.get("model") or None
        upload = form.get("file")
        if upload is None:
            raise HTTPException(400, "expected a 'file' field")
        content = await upload.read()
        title, text = ingest.from_file(upload.filename or "upload", content)
    else:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(400, "expected JSON body with 'text' or 'url'")
        model = (body or {}).get("model") or None
        url = (body or {}).get("url")
        raw_text = (body or {}).get("text")
        if url:
            try:
                title, text = await ingest.from_url(url)
            except Exception as exc:
                raise HTTPException(400, f"could not fetch url: {exc}") from exc
        elif raw_text:
            title, text = ingest.from_text(raw_text)
        else:
            raise HTTPException(400, "expected 'text' or 'url' in the JSON body, or a 'file' upload")

    if not text.strip():
        raise HTTPException(400, "no content to abstract")

    model = model or default_model()
    if model in BLOCKED_MODELS:
        raise HTTPException(400, f"model '{model}' is not allowed")
    tree_id = cache.tree_id_for(text, model)

    if cache.exists(tree_id):
        return {"tree_id": tree_id, "cached": True}

    if build.get_builder(tree_id) is None:
        summariser = get_summariser(model=model)
        builder = build.start_build(tree_id, title, text, summariser)
        builder.tree.model = model

    return {"tree_id": tree_id, "cached": False}


@app.get("/api/tree/{tree_id}")
async def api_tree(tree_id: str) -> dict:
    builder = build.get_builder(tree_id)
    if builder is not None:
        return builder.tree.model_dump()
    tree = cache.load_tree(tree_id)
    if tree is not None:
        return tree.model_dump()
    raise HTTPException(404, "no such tree")


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
    body = await request.json()
    if not isinstance(body, list):
        raise HTTPException(400, "expected a JSON array of events")
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
