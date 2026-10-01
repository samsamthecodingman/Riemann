"""Layout-aware PDF text extraction with pdfplumber.

pypdf returns a page's words in the order they were drawn, which loses
paragraph breaks, reads two columns across the gutter, and turns a table into
a run of cells. This reads word positions instead:

- running headers and footers (the same line, digits blanked, in the top or
  bottom margin of most pages) and page numbers are dropped; page 1's top is kept
- a two-column page is read left column then right column, with lines that span
  both (a title, a full-width table) in their place
- lines are joined into paragraphs; a bigger vertical gap, a first-line indent,
  a bullet, or a size change starts a new one; hyphenated line ends are rejoined
- bullet glyphs become markdown "- " items (a wrapped line joins its item)
- larger type becomes a markdown heading
- a ruled table becomes a markdown table (an unruled one stays prose)
- a paragraph cut by a page break is joined across it

`extract_pages` raises on anything unexpected; ingest falls back to pypdf.
"""

from __future__ import annotations

import io
import re
import statistics
from dataclasses import dataclass, field

MAX_LAYOUT_PAGES = 400  # pdfplumber is slower than pypdf; a book goes the fast way
MARGIN = 0.08  # top and bottom share of the page searched for running headers and footers
_BULLET_GLYPHS = "●○•▪◦■□‣∙⁃◆◇▸►➢✓✔·"
_BULLET_RE = re.compile(rf"^(?:[{re.escape(_BULLET_GLYPHS)}]|[-–—*])\s+(?=\S)")
_NUMBERED_RE = re.compile(r"^(?:\d{1,3}|[a-zA-Z])[.)]\s+(?=\S)")
_TERMINAL_RE = re.compile(r"[.!?:][\"')\]”’]*$")
_PAGE_NO_RE = re.compile(r"^(?:page\s*)?[-–]?\s*(?:\d{1,4}|[ivxlc]{1,6})\s*(?:of\s*\d{1,4})?\s*[-–]?$", re.I)


@dataclass
class _Line:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    col: int = 0  # 0 = full width or single column, 1 = left, 2 = right


@dataclass
class _Table:
    top: float
    bottom: float
    rows: list[list[str]]


@dataclass
class _Page:
    width: float
    height: float
    lines: list[_Line] = field(default_factory=list)
    tables: list[_Table] = field(default_factory=list)
    gutter: tuple[float, float] | None = None


def _edge_key(text: str) -> str:
    return re.sub(r"\d+", "#", text.strip().lower())


def _cluster_rows(words: list[dict]) -> list[list[dict]]:
    """Words sharing a baseline (within ~a third of the type size), each row left to right."""
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        for row in rows[-3:]:
            if abs(row[0]["top"] - w["top"]) <= max(2.0, 0.35 * w["size"]):
                row.append(w)
                break
        else:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["x0"])
    rows.sort(key=lambda r: r[0]["top"])
    return rows


def _find_gutter(words: list[dict], width: float) -> tuple[float, float] | None:
    """The empty vertical strip between two text columns, if the page has one:
    a band (at least 10 pt wide) in the middle of the page that almost no word
    crosses, with real text on both sides."""
    if len(words) < 40:
        return None
    lo, hi = int(width * 0.3), int(width * 0.7)
    cover = [0] * (hi - lo + 1)
    for w in words:
        for x in range(max(lo, int(w["x0"])), min(hi, int(w["x1"]) + 1)):
            cover[x - lo] += 1
    limit = max(1, int(len(words) * 0.02))
    best: tuple[int, int] | None = None
    start = None
    for i, c in enumerate(cover + [limit + 1]):
        if c <= limit and start is None:
            start = i
        elif c > limit and start is not None:
            if i - start >= 10 and (best is None or i - start > best[1] - best[0]):
                best = (start, i)
            start = None
    if best is None:
        return None
    g0, g1 = lo + best[0], lo + best[1]
    left = sum(1 for w in words if w["x1"] <= g0)
    right = sum(1 for w in words if w["x0"] >= g1)
    if left < 0.25 * len(words) or right < 0.25 * len(words):
        return None
    return float(g0), float(g1)


def _lines_of(words: list[dict], gutter: tuple[float, float] | None) -> list[_Line]:
    out: list[_Line] = []
    for row in _cluster_rows(words):
        if gutter is not None:
            g0, g1 = gutter
            crosses = any(w["x0"] < g1 and w["x1"] > g0 for w in row)
            if not crosses:
                halves = [(1, [w for w in row if w["x1"] <= g0]), (2, [w for w in row if w["x0"] >= g1])]
            else:
                halves = [(0, row)]
        else:
            halves = [(0, row)]
        for col, part in halves:
            if not part:
                continue
            out.append(
                _Line(
                    text=" ".join(w["text"] for w in part),
                    x0=part[0]["x0"],
                    x1=max(w["x1"] for w in part),
                    top=min(w["top"] for w in part),
                    bottom=max(w["bottom"] for w in part),
                    size=max(w["size"] for w in part),
                    col=col,
                )
            )
    return out


def _table_rows(table) -> list[list[str]] | None:
    """The table's cells, or None when this is a frame or drawing rather than a table: fewer than
    two rows or columns, mostly empty cells, or a banner row (one filled cell across several
    columns) as in a slide whose whole body is boxed."""
    raw = table.extract()
    rows = [[" ".join((c or "").split()).replace("|", "\\|") for c in row] for row in raw or []]
    rows = [r for r in rows if any(r)]
    ncols = max((len(r) for r in rows), default=0)
    if len(rows) < 2 or ncols < 2:
        return None
    cells = [c for r in rows for c in r]
    if sum(1 for c in cells if c) < 0.7 * len(cells):
        return None  # mostly empty
    full = sum(1 for r in rows if sum(1 for c in r if c) >= ncols)
    if full < 0.6 * len(rows):
        return None  # banner or merged rows: a boxed slide body, not a grid of values
    return rows


def _read_page(page) -> _Page:
    data = _Page(width=float(page.width), height=float(page.height))
    tables: list[_Table] = []
    boxes: list[tuple[float, float, float, float]] = []
    try:
        found = page.find_tables()
    except Exception:  # noqa: BLE001 - a page whose rulings confuse the finder is read as text
        found = []
    for t in found:
        rows = _table_rows(t)
        if rows is not None:
            x0, top, x1, bottom = t.bbox
            tables.append(_Table(top=top, bottom=bottom, rows=rows))
            boxes.append((x0, top, x1, bottom))
    words = page.extract_words(x_tolerance=1.5, y_tolerance=3, extra_attrs=["size"])
    for w in words:
        w["text"] = re.sub(r"\(cid:\d+\)", "", w["text"])  # glyphs the font gave no Unicode for
    words = [w for w in words if w["text"]]

    def in_table(w: dict) -> bool:
        cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
        return any(b[0] - 1 <= cx <= b[2] + 1 and b[1] - 1 <= cy <= b[3] + 1 for b in boxes)

    words = [w for w in words if not in_table(w)]
    data.tables = tables
    data.gutter = _find_gutter(words, data.width)
    data.lines = _lines_of(words, data.gutter)
    return data


def _margin_drop_keys(pages: list[_Page]) -> set[str]:
    """Edge-line keys that repeat in the top or bottom margin of at least half the pages (and 3)."""
    if len(pages) < 3:
        return set()
    counts: dict[str, int] = {}
    for pg in pages:
        keys = set()
        for ln in pg.lines:
            if (ln.top < pg.height * MARGIN or ln.bottom > pg.height * (1 - MARGIN)) and len(ln.text) <= 120:
                keys.add(_edge_key(ln.text))
        for k in keys:
            counts[k] = counts.get(k, 0) + 1
    need = max(3, (len(pages) + 1) // 2)
    return {k for k, n in counts.items() if n >= need or (n >= 3 and _PAGE_NO_RE.match(k.replace("#", "1")))}


def _body_size(pages: list[_Page]) -> float:
    sizes: dict[float, int] = {}
    for pg in pages:
        for ln in pg.lines:
            sizes[round(ln.size, 1)] = sizes.get(round(ln.size, 1), 0) + len(ln.text)
    return max(sizes, key=sizes.get) if sizes else 11.0


def _join(prev: str, nxt: str) -> str:
    if re.search(r"[A-Za-z]-$", prev) and nxt[:1].islower():
        return prev[:-1] + nxt
    return prev + " " + nxt


def _blocks_of(lines: list[_Line], body: float, col_x1: float) -> list[tuple[str, str]]:
    """Lines of one column (top to bottom) -> [(kind, text)], kind "p", "h1".."h3" or "li"."""
    if not lines:
        return []
    pitches = [b.top - a.top for a, b in zip(lines, lines[1:]) if 0 < b.top - a.top < 2.5 * max(a.size, b.size)]
    pitch = statistics.median(pitches) if pitches else body * 1.25
    blocks: list[tuple[str, str]] = []
    cur_kind = ""
    cur_text = ""
    prev: _Line | None = None
    item_x0 = 0.0

    def close() -> None:
        nonlocal cur_kind, cur_text
        if cur_text:
            blocks.append((cur_kind, cur_text))
        cur_kind, cur_text = "", ""

    for ln in lines:
        text = ln.text.strip()
        heading = ln.size >= body * 1.2 and len(text) <= 140 and not _TERMINAL_RE.search(text[:-1] or "")
        level = "h1" if ln.size >= body * 1.7 else "h2" if ln.size >= body * 1.35 else "h3"
        bullet = _BULLET_RE.match(text)
        numbered = _NUMBERED_RE.match(text)
        gap = (ln.top - prev.bottom) if prev is not None else 0.0
        big_gap = prev is not None and (ln.top - prev.top) > pitch * 1.3 + 0.5
        indent = prev is not None and ln.x0 > prev.x0 + body * 0.8 and cur_kind == "p" and bool(_TERMINAL_RE.search(prev.text))
        short_end = (
            prev is not None
            and cur_kind == "p"
            and bool(_TERMINAL_RE.search(prev.text))
            and prev.x1 < col_x1 - 0.3 * max(1.0, col_x1 - lines[0].x0)
            and text[:1].isupper()
        )
        if heading:
            if cur_kind == level and not big_gap and prev is not None and abs(prev.size - ln.size) < 0.6:
                cur_text = _join(cur_text, text)
            else:
                close()
                cur_kind, cur_text = level, text
        elif bullet or numbered:
            close()
            if bullet:
                cur_kind, cur_text = "li", text[bullet.end():].strip()
                item_x0 = ln.x0
            else:
                cur_kind, cur_text = "li", f"{text[:numbered.end()].strip()} {text[numbered.end():].strip()}"
                item_x0 = ln.x0
        elif cur_kind == "li" and not big_gap and ln.x0 >= item_x0 - 1:
            cur_text = _join(cur_text, text)
        elif cur_kind == "p" and not big_gap and not indent and not short_end and (prev is None or abs(prev.size - ln.size) < 0.6):
            cur_text = _join(cur_text, text)
        else:
            close()
            cur_kind, cur_text = "p", text
        prev = ln
    close()
    return blocks


def _page_blocks(pg: _Page, drop: set[str], first: bool, body: float) -> list[tuple[str, str]]:
    lines = [
        ln
        for ln in pg.lines
        if not (
            _edge_key(ln.text) in drop
            and (ln.top < pg.height * MARGIN or ln.bottom > pg.height * (1 - MARGIN))
            and not (first and ln.top < pg.height * MARGIN and ln.size >= body * 1.1)  # page 1's title stays
        )
    ]
    # Reading order: a band is the run of column lines between two full-width items (lines that
    # span the gutter, or tables); inside a band the left column is read, then the right.
    seps = [(ln.top, ln.bottom, "line", ln) for ln in lines if ln.col == 0] + [(t.top, t.bottom, "table", t) for t in pg.tables]
    seps.sort(key=lambda s: s[0])
    cols = [ln for ln in lines if ln.col != 0]
    out: list[tuple[str, str]] = []
    col_x1 = {1: pg.gutter[0] if pg.gutter else pg.width, 2: pg.width - 36, 0: pg.width - 36}

    def flush_band(upper: float, lower: float) -> None:
        for c in (1, 2):
            band = sorted((ln for ln in cols if ln.col == c and upper <= ln.top < lower), key=lambda ln: ln.top)
            out.extend(_blocks_of(band, body, col_x1[c]))

    run: list[_Line] = []  # consecutive full-width lines, read as one stream
    cursor = -1.0

    def flush_run() -> None:
        nonlocal run
        out.extend(_blocks_of(run, body, pg.width - 36))
        run = []

    for top, bottom, kind, item in seps:
        if any(cursor <= ln.top < top for ln in cols):
            flush_run()
            flush_band(cursor, top)
        if kind == "line":
            run.append(item)
            cursor = max(cursor, top)
        else:
            flush_run()
            out.append(("table", _markdown_table(item.rows)))
            cursor = max(cursor, bottom)
    flush_run()
    flush_band(cursor, 1e9)
    return out


def _markdown_table(rows: list[list[str]]) -> str:
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    def fmt(r: list[str]) -> str:
        return "| " + " | ".join(r) + " |"

    return "\n".join([fmt(rows[0]), fmt(["---"] * width), *(fmt(r) for r in rows[1:])])


def _render(pages: list[list[tuple[str, str]]]) -> str:
    merged: list[tuple[str, str]] = []
    for page_blocks in pages:
        for i, (kind, text) in enumerate(page_blocks):
            if (
                i == 0
                and merged
                and kind == "p"
                and merged[-1][0] == "p"
                and not _TERMINAL_RE.search(merged[-1][1])
                and text[:1].islower()
            ):
                merged[-1] = ("p", _join(merged[-1][1], text))  # a paragraph cut by the page break
            else:
                merged.append((kind, text))
    out: list[str] = []
    prev_kind = ""
    for kind, text in merged:
        if kind.startswith("h"):
            out.append(("#" * int(kind[1]) + " " + text))
        elif kind == "li":
            item = "- " + text if not _NUMBERED_RE.match(text) else text
            if prev_kind == "li":
                out[-1] = out[-1] + "\n" + item
            else:
                out.append(item)
        else:
            out.append(text)
        prev_kind = kind
    return "\n\n".join(out)


def extract_pages(content: bytes) -> str:
    """The document's text as markdown-ish paragraphs, lists, headings and tables.
    Raises on anything unexpected (the caller falls back to pypdf)."""
    import pdfplumber

    pages: list[_Page] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        if len(pdf.pages) > MAX_LAYOUT_PAGES:
            raise ValueError("too many pages for layout extraction")
        for page in pdf.pages:
            pages.append(_read_page(page))
            page.flush_cache()
    body = _body_size(pages)
    drop = _margin_drop_keys(pages)
    blocks = [_page_blocks(pg, drop, i == 0, body) for i, pg in enumerate(pages)]
    return _render(blocks)
