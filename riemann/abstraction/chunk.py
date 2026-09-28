"""Chunk: markdown -> leaves.

Splits on headings, then packs paragraphs into leaves of <= ~350 words.
Code fences, numbered procedures and $$...$$ display-math blocks become
their own atomic leaves (never summarised, shown verbatim). A tiny
document (<= ~60 words) becomes a single leaf.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

MAX_LEAF_WORDS = 350
TINY_DOC_WORDS = 60

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)")
_NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s+\S")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


class Leaf(BaseModel):
    text: str
    words: int
    source_span: tuple[int, int]
    atomic: bool = False
    heading_path: tuple[str, ...] = ()


def word_count(text: str) -> int:
    return len(text.split())


class _Block(BaseModel):
    text: str
    span: tuple[int, int]
    kind: str  # "heading" | "atomic" | "paragraph"
    level: int = 0  # for headings


def _split_blocks(text: str) -> list[_Block]:
    """Split raw text into ordered blocks: headings, atomic blocks, paragraphs."""
    lines = text.splitlines(keepends=True)
    blocks: list[_Block] = []
    offset = 0
    i = 0
    n = len(lines)
    buf_start: int | None = None
    buf_lines: list[str] = []

    def flush_paragraph(end_offset: int) -> None:
        nonlocal buf_start, buf_lines
        if buf_lines:
            raw = "".join(buf_lines)
            stripped = raw.strip()
            if stripped:
                start = buf_start if buf_start is not None else end_offset
                blocks.append(_Block(text=stripped, span=(start, start + len(stripped)), kind="paragraph"))
        buf_start = None
        buf_lines = []

    while i < n:
        line = lines[i]
        line_start = offset
        line_end = offset + len(line)

        heading_match = _HEADING_RE.match(line.strip("\n"))
        if heading_match:
            flush_paragraph(line_start)
            stripped = line.strip()
            blocks.append(
                _Block(
                    text=stripped,
                    span=(line_start, line_start + len(stripped)),
                    kind="heading",
                    level=len(heading_match.group(1)),
                )
            )
            offset = line_end
            i += 1
            continue

        if _FENCE_RE.match(line.strip()):
            flush_paragraph(line_start)
            fence_marker = line.strip()[:3]
            block_lines = [line]
            j = i + 1
            j_offset = line_end
            while j < n:
                block_lines.append(lines[j])
                j_offset += len(lines[j])
                if lines[j].strip().startswith(fence_marker):
                    j += 1
                    break
                j += 1
            raw = "".join(block_lines)
            blocks.append(
                _Block(text=raw.strip("\n"), span=(line_start, line_start + len(raw.rstrip("\n"))), kind="atomic")
            )
            offset = j_offset
            i = j
            continue

        if line.strip() == "" :
            flush_paragraph(line_start)
            offset = line_end
            i += 1
            continue

        if buf_start is None:
            buf_start = line_start
        buf_lines.append(line)
        offset = line_end
        i += 1

    flush_paragraph(offset)
    return blocks


def _expand_math_and_procedures(blocks: list[_Block]) -> list[_Block]:
    """Within paragraph blocks, pull out $$...$$ math and numbered-list
    procedures as their own atomic blocks."""
    out: list[_Block] = []
    for block in blocks:
        if block.kind != "paragraph":
            out.append(block)
            continue

        text = block.text
        start_off = block.span[0]

        # Whole-block numbered procedure: >=2 consecutive numbered lines.
        lines = text.splitlines()
        numbered_lines = sum(1 for ln in lines if _NUMBERED_RE.match(ln))
        if numbered_lines >= 2 and numbered_lines >= len(lines) - 1:
            out.append(_Block(text=text, span=block.span, kind="atomic"))
            continue

        # Extract $$...$$ display math spans.
        cursor = 0
        pieces: list[tuple[str, bool]] = []  # (text, is_math)
        for m in re.finditer(r"\$\$.*?\$\$", text, flags=re.DOTALL):
            if m.start() > cursor:
                pieces.append((text[cursor:m.start()], False))
            pieces.append((text[m.start():m.end()], True))
            cursor = m.end()
        if cursor < len(text):
            pieces.append((text[cursor:], False))

        if len(pieces) == 1 and not pieces[0][1]:
            out.append(block)
            continue

        pos = start_off
        for piece_text, is_math in pieces:
            piece_stripped = piece_text.strip()
            # locate piece within original text to get an accurate span
            idx = text.find(piece_text, pos - start_off if pos - start_off >= 0 else 0)
            if idx == -1:
                idx = pos - start_off
            piece_start = start_off + idx
            piece_end = piece_start + len(piece_text)
            pos = piece_end
            if not piece_stripped:
                continue
            out.append(
                _Block(
                    text=piece_stripped,
                    span=(piece_start, piece_start + len(piece_stripped)),
                    kind="atomic" if is_math else "paragraph",
                )
            )
    return out


def _split_long_paragraph(block: _Block) -> list[_Block]:
    """Split a paragraph over MAX_LEAF_WORDS into chunks of <= MAX_LEAF_WORDS
    words, preferring to break at a sentence end near the cap when there is
    one, else a hard word-count cut (robust even with no punctuation at all,
    e.g. a single very long run-on line)."""
    if word_count(block.text) <= MAX_LEAF_WORDS:
        return [block]

    text = block.text
    base = block.span[0]
    words = list(re.finditer(r"\S+", text))
    n = len(words)
    out: list[_Block] = []
    i = 0
    while i < n:
        j = min(i + MAX_LEAF_WORDS, n)
        if j < n:
            search_start = max(i + 1, i + int(MAX_LEAF_WORDS * 0.6))
            best = None
            for k in range(search_start, j + 1):
                if words[k - 1].group().endswith((".", "!", "?", '."', '!"', '?"', ".'", "!'", "?'")):
                    best = k
            if best:
                j = best
        start_char = words[i].start()
        end_char = words[j - 1].end()
        chunk_text = text[start_char:end_char]
        out.append(_Block(text=chunk_text, span=(base + start_char, base + end_char), kind="paragraph"))
        i = j
    return out or [block]


def chunk(text: str) -> list[Leaf]:
    """Turn markdown source text into an ordered list of leaves."""
    text = text if text.endswith("\n") else text + "\n"

    if word_count(text) <= TINY_DOC_WORDS:
        stripped = text.strip()
        return [Leaf(text=stripped, words=word_count(stripped), source_span=(0, len(stripped)), atomic=False, heading_path=())]

    blocks = _split_blocks(text)
    blocks = _expand_math_and_procedures(blocks)

    # Expand over-long paragraphs.
    expanded: list[_Block] = []
    for b in blocks:
        if b.kind == "paragraph":
            expanded.extend(_split_long_paragraph(b))
        else:
            expanded.append(b)
    blocks = expanded

    leaves: list[Leaf] = []
    heading_stack: list[tuple[int, str]] = []  # (level, text)

    def current_path() -> tuple[str, ...]:
        return tuple(h[1] for h in heading_stack)

    # Pack consecutive paragraph blocks (within the same heading section)
    # into leaves of <= MAX_LEAF_WORDS.
    pack_texts: list[str] = []
    pack_words = 0
    pack_start: int | None = None
    pack_end: int | None = None
    pack_path: tuple[str, ...] = ()

    def flush_pack() -> None:
        nonlocal pack_texts, pack_words, pack_start, pack_end
        if pack_texts:
            joined = "\n\n".join(pack_texts)
            leaves.append(
                Leaf(
                    text=joined,
                    words=word_count(joined),
                    source_span=(pack_start, pack_end),
                    atomic=False,
                    heading_path=pack_path,
                )
            )
        pack_texts = []
        pack_words = 0
        pack_start = None
        pack_end = None

    for b in blocks:
        if b.kind == "heading":
            flush_pack()
            while heading_stack and heading_stack[-1][0] >= b.level:
                heading_stack.pop()
            heading_stack.append((b.level, b.text.lstrip("#").strip()))
            continue

        if b.kind == "atomic":
            flush_pack()
            leaves.append(
                Leaf(text=b.text, words=word_count(b.text), source_span=b.span, atomic=True, heading_path=current_path())
            )
            continue

        # paragraph
        b_words = word_count(b.text)
        path = current_path()
        if pack_texts and (pack_words + b_words > MAX_LEAF_WORDS or path != pack_path):
            flush_pack()
        if not pack_texts:
            pack_path = path
            pack_start = b.span[0]
        pack_texts.append(b.text)
        pack_words += b_words
        pack_end = b.span[1]

    flush_pack()

    if not leaves:
        stripped = text.strip()
        leaves = [Leaf(text=stripped, words=word_count(stripped), source_span=(0, len(stripped)), atomic=False, heading_path=())]

    return leaves
