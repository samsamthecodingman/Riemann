"""A .docx is a zip: its inflated size must be checked, not just its file size."""

import io
import zipfile

import pytest

from riemann.abstraction import ingest


def _docx(xml_len: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:document xmlns:w='x'><w:body>" + "a" * xml_len + "</w:body></w:document>")
    return buf.getvalue()


def test_docx_zip_bomb_is_refused_by_declared_size():
    bomb = _docx(ingest.MAX_DOCX_XML_BYTES + 1000)  # a few KB compressed, huge when inflated
    assert len(bomb) < 100_000
    with pytest.raises(ValueError, match="too large"):
        ingest.from_file("bomb.docx", bomb)


def test_normal_docx_still_reads():
    ok = _docx(1000)
    title, text = ingest.from_file("ok.docx", ok)
    assert isinstance(text, str)
