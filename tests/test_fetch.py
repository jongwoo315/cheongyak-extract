from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

from cheongyak_extract.fetch import (
    Skipped,
    download,
    filename_from_disposition,
    parse_list,
    pdf_links,
)

FIXTURES = Path(__file__).parent / "fixtures"
PDF_URL = (
    "https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do"
    "?houseManageNo=2026000532&pblancNo=2026000532&atchmnflSeqNo=2002309&atchmnflSn=4"
)


def test_parse_list_reads_three_attrs_per_row():
    rows = parse_list((FIXTURES / "list.html").read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert rows[0] == ("2026000532", "2026000532", "계양신도시 카이브 유보라(AC4BL)")


def test_pdf_links_returns_absolute_urls():
    html = (FIXTURES / "detail.html").read_text(encoding="utf-8")
    assert pdf_links(html) == [PDF_URL]


def test_filename_from_disposition_decodes_url_encoding():
    header = f'attachment; filename="2026000532 {quote("계양신도시")}.pdf"'
    assert filename_from_disposition(header) == "2026000532 계양신도시.pdf"


def test_filename_from_disposition_decodes_rfc5987_form():
    header = f"attachment; filename*=UTF-8''{quote('2026000518 공고문.pdf')}"
    assert filename_from_disposition(header) == "2026000518 공고문.pdf"


def test_filename_from_disposition_missing_returns_none():
    assert filename_from_disposition(None) is None
    assert filename_from_disposition("attachment") is None


def _transport(pdf_name: str = "공고문.pdf", pdf_bytes: bytes = b"%PDF-1.6 fake"):
    detail = (FIXTURES / "detail.html").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = request.content.decode()
            assert "houseManageNo=2026000532" in body and "pblancNo=2026000532" in body
            return httpx.Response(200, content=detail)
        assert str(request.url) == PDF_URL
        return httpx.Response(
            200,
            content=pdf_bytes,
            headers={
                "content-type": "application/octet-stream",
                "content-disposition": f'attachment; filename="{quote(pdf_name)}"',
            },
        )

    return httpx.MockTransport(handler)


def test_download_writes_detail_and_pdf(tmp_path):
    with httpx.Client(transport=_transport()) as client:
        out = download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)
    assert out == tmp_path / "2026000532"
    assert (out / "detail.html").read_text(encoding="utf-8").count("<table") == 6
    assert (out / "notice.pdf").read_bytes() == b"%PDF-1.6 fake"


def test_download_skips_non_pdf_attachment(tmp_path):
    with httpx.Client(transport=_transport(pdf_name="공고문.hwp")) as client:
        with pytest.raises(Skipped, match="PDF"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)


def test_download_skips_when_detail_has_no_pdf_link(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="<html><body>링크 없음</body></html>".encode())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Skipped, match="링크 없음"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)
