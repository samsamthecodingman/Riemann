from riemann.abstraction import ingest
from riemann.abstraction.chunk import chunk
from riemann.abstraction.normalise import normalise_text

# A small synthetic brief in the shape pypdf produced for the tree that
# prompted this: every word on its own line, " \n" between words, an extra
# blank between paragraphs, bullet glyphs as stand-alone tokens, a lone
# non-breaking hyphen between the halves of a compound.
_GAP = "\n \n"  # one blank line between words
_PARA = "\n \n \n"  # two: a paragraph break


def _words(text: str) -> str:
    return _GAP.join(text.split())


def _word_per_line() -> str:
    bullets = [
        _words("the quality of their design work;"),
        # a lone non-breaking hyphen glued between the halves of a compound
        _GAP.join(["the", "validity", "of", "their", "self"]) + "\n\u2011\n" + _GAP.join(["selected", "evaluation;"]),
        _words("their ability to communicate clearly."),
    ]
    return (
        _words("ABC101 – Widget Engineering Overview The project is worth 25% of your mark in this unit")
        + "\n.\n"  # the full stop sits on its own line, glued to "unit"
        + _PARA
        + _words("Students will be assessed primarily on:")
        + _GAP
        + _GAP.join("●" + _GAP + b for b in bullets)
        + _PARA
        + _words("Submit via the portal by Friday.")
    )


def test_word_per_line_becomes_paragraphs_and_a_list():
    out = normalise_text(_word_per_line())
    blocks = out.split("\n\n")
    assert blocks[0].startswith("ABC101 – Widget Engineering Overview The project is worth 25% of your mark in this unit.")
    assert blocks[1] == "Students will be assessed primarily on:"
    assert blocks[2].split("\n") == [
        "- the quality of their design work;",
        "- the validity of their self-selected evaluation;",
        "- their ability to communicate clearly.",
    ]
    assert blocks[3] == "Submit via the portal by Friday."
    assert "‑" not in out


def test_word_per_line_chunks_into_real_paragraphs_not_one_word_each():
    text = normalise_text(_word_per_line() * 6)
    leaves = chunk(text)
    assert all(leaf.words > 8 for leaf in leaves)
    assert len(leaves) < 10


def test_normal_prose_is_unchanged():
    prose = (
        "# A title\n\n"
        "This is a paragraph of ordinary prose that is written on one long line, the way most markdown is, and it goes on for a while.\n\n"
        "Here is a second paragraph. It has two sentences and no hard wraps at all, so nothing should be rejoined or reflowed here.\n"
    )
    assert normalise_text(prose) == prose.strip()


def test_markdown_lists_and_code_are_preserved():
    md = (
        "## Steps\n\n"
        "Do the following:\n\n"
        "- first thing\n"
        "- second thing with **bold** text\n"
        "- third thing\n\n"
        "1. one\n"
        "2. two\n\n"
        "```python\nx  =  1\nprint(x)\n```\n"
    )
    assert normalise_text(md) == md.strip()


def test_bullet_glyphs_become_markdown_items():
    text = "Requirements include:\n● a working build\n• a test report\n– a readme file\nplus other things.\n"
    out = normalise_text(text)
    assert "- a working build\n- a test report\n- a readme file" in out
    assert "●" not in out and "•" not in out
    # a list is its own block
    assert "Requirements include:\n\n- a working build" in out


def test_inline_bullets_split_into_items():
    out = normalise_text("Assessed on: ● design ● testing ● reporting")
    assert out.split("\n") == ["Assessed on:", "", "- design", "- testing", "- reporting"] or "- design\n- testing\n- reporting" in out


def test_hard_wrapped_pdf_lines_rejoin_and_dehyphenate():
    lines = [
        "The committee reviewed the proposal at length and found that the infor-",
        "mation supplied was incomplete, so a further round of evidence gathering",
        "was requested before any decision could be reached on the matter at hand.",
        "The second paragraph begins here and also wraps across several short lines",
        "because the extraction tool broke it at a fixed column width of about",
        "eighty characters, which is what PDF text usually looks like when copied out.",
        "A third paragraph follows and it too continues across a couple of lines of",
        "text that end without any sentence punctuation until the very last one.",
        "Fourth paragraph text carries on in the same style so the detector sees a",
        "consistent hard wrap and treats the whole thing as wrapped prose rather than",
        "as a set of unrelated short lines that should each stay where they are.",
    ]
    out = normalise_text("\n".join(lines))
    assert "information supplied was incomplete" in out
    assert "infor-" not in out
    assert "\n" not in out.split("\n\n")[0]


def test_characters_are_cleaned():
    out = normalise_text("Non‑breaking space and soft­hyphen   and    runs.\n")
    assert out == "Non-breaking space and softhyphen and runs."


def test_idempotent():
    once = normalise_text(_word_per_line())
    assert normalise_text(once) == once


def test_ingest_applies_normalisation_to_text_files_and_urls():
    _, text = ingest.from_text(_word_per_line())
    assert "\n\n- the quality" in text and " \n" not in text
    _, ftext = ingest.from_file("brief.txt", _word_per_line().encode())
    assert ftext == text


def _make_docx(body_xml: str) -> bytes:
    import io
    import zipfile

    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    doc = f'<?xml version="1.0"?><w:document {ns}><w:body>{body_xml}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def test_docx_headings_lists_and_tables():
    def p(text, style=None, num=False):
        ppr = ""
        if style or num:
            ppr = "<w:pPr>" + (f'<w:pStyle w:val="{style}"/>' if style else "") + ("<w:numPr/>" if num else "") + "</w:pPr>"
        return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"

    body = (
        p("Assignment 1", "Title")
        + p("Deliverables", "Heading1")
        + p("Submit a report.")
        + p("one", num=True)
        + p("two", num=True)
        + "<w:tbl><w:tr><w:tc>" + p("Due") + "</w:tc><w:tc>" + p("Friday") + "</w:tc></w:tr></w:tbl>"
    )
    title, text = ingest.from_file("brief.docx", _make_docx(body))
    assert title == "Assignment 1"
    assert "# Deliverables" in text
    assert "Submit a report." in text
    assert "- one\n- two" in text
    assert "- Due | Friday" in text


def test_binary_and_corrupt_uploads_are_refused_not_decoded():
    import pytest

    with pytest.raises(ValueError):
        ingest.from_file("x.docx", b"not a zip")
    with pytest.raises(ValueError):
        ingest.from_file("x.xlsx", b"PK\x03\x04junk")
    with pytest.raises(ValueError):
        ingest.from_file("x.pdf", b"%PDF-1.4 broken")
    assert ingest.from_file("n.txt", b"hello world")[1] == "hello world"


def test_running_headers_and_page_numbers_are_stripped_from_pdf_pages():
    topics = ["tides", "sediment", "harbour walls", "beach nourishment", "managed retreat"]
    pages = []
    for n, topic in enumerate(topics, 1):
        body = f"This paragraph is about {topic} and says something specific in a full line of prose.\nAnd it continues with more on {topic}, in detail.\nA closing sentence about {topic}."
        pages.append(f"Survey Report - CONFIDENTIAL\n{body}\nPage {n} of 5")
    out = ingest.strip_running_headers(pages)
    joined = "\n".join(out)
    assert "CONFIDENTIAL" not in "\n".join(out[1:])
    assert "Page " not in joined
    assert "about sediment" in joined and joined.count("A closing sentence about") == 5
    # page one keeps its top line (it is the document title)
    assert out[0].startswith("Survey Report - CONFIDENTIAL")


def test_short_documents_and_unique_lines_are_left_alone():
    pages = ["Alpha line\nbody one\nOmega line", "Beta line\nbody two\nOmega line"]
    assert ingest.strip_running_headers(pages) == pages  # under 3 pages
    pages = [f"Heading {w}\nbody about {w}\nclosing on {w}" for w in ("cats", "dogs", "birds", "fish")]
    assert ingest.strip_running_headers(pages) == pages  # nothing repeats


def test_numbered_heading_line_is_not_a_list_that_swallows_the_next_paragraph():
    wrapped = (
        "Managers usually respond in one of three ways:\n"
        "hard defences such as sea walls, soft defences such\n"
        "as beach nourishment, or managed retreat. Each has\n"
        "costs that fall on different groups, and each changes\n"
        "the sediment budget of neighbouring beaches, which\n"
        "is why decisions taken in one town often surprise\n"
        "the next town along the coast.\n"
    )
    src = "Prepared for the Board, October 2025\n1. Section number one heading\n" + wrapped + "2. Method\n" + wrapped
    out = normalise_text(src)
    assert "## 1. Section number one heading\n\nManagers usually" in out
    assert "\n\n## 2. Method\n\nManagers usually" in out
    assert normalise_text(out) == out  # idempotent


def test_real_numbered_list_is_still_a_list():
    src = (
        "You must do the following before the deadline:\n"
        "1. Submit the report through the portal\n"
        "2. Attend the demonstration session\n"
        "3. Complete the peer review form\n"
    )
    out = normalise_text(src)
    assert "1. Submit the report through the portal\n2. Attend the demonstration session" in out


def test_clean_extracted_unwraps_single_cell_tables_and_drops_permalinks():
    md = "| November 2022 In the books I read as a kid, reading was replaced.\nMore prose. |\n\n# Tutorials¶\n\n## Key principles ¶\n\nBody."
    out = ingest.clean_extracted(md)
    assert out.startswith("November 2022 In the books")
    assert not out.startswith("|") and "More prose.\n" in out + "\n" and "|" not in out
    assert "# Tutorials\n" in out and "## Key principles\n" in out and "¶" not in out


def test_clean_extracted_leaves_real_tables_alone():
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert ingest.clean_extracted(md) == md


def test_dotted_numbered_headings_become_nested_markdown_headings():
    wrapped = (
        "Field surveys were carried out on 14 March at twelve\n"
        "transects along the whole of the northern coast line\n"
        "and each transect was measured twice by two people\n"
        "using an RTK GPS receiver mounted on a survey pole.\n"
        "Samples were then dried and sieved in the laboratory\n"
        "before being weighed on a balance in grams.\n"
    )
    out = normalise_text("2. Methods\n" + wrapped + "2.1 Field work\n" + wrapped + "2.1.1 Sampling\n" + wrapped)
    assert out.startswith("## 2. Methods\n\nField surveys")
    assert "\n\n### 2.1 Field work\n\nField surveys" in out
    assert "\n\n#### 2.1.1 Sampling\n\nField surveys" in out
    assert normalise_text(out) == out


def test_typographic_ligatures_are_expanded():
    src = "The classiﬁed, deﬁned and ﬂexible oﬃce staﬀ suﬃx ﬅ ﬆ"
    out = normalise_text(src)
    assert out == "The classified, defined and flexible office staff suffix st st"
    assert normalise_text(out) == out


EMAIL = """From: Dana Whitfield <dana@example.org>
To: Sam Roberts <sam@example.com>
Subject: Re: Placement start date
Date: Wed, 15 Oct 2025 16:42

Hi Sam,

Thanks for getting back so quickly. Two things I need from you before I can lock this in. First, I need the signed placement agreement back by end of day Friday 24 October.

On Tue, 14 Oct 2025 at 09:15, Sam Roberts <sam@example.com> wrote:
> Hi Dana,
>
> Thanks for the details. I can start on 3 November as discussed, but I would need to leave at 3 pm on Thursdays for my lab class. Is that workable?
> Also, do I need to bring my own laptop?
>
> Thanks,
> Sam

On Mon, 13 Oct 2025 at 14:20, Dana Whitfield <dana@example.org> wrote:
>> Hi Sam,
>>
>> Great news, your placement has been approved. The start date is Monday 3 November, 9 am at the Northgate site.
"""


def test_email_headers_and_quoted_replies_keep_their_structure():
    out = normalise_text(EMAIL)
    # each header is its own paragraph, not one run-on line
    assert "From: Dana Whitfield <dana@example.org>\n\nTo: Sam Roberts <sam@example.com>\n\nSubject: Re: Placement start date\n\nDate:" in out
    # quoted lines stay on their own lines, with no ">" marker in the middle of a paragraph
    assert "> Hi Dana,\n>\n> Thanks for the details." in out
    assert "> Also, do I need to bring my own laptop?\n>\n> Thanks,\n> Sam" in out
    assert ">> Hi Sam,\n>>\n>> Great news" in out
    for line in out.split("\n"):
        assert line.count(" > ") == 0 and " >> " not in line, line
    assert normalise_text(out) == out


def test_wrapped_prose_without_quotes_is_unchanged_by_the_quote_rule():
    src = "A plain sentence that is long enough to matter.\nIt continues on a second line here."
    assert normalise_text(src) == src
