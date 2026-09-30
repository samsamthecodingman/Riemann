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
    if lower.endswith(".pdf") or content[:5] == b"%PDF-":
        try:
            return _from_pdf(filename, content)
        except Exception as exc:  # noqa: BLE001 - corrupt/encrypted PDF
            raise ValueError(f"could not read that PDF ({type(exc).__name__})") from exc
    if lower.endswith(".docx"):
        return _from_docx(filename, content)
    if content[:4] == b"PK\x03\x04" or b"\x00" in content[:4096]:
        raise ValueError("that file type is not supported; use .pdf, .docx, .md or .txt")
    # .md / .txt / anything else: decode as text
    text = normalise_text(content.decode("utf-8", errors="replace"))
    title = _title_from_text(text, filename)
    return (title, text)


def _edge_key(line: str) -> str:
    """A page line with its digits blanked, so "Page 3 of 12" and "Page 4 of 12"
    are the same running header/footer."""
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_running_headers(pages: list[str]) -> list[str]:
    """Drop lines that repeat at the top or bottom of most pages (running
    titles, "Page 3 of 12", confidential notices). A line counts when, digits
    blanked, it appears within the first or last 2 lines of at least half the
    pages (and at least 3). Needs 3+ pages; body lines are never touched, and
    the first page's top lines (the document title) are kept."""
    if len(pages) < 3:
        return pages
    edges: list[list[str]] = []
    counts: dict[str, int] = {}
    for page in pages:
        lines = [ln for ln in page.split("\n") if ln.strip()]
        keys = {_edge_key(ln) for ln in lines[:2] + lines[-2:] if len(ln.strip()) <= 120}
        edges.append(lines)
        for k in keys:
            counts[k] = counts.get(k, 0) + 1
    need = max(3, (len(pages) + 1) // 2)
    repeated = {k for k, n in counts.items() if n >= need}
    if not repeated:
        return pages
    out: list[str] = []
    for pi, lines in enumerate(edges):
        n = len(lines)
        # The first page's top is kept: it is usually the document's own title,
        # which the running header repeats.
        kept = [
            ln
            for i, ln in enumerate(lines)
            if not (((i < 2 and pi > 0) or i >= n - 2) and _edge_key(ln) in repeated and len(ln.strip()) <= 120)
        ]
        out.append("\n".join(kept))
    return out


def _from_pdf(filename: str, content: bytes) -> tuple[str, str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text.strip())
    parts = strip_running_headers(pages)
    text = normalise_text("\n\n".join(p for p in parts if p.strip()))
    title = _title_from_text(text, filename)
    return (title, text)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph_text(p) -> str:
    out: list[str] = []
    for el in p.iter():
        if el.tag == _W + "t":
            out.append(el.text or "")
        elif el.tag == _W + "tab":
            out.append(" ")
        elif el.tag in (_W + "br", _W + "cr"):
            out.append("\n")
    return "".join(out).strip()


def _docx_blocks(parent, lines: list[str]) -> None:
    for el in parent:
        if el.tag == _W + "p":
            text = _docx_paragraph_text(el)
            if not text:
                lines.append("")
                continue
            ppr = el.find(_W + "pPr")
            style = ""
            is_list = False
            if ppr is not None:
                st = ppr.find(_W + "pStyle")
                if st is not None:
                    style = (st.get(_W + "val") or "").lower()
                is_list = ppr.find(_W + "numPr") is not None
            m = re.match(r"heading\s*(\d)", style)
            if style == "title":
                lines.append(f"# {text}")
            elif m:
                lines.append(f"{'#' * min(int(m.group(1)), 6)} {text}")
            elif is_list or style.startswith("listparagraph"):
                lines.append(f"- {text}")
            else:
                lines.append(text)
        elif el.tag == _W + "tbl":
            for row in el.iter(_W + "tr"):
                cells = []
                for cell in row.findall(_W + "tc"):
                    cells.append(" ".join(_docx_paragraph_text(p) for p in cell.iter(_W + "p")).strip())
                if any(cells):
                    lines.append("- " + " | ".join(c for c in cells if c))
            lines.append("")
        elif el.tag in (_W + "sdt", _W + "sdtContent", _W + "body"):
            _docx_blocks(el, lines)


def _from_docx(filename: str, content: bytes) -> tuple[str, str]:
    """A .docx upload, read with the standard library only (zip + XML):
    headings, list items, paragraphs and table rows, in document order."""
    import zipfile
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except Exception as exc:  # noqa: BLE001 - not a real docx
        raise ValueError("could not read that Word file; is it a .docx?") from exc
    body = root.find(_W + "body")
    lines: list[str] = []
    _docx_blocks(body if body is not None else root, lines)
    # One blank line between blocks; consecutive list items stay together.
    out: list[str] = []
    prev_list = False
    for ln in lines:
        if not ln:
            continue
        is_list = ln.startswith("- ")
        if out and not (is_list and prev_list):
            out.append("")
        out.append(ln)
        prev_list = is_list
    text = normalise_text("\n".join(out))
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
