"""Text normalisation: repair extracted text before it is hashed and chunked.

Text pasted from a PDF (or extracted from one) often arrives with every word
on its own line, hard line wraps in mid-sentence, bullet glyphs standing alone
as "paragraphs", non-breaking hyphens and soft hyphens. Chunked as-is, each
word becomes its own paragraph and the reader shows one word per line.
`normalise_text` rejoins that into real paragraphs and markdown lists, and
leaves well-formed prose and markdown unchanged (apart from character
clean-up). It is applied to pasted text, uploaded files and fetched URLs
alike, in ingest.py, so the tree id is a hash of the *repaired* text.
"""

from __future__ import annotations

import re
import statistics

# Strong bullet glyphs: always start a list item wherever they appear.
_BULLET_GLYPHS = "●○•▪◦■□‣∙⁃◆◇▸►➢✓✔"
_BULLET_CLASS = f"[{re.escape(_BULLET_GLYPHS)}]"
_BULLET_LINE_RE = re.compile(rf"^\s*{_BULLET_CLASS}\s*")
_MID_BULLET_RE = re.compile(rf"(?<=\S)[ \t]+(?={_BULLET_CLASS}[ \t]+\S)")
_DASH_BULLET_RE = re.compile(r"^\s*[–—]\s+(?=\S)")
_MD_BULLET_RE = re.compile(r"^\s*[-*+]\s+\S")
_NUMBERED_START_RE = re.compile(r"^\s*(\d{1,3}|[a-zA-Z])[.)]\s+\S")
_TERMINAL_RE = re.compile(r"[.!?][\"')\]”’]*$")
_MD_STRUCT_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d{1,3}[.)]\s|>|\||```|~~~)")

_CHAR_MAP = {
    "ﬀ": "ff",  # typographic ligatures: LaTeX and Word PDFs extract "ﬁ" for "fi"
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
    "‐": "-",
    "‑": "-",  # non-breaking hyphen
    "‒": "-",
    "­": "",  # soft hyphen
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "​": "",
    "‌": "",
    "‍": "",
    "⁠": "",
    "﻿": "",
    " ": "\n",
    " ": "\n\n",
    "\f": "\n\n",
    "\x0b": "\n",
}


def clean_characters(text: str) -> str:
    """Line endings, odd spaces/hyphens/zero-width characters, runs of spaces
    and tabs, trailing whitespace. Code fences are left byte-for-byte alone
    (apart from trailing whitespace); line structure is untouched."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(_CHAR_MAP.get(ch, ch) for ch in text)
    out: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            out.append(line.rstrip())
        elif in_fence:
            out.append(line.rstrip())
        else:
            lead = re.match(r"[ \t]*", line).group(0)
            body = re.sub(r"[ \t]+", " ", line.strip())
            out.append((lead.replace("\t", "    ") + body) if body else "")
    return "\n".join(out)


def _nonblank(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.strip()]


def looks_word_per_line(lines: list[str]) -> bool:
    """Nearly every non-blank line is a single word (or glyph): the
    "one word per paragraph" extraction shape."""
    nb = _nonblank(lines)
    if len(nb) < 20:
        return False
    short = sum(1 for ln in nb if len(ln.split()) <= 2)
    return short / len(nb) >= 0.85 and statistics.median(len(ln.split()) for ln in nb) <= 1


def looks_hard_wrapped(lines: list[str]) -> bool:
    """Prose broken into ~fixed-width lines mid-sentence (PDF-style): many
    medium-length lines, mostly not ending a sentence, with few blank lines."""
    nb = _nonblank(lines)
    prose = [ln for ln in nb if not _MD_STRUCT_RE.match(ln) and not _BULLET_LINE_RE.match(ln)]
    if len(prose) < 8:
        return False
    lengths = [len(ln) for ln in prose]
    median_len = statistics.median(lengths)
    if not 25 <= median_len <= 110:
        return False
    if statistics.mean(len(ln.split()) for ln in prose) < 5:
        return False
    unfinished = sum(1 for ln in prose if not _TERMINAL_RE.search(ln))
    blank_ratio = 1 - len(nb) / max(1, len(lines))
    return unfinished / len(prose) >= 0.55 and blank_ratio < 0.25


def _dehyphenate_join(prev: str, nxt: str) -> str:
    """Join two wrapped lines: "infor-" + "mation" -> "information"; else a space."""
    if re.search(r"[A-Za-z]-$", prev) and nxt[:1].islower():
        return prev[:-1] + nxt
    return prev + " " + nxt


def _emit_blocks(blocks: list[tuple[str, list[str]]]) -> str:
    """blocks: (kind, lines) with kind "p" or "list". Lists keep one item per
    line; every block is separated by a blank line."""
    out: list[str] = []
    for kind, items in blocks:
        if not items:
            continue
        out.append("\n".join(items) if kind == "list" else " ".join(items))
    return "\n\n".join(x for x in out if x.strip())


_ABBREVIATIONS = {"e.g.", "i.e.", "etc.", "vs.", "cf.", "fig.", "eq.", "no.", "dr.", "mr.", "mrs.", "ms.", "approx."}


def _ends_sentence(tok: str) -> bool:
    """A token that ends a sentence: terminal punctuation, but not an
    abbreviation, a bare number ("3."), or a very short dotted token."""
    if not _TERMINAL_RE.search(tok):
        return False
    core = tok.rstrip("\"')]”’").lower()
    if core in _ABBREVIATIONS or re.fullmatch(r"\d{1,3}[.]", core):
        return False
    return not (len(core) <= 3 and "." in core[:-1])


def _rejoin_tokens(lines: list[str]) -> str:
    """The word-per-line shape: each non-blank line is a token. The blank
    lines between tokens carry the structure: none = glued (a "." or "-" on
    its own line), one = a space, two or more = a paragraph break. Bullet
    glyph tokens start list items."""
    # (token, blank_run_before)
    toks: list[tuple[str, int]] = []
    run = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            run += 1
            continue
        toks.append((s, run if toks else 2))
        run = 0

    blocks: list[tuple[str, list[str]]] = []
    kind = "p"
    cur: list[str] = []  # for "p": [text]; for "list": items

    def close() -> None:
        nonlocal cur, kind
        if cur:
            blocks.append((kind, cur))
        cur = []
        kind = "p"

    def start_paragraph() -> None:
        close()
        cur.append("")

    start_paragraph()
    prev_tok = ""
    for i, (tok, gap) in enumerate(toks):
        nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
        if re.fullmatch(_BULLET_CLASS, tok):
            if kind != "list":
                close()
                kind = "list"
            cur.append("- ")
            prev_tok = tok
            continue
        if gap >= 2 and prev_tok and cur and cur[-1].strip():
            # explicit paragraph break
            start_paragraph()
        elif (
            prev_tok
            and _TERMINAL_RE.search(prev_tok)
            and re.fullmatch(r"\d{1,2}[.)]?", tok)
            and kind == "p"
            and gap >= 1
            and nxt[:1].isupper()
        ):
            # a numbered heading ("3." "Computational" ...) after a full stop
            start_paragraph()
        elif kind == "list" and prev_tok and _ends_sentence(prev_tok) and tok[:1].isupper():
            # a list item that ended in a full stop, followed by a capital: the list is over
            start_paragraph()
        if not cur:
            cur.append("")
        sep = "" if (gap == 0 or not cur[-1] or cur[-1].endswith(" ")) else " "
        cur[-1] = cur[-1] + sep + tok
        prev_tok = tok
    close()
    return _emit_blocks(blocks)


def _rejoin_wrapped(lines: list[str]) -> str:
    """Hard-wrapped prose (PDF-style): merge wrapped lines into paragraphs,
    keeping real paragraph breaks (blank lines; a sentence that ended a short
    line; a heading-like line) and list items on their own lines."""
    lengths = sorted(len(ln.strip()) for ln in lines if ln.strip())
    wide = lengths[int(len(lengths) * 0.9)] if lengths else 0

    def heading_like(t: str) -> bool:
        return (
            len(t) <= 60
            and len(t.split()) <= 8
            and t[:1].isupper()
            and not _TERMINAL_RE.search(t)
            and not t.endswith((",", ";", ":"))
        )

    blocks: list[tuple[str, list[str]]] = []
    kind = "p"
    cur: list[str] = []

    def close() -> None:
        nonlocal cur, kind
        if cur:
            blocks.append((kind, cur))
        cur = []
        kind = "p"

    def is_item_line(t: str) -> bool:
        return bool(_BULLET_LINE_RE.match(t) or _DASH_BULLET_RE.match(t) or re.match(r"^\s*([-*+]|\d{1,3}[.)]|[a-zA-Z][.)])\s+\S", t))

    prev = ""
    for idx, raw in enumerate(lines):
        s = raw.strip()
        if not s:
            close()
            prev = ""
            continue
        if s.startswith(">"):
            # A quoted reply (email, markdown blockquote): keep its own lines. Joining them
            # put ">" markers in the middle of a paragraph.
            if kind != "quote":
                close()
                kind = "quote"
            cur.append(s)
            prev = s
            continue
        if kind == "quote":
            close()
        if _EMAIL_HEADER_RE.match(s):
            close()  # From:/To:/Subject: lines are separate facts, not a wrapped sentence
            blocks.append(("p", [s]))
            prev = s
            continue
        nxt = next((x.strip() for x in lines[idx + 1:] if x.strip()), "")
        md_bullet = re.match(r"^\s*[-*+]\s+(?=\S)", s)
        glyph = _BULLET_LINE_RE.match(s)
        dash = _DASH_BULLET_RE.match(s)
        numbered = re.match(r"^(\d{1,3}|[a-zA-Z])[.)]\s+(?=\S)", s)
        if md_bullet or glyph or dash:
            body = s[(md_bullet or glyph or dash).end():]
            if kind != "list":
                close()
                kind = "list"
            cur.append("- " + body)
        elif (
            (hmatch := re.match(r"^(\d{1,2}(?:\.\d{1,2})*)[.)]?\s+(?=\S)", s))
            and kind != "list"
            and heading_like(s[hmatch.end():])
            and nxt
            and not is_item_line(nxt)
            and nxt[:1].isupper()
        ):
            # "2. Method" / "2.1 Data" on a line of its own, followed by prose:
            # a numbered heading, not a one-item list that swallows the next
            # paragraph. Emitted as a markdown heading so the chunker keeps
            # the section ("2." -> ##, "2.1" -> ###).
            close()
            depth = hmatch.group(1).count(".") + 2
            blocks.append(("p", ["#" * min(depth, 6) + " " + s]))
        elif numbered:
            if kind != "list":
                close()
                kind = "list"
            cur.append(f"{numbered.group(1)}. " + s[numbered.end():])
        else:
            ended_short = bool(prev) and bool(_TERMINAL_RE.search(prev)) and len(prev) < 0.6 * wide
            if kind == "list":
                if ended_short or (heading_like(s) and prev and _TERMINAL_RE.search(prev)):
                    close()
                    cur.append(s)
                else:
                    cur[-1] = _dehyphenate_join(cur[-1], s)  # a continuation of the item
            elif not cur:
                cur.append(s)
            elif ended_short or (len(cur) == 1 and cur[0] == prev and heading_like(prev) and s[:1].isupper()):
                close()
                cur.append(s)
            else:
                cur[-1] = _dehyphenate_join(cur[-1], s)
        prev = s
    close()
    out = ["\n".join(items) if k in ("list", "quote") else " ".join(items) for k, items in blocks]
    return "\n\n".join(x for x in out if x.strip())


def _normalise_bullets(text: str) -> str:
    """Bullet glyphs -> markdown list items on their own lines (for text that
    is already line-structured). A glyph in the middle of a line starts a new
    item; "- " / "* " lists and everything else are left as they are."""
    text = _MID_BULLET_RE.sub("\n", text)
    out: list[str] = []
    for line in text.split("\n"):
        if _BULLET_LINE_RE.match(line):
            out.append("- " + _BULLET_LINE_RE.sub("", line, count=1))
        elif _DASH_BULLET_RE.match(line):
            out.append("- " + _DASH_BULLET_RE.sub("", line, count=1))
        else:
            out.append(line)
    return "\n".join(out)


_EMAIL_HEADER_RE = re.compile(r"^(?:From|To|Cc|Bcc|Subject|Date|Sent|Reply-To):\s+\S", re.I)
_LIST_ITEM_RE = re.compile(r"^(- |\d{1,3}\. )\S")


def _separate_lists(text: str) -> str:
    """A blank line before a run of list items that follows a non-list line,
    and after it, so markdown renders a real list."""
    out: list[str] = []
    for line in text.split("\n"):
        is_item = bool(_LIST_ITEM_RE.match(line))
        prev_item = bool(out) and bool(_LIST_ITEM_RE.match(out[-1]))
        if is_item and out and out[-1].strip() and not prev_item:
            out.append("")
        elif not is_item and prev_item and line.strip() and not line.startswith((" ", "\t")):
            out.append("")
        out.append(line)
    return "\n".join(out)


def normalise_text(text: str) -> str:
    """Repair extracted/pasted text; idempotent, and a no-op (beyond
    character clean-up) for well-formed prose and markdown."""
    if not text:
        return ""
    text = clean_characters(text)
    lines = text.split("\n")
    if looks_word_per_line(lines):
        text = _separate_lists(_rejoin_tokens(lines))
    elif looks_hard_wrapped(lines):
        text = _separate_lists(_rejoin_wrapped(_normalise_bullets(text).split("\n")))
    else:
        fixed = _normalise_bullets(text)
        text = _separate_lists(fixed) if fixed != text else text
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(ln.rstrip() for ln in text.split("\n"))
    return text.strip()


# ---------------------------------------------------------------------------
# Email clean-up (ingest, pasted text and text files only; never a fetched page)
# ---------------------------------------------------------------------------
_HEADER_FIELD_RE = re.compile(r"^(From|To|Cc|Bcc|Subject|Date|Sent|Reply-To):[ \t]*\S", re.I)
_ORIGINAL_MARKER_RE = re.compile(r"^\s*-{2,}\s*(original|reply)\s+message\s*-{2,}\s*$", re.I)
_UNDERSCORE_RULE_RE = re.compile(r"^\s*_{10,}\s*$")
_ATTRIB_START_RE = re.compile(r"^\s*On\s.{2,}", re.I)
_SIGNOFF_RE = re.compile(
    r"^\s*(?:best(?: regards| wishes)?|(?:kind |warm |many |best )?regards|thanks(?: again| very much)?|thank you|many thanks|"
    r"cheers|sincerely|yours (?:sincerely|faithfully)|cordially|warmly|with thanks),?\s*$",
    re.I,
)
_MOBILE_FOOTER_RE = re.compile(r"^\s*(sent from my .{2,40}|get outlook for .{2,20}|sent via .{2,40}|sent from (?:mail|outlook) for .{2,20})\s*$", re.I)
_CONTACT_RE = re.compile(
    r"(@\w|https?://|www\.|\btel\b|\bphone\b|\bmobile\b|\bfax\b|\bext\b|\+\d[\d ()-]{6,}|\b\d{3,4}[ -]\d{3,4}[ -]\d{3,4}\b|\|)",
    re.I,
)
_DISCLAIMER_INDICATORS = [
    re.compile(p, re.I)
    for p in (
        r"not the intended recipient",
        r"intended (?:only )?for (?:the )?(?:named |intended )?(?:recipient|addressee|use of)",
        r"received this (?:e-?mail|message|communication|transmission) in error",
        r"\bprivileged\b",
        r"confidentiality (?:notice|statement)",
        r"\b(?:e-?mail|message)\b[^.]{0,80}\bconfidential\b",
        r"unauthori[sz]ed (?:use|disclosure|copying|review|distribution)",
        r"please consider the environment",
        r"\bdisclaimer\b",
        r"\bvirus(?:es)?\b.{0,40}\b(?:scan|free|checked)",
    )
]
_DISCLAIMER_LEAD_RE = re.compile(
    r"^\s*(this (?:e-?mail|message|communication)|confidential|disclaimer|notice|please consider the environment|think before you print|"
    r"the information (?:in|contained in) this)",
    re.I,
)


def _attribution_len(lines: list[str], i: int) -> int:
    """Lines used by an "On <date>, <name> wrote:" attribution that starts at i
    (it often wraps onto the next line or two), else 0."""
    if not _ATTRIB_START_RE.match(lines[i]):
        return 0
    joined = lines[i].strip()
    for extra in range(3):
        if re.search(r"wrote:\s*$", joined, re.I):
            return extra + 1
        if i + extra + 1 >= len(lines) or not lines[i + extra + 1].strip():
            return 0
        joined += " " + lines[i + extra + 1].strip()
    return 0


def _leading_header_end(lines: list[str]) -> int:
    """Index after the message's own header block (From:/To:/Subject:/Date: at the very top), or 0."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    start = i
    while i < len(lines) and lines[i].strip() and (_HEADER_FIELD_RE.match(lines[i]) or (i > start and lines[i][:1] in " \t")):
        i += 1
    return i if i > start else 0


def _is_outlook_block(lines: list[str], i: int) -> bool:
    """"From: X" followed within a few lines by "Sent:" and "To:"/"Subject:": the header of quoted history."""
    if not re.match(r"^From:\s*\S", lines[i], re.I):
        return False
    window = [ln for ln in lines[i + 1 : i + 6]]
    return any(re.match(r"^Sent:\s*\S", ln, re.I) for ln in window) and any(re.match(r"^(To|Subject|Cc):", ln, re.I) for ln in window)


def looks_like_email(text: str) -> bool:
    """Does this pasted text look like an email (or a thread)? Headers at the
    top (two or more of From/To/Subject/Date/Sent/Cc), an "On ... wrote:"
    attribution line, an "Original Message" marker, a "Sent from my ..." footer or an Outlook history header.
    Quoting with ">" or a "-- " line alone is not enough."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    top = _leading_header_end(lines)
    fields = {m.group(1).lower() for ln in lines[:top] if (m := _HEADER_FIELD_RE.match(ln))}
    if len(fields) >= 2:
        return True
    for i, ln in enumerate(lines):
        if _ORIGINAL_MARKER_RE.match(ln) or _MOBILE_FOOTER_RE.match(ln) or _is_outlook_block(lines, i):
            return True
        if _attribution_len(lines, i):
            return True
    return False


def _drop_signatures(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if re.fullmatch(r"--\s?", ln.rstrip("\n")) or re.fullmatch(r"--\s?", ln):
            # the "-- " delimiter: a signature to the end of the message (the next header block, or the end)
            j = i + 1
            while j < n and not (_HEADER_FIELD_RE.match(lines[j]) and re.match(r"^From:", lines[j], re.I)):
                j += 1
            i = j
            continue
        if _MOBILE_FOOTER_RE.match(ln):
            i += 1
            continue
        if _SIGNOFF_RE.match(ln):
            j = i + 1
            block: list[str] = []
            while j < n and lines[j].strip() and len(block) < 9 and not _HEADER_FIELD_RE.match(lines[j]):
                block.append(lines[j])
                j += 1
            if block and len(block) <= 8 and all(len(b) <= 90 for b in block) and (
                len(block) >= 3 or any(_CONTACT_RE.search(b) for b in block)
            ):
                i = j  # sign-off, name, title, phone, address: the whole block
                continue
        out.append(ln)
        i += 1
    return out


def _drop_disclaimers(text: str) -> str:
    paras = re.split(r"\n\s*\n", text)
    keep: list[str] = []
    for para in paras:
        hits = sum(1 for rx in _DISCLAIMER_INDICATORS if rx.search(para))
        if hits >= 2 or (hits == 1 and _DISCLAIMER_LEAD_RE.match(para)):
            continue
        keep.append(para)
    return "\n\n".join(keep)


def strip_email_noise(text: str) -> str:
    """For text that looks like an email: drop the quoted reply history ("> "
    lines, "On ... wrote:" attributions, an Outlook "Original Message" tail),
    signatures (the "-- " delimiter, sign-off blocks with contact details,
    "Sent from my ..."), and legal or environmental footers. The newest
    message, its own headers, and any new text written between quoted lines
    stay. Anything else is returned untouched, and so is an email where
    nothing new would be left. Deterministic and idempotent."""
    if not text or not looks_like_email(text):
        return text
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body_start = _leading_header_end(lines)

    # 1. Cut an Outlook-style history tail (only when something new comes before it).
    cut = None
    for i in range(body_start, len(lines)):
        if _ORIGINAL_MARKER_RE.match(lines[i]) or _is_outlook_block(lines, i):
            if any(ln.strip() for ln in lines[body_start:i]):
                cut = i
                if i > 0 and _UNDERSCORE_RULE_RE.match(lines[i - 1]):
                    cut = i - 1
                break
    if cut is not None:
        lines = lines[:cut]

    # 2. Quoted lines and their attribution lines.
    kept: list[str] = []
    i = 0
    while i < len(lines):
        used = _attribution_len(lines, i)
        if used:
            j = i + used
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines) or lines[j].lstrip().startswith(">"):
                i = j  # the attribution goes; the quoted lines after it go in the next steps
                continue
        if lines[i].lstrip().startswith(">"):
            i += 1
            continue
        kept.append(lines[i])
        i += 1

    out = _drop_disclaimers("\n".join(_drop_signatures(kept)))
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = "\n".join(ln.rstrip() for ln in out.split("\n")).strip()
    body_words = len(re.sub(r"^(?:[A-Za-z-]+:[ \t]*.*)$", "", out, flags=re.M).split())
    if body_words < 8:
        return text  # nothing new would be left: keep what was pasted
    return out
