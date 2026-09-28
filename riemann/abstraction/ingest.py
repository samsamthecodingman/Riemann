"""Ingest: text | file | url -> (title, clean markdown text).

Normalises whatever Sam pastes, uploads or links into a single markdown
string plus a best-effort title, so chunk.py has one uniform input shape.
"""

from __future__ import annotations

import io
import re

import httpx


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.*)", line)
        if heading:
            return heading.group(1).strip()[:200]
        return line[:200]
    return fallback


def from_text(text: str, title: str | None = None) -> tuple[str, str]:
    """Plain pasted text/markdown."""
    text = text.strip()
    return (title or _title_from_text(text, "Untitled"), text)


def from_file(filename: str, content: bytes) -> tuple[str, str]:
    """A .md/.txt/.pdf upload."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _from_pdf(filename, content)
    # .md / .txt / anything else: decode as text
    text = content.decode("utf-8", errors="replace").strip()
    title = _title_from_text(text, filename)
    return (title, text)


def _from_pdf(filename: str, content: bytes) -> tuple[str, str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            parts.append(page_text.strip())
    text = "\n\n".join(parts).strip()
    title = _title_from_text(text, filename)
    return (title, text)


async def from_url(url: str) -> tuple[str, str]:
    """Fetch a URL and extract clean markdown via trafilatura."""
    import trafilatura

    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers={"User-Agent": "riemann/0.1"})
        resp.raise_for_status()
        html = resp.text

    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        with_metadata=False,
        url=url,
    )
    if not extracted:
        raise ValueError(f"Could not extract readable content from {url}")

    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = (metadata.title if metadata and metadata.title else None) or _title_from_text(
        extracted, url
    )
    return (title, extracted.strip())
