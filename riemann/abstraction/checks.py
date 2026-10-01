"""Deterministic faithfulness checks on short model-written items (essentials,
key facts, the first step, deadlines, actions) against the leaves they cite.

Numbers are checked in build.py (`_number_in_source`). This module adds:

- dates: weekday names, month names (and a deadline's day, month and time) must
  appear in the cited text;
- cite overlap: an item must share content words with the leaves it cites;
- qualifiers: a source sentence with "not", "unless", "except" ... that the item
  drops is reported (a warning, never a drop).
"""

from __future__ import annotations

import datetime as _dt
import re

# --------------------------------------------------------------------------
# Content-word overlap
# --------------------------------------------------------------------------
_STOP = frozenset(
    """a about above after again all also an and any are as at be because been before being below between both but by can could did do does
    doing down during each few for from further had has have having he her here hers him his how i if in into is it its itself just me more most
    my no nor not now of off on once only or other our out over own same she should so some such than that the their them then there these they
    this those through to too under until up very was we were what when where which while who whom why will with would you your yours
    also may must shall need needs per via etc eg ie one two three""".split()
)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ed", "es", "ly", "s")


def _stem(word: str) -> str:
    w = word.lower().strip("'’-")
    if w.endswith(("'s", "’s")):
        w = w[:-2]
    if any(c.isdigit() for c in w):
        return w.replace(",", "")
    for suf in _SUFFIXES:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w[:5]  # "submit" / "submission" / "submitted" meet at "submi"


def content_tokens(text: str) -> list[str]:
    """Stemmed content words of text, in order, without stop words and without duplicates."""
    seen: dict[str, None] = {}
    for m in _WORD_RE.finditer(text or ""):
        raw = m.group()
        low = raw.lower()
        if low in _STOP or (len(low) < 3 and not any(c.isdigit() for c in low)):
            continue
        seen.setdefault(_stem(raw), None)
    return list(seen)


def overlap(item_text: str, source_text: str) -> tuple[int, int]:
    """(content words of the item that also occur in the source, content words of the item)."""
    item = content_tokens(item_text)
    if not item:
        return 0, 0
    src = set(content_tokens(source_text))
    return sum(1 for t in item if t in src), len(item)


def overlap_ok(item_text: str, source_text: str, floor: float) -> bool:
    """Does the item share enough of its words with the source? An item with no content
    words at all (e.g. "5 pm") is left to the number and date checks."""
    shared, total = overlap(item_text, source_text)
    return total == 0 or shared / total >= floor


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_WEEKDAY_ALT = r"mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?"
_MONTH_ALT = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
# In the item: names must be written as names (capitalised), so "sat down" and "the sun" are not weekdays
# and the modal "may" is only a month beside a day number.
_ITEM_WEEKDAY_RE = re.compile(r"\b(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\b")
_ITEM_MONTH_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b"
)
_ITEM_MAY_RE = re.compile(r"(?:\bMay\s+\d{1,2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?May\b)")
_SRC_WEEKDAY_RE = re.compile(rf"\b(?:{_WEEKDAY_ALT})\b", re.I)
_SRC_MONTH_RE = re.compile(rf"\b(?:{_MONTH_ALT})\b", re.I)
_NUMERIC_DATE_RE = re.compile(r"(?<![\d.])(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?(?![\d])")
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")


def _weekday_index(token: str) -> int:
    return next(i for i, name in enumerate(_WEEKDAYS) if name.startswith(token.lower()[:3]))


def _month_index(token: str) -> int:
    return next(i for i, name in enumerate(_MONTHS) if name.startswith(token.lower()[:3]))


def weekdays_in(text: str, strict: bool = True) -> set[int]:
    rx = _ITEM_WEEKDAY_RE if strict else _SRC_WEEKDAY_RE
    return {_weekday_index(m.group()) for m in rx.finditer(text or "")}


def months_in_item(text: str) -> set[int]:
    out = {_month_index(m.group()) for m in _ITEM_MONTH_RE.finditer(text or "")}
    if _ITEM_MAY_RE.search(text or ""):
        out.add(4)
    return out


def months_in_source(text: str) -> set[int]:
    """Months a source mentions, by name or in a numeric date (12/03/2025 counts as March and December)."""
    out = {_month_index(m.group()) for m in _SRC_MONTH_RE.finditer(text or "")}
    for m in _NUMERIC_DATE_RE.finditer(text or ""):
        for part in (m.group(1), m.group(2)):
            if 1 <= int(part) <= 12:
                out.add(int(part) - 1)
    for m in _ISO_DATE_RE.finditer(text or ""):
        if 1 <= int(m.group(2)) <= 12:
            out.add(int(m.group(2)) - 1)
    return out


def dates_ok(item_text: str, source_text: str) -> bool:
    """Every weekday name and month name in the item appears in the source (any
    abbreviation counts: "Fri" matches "Friday"). Day numbers are checked with the
    other numbers, by the caller."""
    if weekdays_in(item_text) - weekdays_in(source_text, strict=False):
        return False
    return not (months_in_item(item_text) - months_in_source(source_text))


def day_in_source(day: int, source_text: str) -> bool:
    """Does the number `day` (1-31) appear in the source as a whole number (24, 24th, 024)?"""
    return re.search(rf"(?<![\d.,]){day:d}(?:st|nd|rd|th)?(?![\d]|[.,]\d)|(?<![\d.,])0{day:d}(?!\d)", source_text or "", re.I) is not None


def parse_iso(iso: object, today: _dt.date | None = None) -> tuple[_dt.date, bool] | None:
    """(date, year_inferred) for "YYYY-MM-DD", or for a year-less "MM-DD" / "----MM-DD" / "?-MM-DD",
    which becomes the next occurrence of that day on or after `today`. None if not a real date."""
    if not isinstance(iso, str):
        return None
    s = iso.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    try:
        if m:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), False
        m = re.fullmatch(r"(?:-{1,4}|\?{1,4}|null|)-?(\d{2})-(\d{2})", s, re.I)
        if m:
            today = today or _dt.date.today()
            month, day = int(m.group(1)), int(m.group(2))
            for year in (today.year, today.year + 1, today.year + 4):  # 29 February needs a leap year
                try:
                    cand = _dt.date(year, month, day)
                except ValueError:
                    continue
                if cand >= today:
                    return cand, True
    except ValueError:
        return None
    return None


def date_in_source(d: _dt.date, source_text: str) -> bool:
    """The day number and the month of d both appear in the source (the month by name or in a numeric date)."""
    return day_in_source(d.day, source_text) and (d.month - 1) in months_in_source(source_text)


def years_in(text: str) -> set[int]:
    return {int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text or "")}


def time_in_source(hhmm: str, source_text: str) -> bool:
    """Does a clock time equal to "HH:MM" (24 h) appear in the source: 17:00, 5 pm, 5:00 PM, 5.00pm,
    or "midnight"/"noon" for 00:00/12:00?"""
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", hhmm or "")
    if not m:
        return False
    h, mm = int(m.group(1)), int(m.group(2))
    src = source_text or ""
    if re.search(rf"(?<!\d){h:02d}[:.h]{mm:02d}(?!\d)|(?<!\d){h}[:.]{mm:02d}(?!\d)", src) and (h >= 13 or h == 0 or re.search(rf"(?<!\d){h:02d}[:.]{mm:02d}", src)):
        return True
    h12 = h % 12 or 12
    meridiem = "am" if h < 12 else "pm"
    minutes = rf"(?:[:.]{mm:02d})" if mm else r"(?:[:.]00)?"
    if re.search(rf"(?<![\d:.]){h12}{minutes}\s*{meridiem[0]}\.?m?\.?(?![a-z])", src, re.I):
        return True
    if (h, mm) == (0, 0) and re.search(r"\bmidnight\b", src, re.I):
        return True
    if (h, mm) == (12, 0) and re.search(r"\b(noon|midday)\b", src, re.I):
        return True
    return False


# --------------------------------------------------------------------------
# Qualifiers (negation, exception, modality)
# --------------------------------------------------------------------------
_QUALIFIER_RE = re.compile(
    r"\b(must not|shall not|may not|should not|cannot|can't|cant|do not|does not|did not|don't|doesn't|not|never|no|unless|except(?:ion|ions)?|"
    r"only if|only when|without|excluding|other than)\b|n't\b",
    re.I,
)
# What counts as the qualifier being kept: any negation or exception word in the item.
_KEPT_RE = re.compile(
    r"\b(not|no|none|nobody|nothing|neither|nor|never|unless|except(?:ion|ions)?|only|without|excluding|cannot|prohibit(?:ed|s)?|forbid(?:den)?|ban(?:ned)?|"
    r"must\s+not|shall\s+not|may\s+not|disallow(?:ed)?|exempt(?:ed)?)\b|n't\b",
    re.I,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def qualifier_dropped(item_text: str, cited_text: str) -> tuple[str, str] | None:
    """If the sentence of the cited text that the item is mostly about (at least two shared
    content words, and the best such sentence) carries a negation or exception that the item
    does not, return (qualifier, sentence); else None. Used for log-only warnings."""
    item = set(content_tokens(item_text))
    if len(item) < 2 or _KEPT_RE.search(item_text or ""):
        return None
    best: tuple[int, str] | None = None
    for sent in _SENTENCE_SPLIT_RE.split(cited_text or ""):
        sent = sent.strip()
        if not sent:
            continue
        shared = len(item & set(content_tokens(sent)))
        if shared >= 2 and (best is None or shared > best[0]):
            best = (shared, sent)
    if best is None:
        return None
    m = _QUALIFIER_RE.search(best[1])
    return (m.group(0).lower(), best[1]) if m else None
