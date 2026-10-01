"""PDF extraction with pdfplumber: paragraph breaks, bullets, two columns,
tables as markdown, running headers and footers gone; pypdf is the fallback."""
import io

import pytest

from riemann.abstraction import ingest
from tests.pdfgen import PdfBuilder

LEFT = [
    "The tide gauge at the north pier",
    "recorded water levels every six",
    "minutes across the whole year.",
]
LEFT2 = [
    "A second paragraph in the left",
    "column ends on this line.",
]
RIGHT = [
    "The right column holds the talk of",
    "the datum shift applied after the",
    "storm and why the trend is stable.",
]


def _frame(pdf_page, n: int, total: int) -> None:
    pdf_page.text(72, 770, "Annual Coastal Survey Report", size=9)
    pdf_page.text(72, 28, f"Confidential - Page {n} of {total}", size=9)


def make_pdf() -> bytes:
    pdf = PdfBuilder()
    total = 5

    p = pdf.page()
    _frame(p, 1, total)
    p.text(72, 700, "Tidal Gauge Study", size=22, bold=True)
    p.text(72, 672, "A short report on sea level at one station", size=11)
    y = p.lines(72, 620, 11, 14, LEFT)
    p.lines(72, y - 12, 11, 14, LEFT2)  # paragraph gap = one extra line
    p.lines(330, 620, 11, 14, RIGHT)

    p = pdf.page()
    _frame(p, 2, total)
    p.text(72, 700, "2. Method", size=15, bold=True)
    p.text(72, 676, "The team did three things during the campaign:", size=11)
    y = 656
    for bullet in (
        ["First bullet text that wraps onto", "a second line of its own"],
        ["Second bullet is short"],
        ["Third bullet also runs onto", "two lines here"],
    ):
        p.text(80, y, "•", size=11)
        y = p.lines(96, y, 11, 14, bullet)
    p.grid(72, y - 16, [120, 100, 100], 20, [["Site", "Depth (m)", "Mean (cm)"], ["North pier", "4.2", "112"], ["Harbour", "6.0", "98"], ["Outer bar", "9.5", "87"]])
    p.lines(72, y - 130, 11, 14, ["After the table the prose carries on and this", "sentence is left open across the page and"])

    p = pdf.page()
    _frame(p, 3, total)
    y = p.lines(72, 700, 11, 14, ["continues here on the next page without a break.", "Then it stops."])
    p.lines(72, y - 12, 11, 14, ["A fresh paragraph starts after a gap."])
    for n in (4, 5):
        p = pdf.page()
        _frame(p, n, total)
        p.lines(72, 700, 11, 14, [f"Body text of page {n} that is unique to it."])
    return pdf.to_bytes()


@pytest.fixture(scope="module")
def extracted() -> tuple[str, str]:
    return ingest.from_file("report.pdf", make_pdf())


def test_running_header_and_footer_are_gone_but_the_title_stays(extracted):
    title, text = extracted
    assert "Annual Coastal Survey Report" not in text
    assert "Confidential" not in text and "Page 3 of 5" not in text
    assert "# Tidal Gauge Study" in text
    assert "Tidal Gauge Study" in title


def test_two_columns_read_left_then_right_with_wrapped_lines_joined(extracted):
    _, text = extracted
    left = " ".join(LEFT)
    right = " ".join(RIGHT)
    assert left in text and right in text
    assert text.index(left) < text.index(" ".join(LEFT2)) < text.index(right)
    # the two paragraphs of the left column are separate paragraphs
    assert f"{left}\n\n{' '.join(LEFT2)}" in text


def test_bullets_become_markdown_list_items_with_continuations_joined(extracted):
    _, text = extracted
    assert "- First bullet text that wraps onto a second line of its own" in text
    assert "- Second bullet is short" in text
    assert "- Third bullet also runs onto two lines here" in text
    assert "## 2. Method" in text or "# 2. Method" in text


def test_ruled_table_becomes_a_markdown_table_and_is_not_repeated_as_prose(extracted):
    _, text = extracted
    assert "| Site | Depth (m) | Mean (cm) |" in text
    assert "| --- | --- | --- |" in text
    assert "| North pier | 4.2 | 112 |" in text and "| Outer bar | 9.5 | 87 |" in text
    assert text.count("North pier") == 1


def test_a_paragraph_continues_across_a_page_break(extracted):
    _, text = extracted
    assert "this sentence is left open across the page and continues here on the next page without a break." in text.replace("\n", " ") or (
        "sentence is left open across the page and continues here on the next page" in text
    )
    assert "Then it stops.\n\nA fresh paragraph starts after a gap." in text


def test_output_chunks_into_sensible_leaves(extracted):
    from riemann.abstraction.chunk import chunk

    _, text = extracted
    leaves = chunk(text)
    tables = [l for l in leaves if l.atomic and l.text.startswith("| Site")]
    assert len(tables) == 1 and tables[0].text.count("\n") == 4  # header, rule, three rows


def test_falls_back_to_pypdf_when_pdfplumber_fails(monkeypatch):
    from riemann.abstraction import pdftext

    def boom(_content):
        raise RuntimeError("layout extraction broke")

    monkeypatch.setattr(pdftext, "extract_pages", boom)
    title, text = ingest.from_file("report.pdf", make_pdf())
    assert "tide gauge at the north pier" in text.replace("\n", " ")  # pypdf still reads the words
    assert "| Site |" not in text  # but has no table structure


def test_a_broken_pdf_is_still_a_plain_error():
    with pytest.raises(ValueError, match="could not read that PDF"):
        ingest.from_file("x.pdf", b"%PDF-1.4 broken")


def test_single_page_and_empty_pdf_do_not_crash():
    pdf = PdfBuilder()
    p = pdf.page()
    p.text(72, 700, "Just one short line on a single page.", size=12)
    title, text = ingest.from_file("one.pdf", pdf.to_bytes())
    assert "Just one short line on a single page." in text
    empty = PdfBuilder()
    empty.page()
    assert ingest.from_file("blank.pdf", empty.to_bytes())[1].strip() == ""


def test_a_boxed_page_body_with_a_footer_strip_is_not_a_table():
    """A slide-style frame (one big box over a small two-cell footer) is drawn with the same
    ruling lines as a table; it must stay prose."""
    pdf = PdfBuilder()
    for n in (1, 2):
        p = pdf.page()
        for x1, y1, x2, y2 in ((72, 700, 540, 700), (72, 430, 540, 430), (72, 400, 540, 400), (72, 700, 72, 400), (540, 700, 540, 400), (300, 430, 300, 400)):
            p.line(x1, y1, x2, y2)
        p.lines(80, 680, 11, 14, [f"Slide {n} says the optimiser takes a step in the", "direction of the negative gradient each time."])
        p.text(80, 410, "Course name", size=9)
        p.text(310, 410, "Topic name", size=9)
    _, text = ingest.from_file("slides.pdf", pdf.to_bytes())
    assert "| --- |" not in text
    assert "takes a step in the direction of the negative gradient each time." in text

