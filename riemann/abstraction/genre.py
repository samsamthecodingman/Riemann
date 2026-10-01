"""Document genre: what kind of document this is decides what a good summary
must cover (docs/overnight-review.md F1-F8), while the reader's goal
(OBJECTIVE_FOCUS in build.py) still decides what to emphasise within it.

`detect_genre` is deterministic and free: cue words in the title, the first
couple of thousand characters, the headings and a few structural signals. A
strong result is used straight away; otherwise the provisional-gist call also
returns a "genre" (build.py), so no extra model call is made.
"""

from __future__ import annotations

import re

GENRES: dict[str, str] = {
    "assignment": "Assignment or task brief",
    "paper": "Research paper",
    "news": "News article",
    "email": "Email or thread",
    "meeting": "Meeting notes",
    "legal": "Legal or policy document",
    "technical": "Technical documentation",
    "article": "General article",
    "other": "Other",
}

# Genres whose reader has something to do: the overview adds a first step, the size of the job and
# the deadline. (An execute or plan goal makes any document task-like too.)
TASK_GENRES = {"assignment", "meeting"}
TASK_OBJECTIVES = {"execute", "plan"}


def valid_genre(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    key = value.strip().lower().replace(" ", "_")
    aliases = {
        "assignment_brief": "assignment", "task": "assignment", "brief": "assignment", "assignment/task": "assignment",
        "research_paper": "paper", "paper": "paper", "study": "paper",
        "news_article": "news", "email_thread": "email", "thread": "email", "meeting_notes": "meeting", "minutes": "meeting",
        "legal/policy": "legal", "policy": "legal", "contract": "legal", "technical_docs": "technical", "docs": "technical",
        "documentation": "technical", "general_article": "article", "essay": "article", "blog": "article",
    }
    key = aliases.get(key, key)
    return key if key in GENRES else None


def is_task_like(genre: str | None, objective: str | None) -> bool:
    return genre in TASK_GENRES or objective in TASK_OBJECTIVES


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
_HEADER_FIELD_RE = re.compile(r"^(?:From|To|Cc|Subject|Date|Sent|Reply-To):\s*\S", re.I | re.M)


def _count(patterns: list[str], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.I | re.M))


_ASSIGNMENT = [
    r"\bassignment\b", r"\bproject brief\b|\bbrief\b", r"\bdue (?:date|by|on)\b|\bdue:|\bdeadline\b", r"\bsubmi(?:t|ssion)\b",
    r"\bmarking (?:criteria|rubric)\b|\brubric\b|\bassessed\b|\bassessment\b", r"\bword (?:limit|count)\b|\bmax(?:imum)?\s+\d+\s+(?:pages|words)\b",
    r"\bweight(?:ing)?\b|\bworth \d+\s*%|\b\d+\s*% of (?:your|the) (?:final )?(?:mark|grade|unit)", r"\bdeliverables?\b",
    r"\bplagiarism\b|\bacademic integrity\b", r"\bextension\b", r"\bcoursework\b|\bunit (?:code|coordinator)\b",
]
_PAPER = [
    r"^#{0,6}\s*abstract\b", r"^#{1,6}\s*(?:\d+\.?\s*)?introduction\b|^\s*(?:\d+\.?\s*)introduction\s*$", r"^#{1,6}\s*(?:\d+\.?\s*)?(?:methods?|methodology|materials and methods)\b",
    r"^#{1,6}\s*(?:\d+\.?\s*)?results?\b", r"^#{1,6}\s*(?:\d+\.?\s*)?discussion\b", r"^#{1,6}\s*(?:\d+\.?\s*)?(?:references|bibliography)\b",
    r"\bet al\.", r"\bdoi:|\barxiv\b|doi\.org", r"\bwe (?:propose|show|find|present|study|report|evaluate)\b|\bparticipants\b|\bp\s*[<=]\s*0?\.\d+",
]
_NEWS = [
    r"\((?:reuters|ap|afp|upi|bloomberg)\)|\bassociated press\b|\bstaff reporter\b", r"\bsaid (?:on )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\baccording to\b", r"\b(?:officials|spokes(?:man|woman|person)|police|authorities) said\b", r"\bpublished\b.{0,40}\b20\d\d\b",
]
_MEETING = [
    r"\bmeeting (?:notes|minutes)\b|\bminutes of\b|\bminutes\b", r"\bagenda\b", r"\battendees\b|\bpresent:|\bapologies\b", r"\baction(?:s| items?)\b",
    r"\bnext meeting\b", r"\bdecisions?\b", r"\bchair(?:ed)?\b|\bminute[- ]taker\b|\bnotes by\b",
]
_LEGAL = [
    r"\bhereinafter\b|\bwhereas\b|\bpursuant to\b|\bindemnif", r"\bgoverning law\b|\bjurisdiction\b", r"\bthe (?:licensee|licensor|company|supplier|customer|employee|employer|tenant|landlord)\b",
    r"\bterms and conditions\b|\bterms of (?:service|use)\b|\bprivacy policy\b|\bpolicy\b", r"\bclause \d|\bsection \d+(?:\.\d+)*\b",
    r"\bnon-compliance\b|\bbreach\b|\bterminat(?:e|ion)\b", r"\bthis (?:agreement|policy|contract|procedure)\b",
]
_TECH = [
    r"^#{1,6}\s*(?:installation|install|usage|getting started|quick ?start|api(?: reference)?|configuration|prerequisites|requirements|examples?|troubleshooting|changelog|cli)\b",
    r"```", r"\bpip install\b|\bnpm (?:install|i)\b|\bcargo (?:add|install)\b|\bapt(?:-get)? install\b", r"\b(?:returns?|parameters?|arguments?|options?|flags?)\b\s*[:|]",
    r"\bsudo\b|\bgit clone\b|\bdocker (?:run|build)\b", r"--[a-z][a-z-]+",
]
_ARTICLE = [r"^\s*by\s+[A-Z][a-z]+ [A-Z]", r"\bposted (?:on|by)\b|\bupdated\b.{0,20}\b20\d\d\b"]


def detect_genre(title: str, text: str) -> tuple[str | None, bool]:
    """(genre, strong) from cue words; (None, False) when nothing stands out. "Strong" means
    several independent cues agree, so the build may use it before any model has seen the text."""
    head = "\n".join([title or "", text[:3500]])
    headings = "\n".join(ln for ln in text.splitlines() if ln.lstrip().startswith("#"))
    title_head = (title or "") + "\n" + headings[:1500]

    # Email: its own headers are decisive.
    fields = {m.group(0).split(":")[0].lower() for m in _HEADER_FIELD_RE.finditer(text[:1500])}
    if len(fields) >= 2:
        return "email", True
    scores: dict[str, int] = {
        "assignment": _count(_ASSIGNMENT, head),
        "paper": _count(_PAPER, text[:6000] + "\n" + headings),
        "news": _count(_NEWS, head),
        "meeting": _count(_MEETING, head),
        "legal": _count(_LEGAL, head),
        "technical": _count(_TECH, text[:6000] + "\n" + headings),
    }
    # Title and headings weigh double for the genres that announce themselves there.
    if re.search(r"\bmeeting (?:notes|minutes)\b|\bminutes\b", title_head, re.I):
        scores["meeting"] += 2
    if re.search(r"\bassignment\b|\bbrief\b|\bcoursework\b|\bassessment task\b", title_head, re.I):
        scores["assignment"] += 2
    if re.search(r"^#{0,6}\s*abstract\b", text[:3000], re.I | re.M):
        scores["paper"] += 1
    if re.search(r"\bpolicy\b|\bagreement\b|\bterms\b|\bcontract\b", title or "", re.I):
        scores["legal"] += 2
    thresholds = {"assignment": 4, "paper": 4, "news": 2, "meeting": 3, "legal": 4, "technical": 3}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    runner = ranked[1][1]
    if best_score >= thresholds[best] and best_score >= runner + 2:
        return best, True
    if best_score >= max(2, thresholds[best] - 2) and best_score > runner:
        return best, False
    if re.search(r"\bthe (?:meeting|minutes)\b", head, re.I) and scores["meeting"] >= 2:
        return "meeting", False
    return None, False


# ---------------------------------------------------------------------------
# Prompts: one block per genre, appended to summary / root / overview prompts
# ---------------------------------------------------------------------------
_TAIL = (
    "\nThe reader's goal (below, if given) still decides what to emphasise inside this shape. Every claim, number, date,"
    " name and title must still be supported by the source; never invent requirements, deadlines, results or owners."
)
# FakeSummariser (and tests) detect a block through its first line.
GENRE_FOCUS: dict[str, str] = {
    "assignment": (
        "Document genre: assignment\n"
        "This is an assignment or task brief. Summarise it as an unpacking of the task, not a shortening: lead with the"
        " constraints (due date, word or page limit, weighting, how to submit), then the task itself: the command word"
        " (analyse, compare, evaluate, discuss, ...) and what it asks for, the deliverables, the marking criteria, and what"
        " is not allowed (limits, AI or collaboration rules, penalties). Phrase titles as requirements or tasks."
        " Fill \"steps\" whenever the brief gives an order of work."
        + _TAIL
    ),
    "paper": (
        "Document genre: paper\n"
        "This is a research paper. Cover its question, the method and sample, the main result with its number, and its"
        " limits, in the paper's own order. Name the claim in titles, not the section heading (\"Methods\" becomes what was"
        " done). Keep evidence limits, hedges and sample sizes; if the paper states no limitation, say that nothing is stated"
        " rather than inventing one."
        + _TAIL
    ),
    "news": (
        "Document genre: news\n"
        "This is a news story written as an inverted pyramid: the opening says who, what, when, where and why, and detail"
        " falls in importance, so earlier paragraphs usually matter more than later ones. Keep attribution (\"said\","
        " \"according to\"): never turn a claim someone made into a plain fact."
        + _TAIL
    ),
    "email": (
        "Document genre: email\n"
        "This is an email or a thread. Put the ask first: what the sender wants from the reader, and by when. Keep what is"
        " decided separate from what is still open, and keep who said or asked what. Ignore greetings, sign-offs and"
        " boilerplate. Titles state the ask or the decision."
        + _TAIL
    ),
    "meeting": (
        "Document genre: meeting\n"
        "These are meeting notes or minutes. Cover the decisions (with the reason and any dissent), the actions as who will"
        " do what by when, and the open questions; never mix what was said with what will be done. A node about actions should"
        " name the owner and the date. Prefer the earliest dated action for \"key_fact\"."
        + _TAIL
    ),
    "legal": (
        "Document genre: legal\n"
        "This is a legal, policy or rules document. Keep who is bound, what they must (\"must\", \"shall\"), may or should do,"
        " the exceptions (\"unless\", \"except\"), the negations (\"must not\") and the deadlines. Never soften \"must\" to"
        " \"should\" or drop an exception, and never change who it applies to. Titles name the rule or the obligation."
        + _TAIL
    ),
    "technical": (
        "Document genre: technical\n"
        "This is technical documentation. Decide whether it is a tutorial, a how-to, reference or an explanation. A how-to or"
        " tutorial keeps its steps in order, with commands, flags and names copied exactly (fill \"steps\"); reference keeps"
        " values, signatures and names so each can be found; an explanation keeps the causal chain. Titles name the task or the"
        " thing a section covers."
        + _TAIL
    ),
    "article": (
        "Document genre: article\n"
        "This is a general article or essay. Foreground its main claim, the strongest support for it, and what a reader should"
        " take away. Titles name the claim."
        + _TAIL
    ),
}

# Overview essentials by genre. They are ordered by what the reader must act on first (deadline,
# deliverables, first step) and then reference information; build._sort_essentials enforces the order.
GENRE_ESSENTIALS: dict[str, str] = {
    "assignment": (
        "For this assignment or task brief, prefer essentials like: Due, Deliverables, Task verb (the command word and what it"
        " asks for), Weight, Limits (words, pages), Not allowed, Submit how, Assessed on."
    ),
    "paper": "For this research paper, prefer essentials like: Question, Method and sample, Main result (with the number), Limits. If the paper states no limitation, the value is \"not stated\".",
    "news": "For this news story, prefer essentials like: Who, What, When, Where, Why or how. Keep who said it (attribution).",
    "email": "For this email or thread, prefer essentials like: The ask, Reply by, Decided, Still open, From.",
    "meeting": "For these meeting notes, prefer essentials like: Decisions, Next action (earliest dated), Open questions, Next meeting, Attendees.",
    "legal": "For this legal or policy document, prefer essentials like: Applies to, Must, May, Exceptions, Deadline, If not followed. Keep must, shall, may and should exactly as the source has them.",
    "technical": "For this technical document, prefer essentials like: Type (tutorial, how-to, reference or explanation), Covers, Key steps or rules, Where to look.",
    "article": "For this article, prefer essentials like: Main claim, Evidence, Takeaway.",
}


def genre_focus(genre: str | None) -> str | None:
    return GENRE_FOCUS.get(genre or "")
