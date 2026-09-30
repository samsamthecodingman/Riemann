"""Ingest: text | file | url -> (title, clean markdown text).

Normalises whatever Sam pastes, uploads or links into a single markdown
string plus a best-effort title, so chunk.py has one uniform input shape.
"""

from __future__ import annotations

import io
import re

import httpx

from riemann.abstraction.normalise import normalise_text


def _shorten(line: str, limit: int = 90) -> str:
    """A title from a long first line: cut at a word boundary."""
    if len(line) <= limit:
        return line
    cut = line[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-–")
    return cut + "…"


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.*)", line)
        if heading:
            return _shorten(heading.group(1).strip(), 200)
        return _shorten(line)
    return fallback


def from_text(text: str, title: str | None = None) -> tuple[str, str]:
    """Plain pasted text/markdown."""
    text = normalise_text(text)
    return (title or _title_from_text(text, "Untitled"), text)


def from_file(filename: str, content: bytes) -> tuple[str, str]:
    """A .md/.txt/.pdf upload."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _from_pdf(filename, content)
    # .md / .txt / anything else: decode as text
    text = normalise_text(content.decode("utf-8", errors="replace"))
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
    text = normalise_text("\n\n".join(parts))
    title = _title_from_text(text, filename)
    return (title, text)


def clean_url(url: str) -> str:
    """Trim a pasted link and add https:// when the scheme was left off
    ("example.com/page"). Other schemes are left for the fetch to refuse."""
    url = url.strip()
    if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    return url


def fetch_error_message(exc: Exception) -> str:
    """A short human sentence for a failed fetch (no httpx boilerplate)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"the site answered {exc.response.status_code}"
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "could not connect to that address"
    if isinstance(exc, httpx.TimeoutException):
        return "the site took too long to answer"
    if isinstance(exc, httpx.UnsupportedProtocol):
        return "only http and https links work"
    if isinstance(exc, httpx.InvalidURL):
        return "that does not look like a valid link"
    return str(exc) or type(exc).__name__


async def from_url(url: str) -> tuple[str, str]:
    """Fetch a URL and extract clean markdown via trafilatura."""
    import trafilatura

    url = clean_url(url)
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
    return (title, normalise_text(extracted))
