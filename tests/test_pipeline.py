from pathlib import Path
from urllib.parse import quote

import httpx
import pymupdf

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.fetch import LIST_URL
from cheongyak_extract.pipeline import run

FIXTURES = Path(__file__).parent / "fixtures"


def make_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "입주자모집공고 1쪽")
    doc.new_page().insert_text((72, 72), "2쪽")
    data = doc.tobytes()
    doc.close()
    return data


def make_transport(pdf_names: list[str]) -> httpx.MockTransport:
    """PDF 요청이 올 때마다 pdf_names를 차례로 파일명으로 쓴다."""
    list_html = (FIXTURES / "list.html").read_bytes()
    detail_html = (FIXTURES / "detail.html").read_bytes()
    pdf = make_pdf_bytes()
    names = iter(pdf_names)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, content=detail_html)
        if str(request.url) == LIST_URL:
            return httpx.Response(200, content=list_html)
        return httpx.Response(
            200,
            content=pdf,
            headers={"content-disposition": f'attachment; filename="{quote(next(names))}"'},
        )

    return httpx.MockTransport(handler)


def test_run_goes_from_fetch_to_report_with_stub_values(tmp_path):
    report_path = tmp_path / "reports" / "skeleton.md"
    with httpx.Client(transport=make_transport(["a.pdf"] * 3)) as client:
        result = run(3, client, tmp_path / "raw", report_path, pause=lambda s: None)

    assert result.processed == 3 and result.skipped == []
    assert [m.field for m in result.metrics] == list(FIELDS)
    for m in result.metrics:
        assert m.with_truth >= 1
        assert m.accuracy == 0.0 and m.blank == 1.0
        assert m.fabricated == 0 and m.filled_empty == 0
    for pbno in ("2026000532", "2026000531", "2026000530"):
        assert (tmp_path / "raw" / pbno / "notice.pdf").exists()
    text = report_path.read_text(encoding="utf-8")
    assert "| 필드 | 정답 있음 | 정확도 |" in text
    assert "| 공급위치 | 3 | 0% | 100% | 0 | 0 | — |" in text


def test_run_skips_non_pdf_and_reports_reason(tmp_path):
    report_path = tmp_path / "skeleton.md"
    with httpx.Client(transport=make_transport(["a.hwp", "b.pdf", "c.pdf"])) as client:
        result = run(2, client, tmp_path / "raw", report_path, pause=lambda s: None)

    assert result.processed == 2
    assert [pbno for pbno, _ in result.skipped] == ["2026000532"]
    assert "건너뛴 공고" in report_path.read_text(encoding="utf-8")


def test_run_skips_announcement_when_download_fails(tmp_path):
    list_html = (FIXTURES / "list.html").read_bytes()
    detail_html = (FIXTURES / "detail.html").read_bytes()
    pdf = make_pdf_bytes()
    posts = iter([500, 200, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            status = next(posts)
            return httpx.Response(status, content=detail_html if status == 200 else b"")
        if str(request.url) == LIST_URL:
            return httpx.Response(200, content=list_html)
        return httpx.Response(
            200, content=pdf, headers={"content-disposition": 'attachment; filename="a.pdf"'}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run(2, client, tmp_path / "raw", tmp_path / "r.md", pause=lambda s: None)

    assert result.processed == 2
    assert result.skipped[0][0] == "2026000532" and "다운로드 실패" in result.skipped[0][1]
