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
