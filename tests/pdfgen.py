"""A tiny PDF writer for tests: pages of positioned text and ruling lines,
core fonts only. reportlab is not a dependency, and a test that only shows
what a real generator would do needs nothing more than this.

    pdf = PdfBuilder()
    page = pdf.page()
    page.text(72, 720, "Hello", size=12, bold=True)
    page.line(72, 700, 300, 700)
    data = pdf.to_bytes()
"""
from __future__ import annotations


def _esc(s: str) -> bytes:
    raw = s.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class PdfPage:
    def __init__(self, width: int = 612, height: int = 792) -> None:
        self.width, self.height = width, height
        self.ops: list[bytes] = []

    def text(self, x: float, y: float, s: str, size: float = 11, bold: bool = False) -> None:
        font = b"/F2" if bold else b"/F1"
        self.ops.append(b"BT " + font + b" %g Tf %g %g Td (" % (size, x, y) + _esc(s) + b") Tj ET")

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float = 0.8) -> None:
        self.ops.append(b"%g w %g %g m %g %g l S" % (width, x1, y1, x2, y2))

    def lines(self, x: float, y_top: float, size: float, leading: float, strings: list[str], bold: bool = False) -> float:
        """Stack strings downward from y_top; returns the y of the next free line."""
        y = y_top
        for s in strings:
            self.text(x, y, s, size=size, bold=bold)
            y -= leading
        return y

    def grid(self, x: float, y_top: float, col_widths: list[float], row_height: float, rows: list[list[str]], size: float = 10) -> None:
        """A ruled table: outer box, every row and column line, text in each cell."""
        total_w = sum(col_widths)
        y_bottom = y_top - row_height * len(rows)
        for r in range(len(rows) + 1):
            self.line(x, y_top - r * row_height, x + total_w, y_top - r * row_height)
        cx = x
        for w in [0, *col_widths]:
            cx += w
            self.line(cx, y_top, cx, y_bottom)
        for r, row in enumerate(rows):
            cx = x
            for c, cell in enumerate(row):
                self.text(cx + 4, y_top - (r + 1) * row_height + 5, cell, size=size, bold=(r == 0))
                cx += col_widths[c]


class PdfBuilder:
    def __init__(self) -> None:
        self.pages: list[PdfPage] = []

    def page(self, width: int = 612, height: int = 792) -> PdfPage:
        p = PdfPage(width, height)
        self.pages.append(p)
        return p

    def to_bytes(self) -> bytes:
        objs: list[bytes] = []  # object bodies, 1-based ids

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        catalog = add(b"")  # 1, filled below
        pages_id = add(b"")  # 2
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        page_ids = []
        for p in self.pages:
            stream = b"\n".join(p.ops)
            content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
            page_ids.append(
                add(
                    b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>" % (pages_id, p.width, p.height, content, f1, f2)
                )
            )
        objs[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
        kids = b" ".join(b"%d 0 R" % i for i in page_ids)
        objs[pages_id - 1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(page_ids)

        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for off in offsets:
            out += b"%010d 00000 n \n" % off
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
        return bytes(out)
