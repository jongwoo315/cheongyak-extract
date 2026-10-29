from cheongyak_extract.raw_check import check_raw, scan
from pdfs import TRUNCATED_PDF, make_pdf

LINK = '<a href="https://x.kr/getAtchmnfl.do?n=1">공고문</a>'


def _notice(raw, pbno, *, detail="<html></html>", pdf=None):
    out = raw / pbno
    out.mkdir(parents=True)
    if detail is not None:
        (out / "detail.html").write_text(detail, encoding="utf-8")
    if pdf is not None:
        (out / "notice.pdf").write_bytes(pdf)


def test_scan_counts_a_notice_collected_only_with_detail_html_and_an_opening_pdf(tmp_path):
    _notice(tmp_path, "A", pdf=make_pdf("A"))
    _notice(tmp_path, "B", pdf=make_pdf("B"))
    result = scan(tmp_path)
    assert result.dirs == 2 and result.collected == ["A", "B"]


def test_scan_lists_a_pdf_that_does_not_open_with_the_reason(tmp_path):
    _notice(tmp_path, "A", pdf=TRUNCATED_PDF)
    result = scan(tmp_path)
    assert result.collected == []
    assert [p for p, _ in result.unreadable] == ["A"] and result.unreadable[0][1]


def test_scan_tells_whether_the_detail_of_a_notice_without_pdf_has_a_link(tmp_path):
    _notice(tmp_path, "A", detail=f"<html>{LINK}</html>")
    _notice(tmp_path, "B", detail="<html>링크 없음</html>")
    _notice(tmp_path, "C", detail=None)
    result = scan(tmp_path)
    assert result.collected == [] and result.unreadable == []
    assert result.no_pdf == [
        ("A", "상세에 공고문 링크 있음"),
        ("B", "상세에 공고문 링크 없음"),
        ("C", "detail.html 없음"),
    ]


def test_scan_does_not_count_an_opening_pdf_without_detail_html(tmp_path):
    _notice(tmp_path, "A", detail=None, pdf=make_pdf())
    result = scan(tmp_path)
    assert result.collected == [] and result.no_detail == ["A"]


def test_scan_ignores_files_and_part_leftovers(tmp_path):
    (tmp_path / ".DS_Store").write_text("")
    _notice(tmp_path, "A", pdf=make_pdf())
    (tmp_path / "A" / "notice.pdf.part").write_bytes(b"x")
    result = scan(tmp_path)
    assert result.dirs == 1 and result.collected == ["A"]


def test_scan_of_a_missing_raw_dir_is_empty(tmp_path):
    assert scan(tmp_path / "none").dirs == 0


def test_check_raw_writes_a_report_with_the_counts_and_the_problem_notices(tmp_path):
    raw = tmp_path / "raw"
    _notice(raw, "A", pdf=make_pdf())
    _notice(raw, "B", pdf=TRUNCATED_PDF)
    _notice(raw, "C", detail="<html>링크 없음</html>")
    out = tmp_path / "reports" / "raw.md"
    result = check_raw(raw, out)
    text = out.read_text(encoding="utf-8")
    assert result.collected == ["A"]
    assert "공고 디렉터리 3개" in text and "수집된 공고 1건" in text
    assert "열리지 않는 PDF 1건" in text and "| B |" in text
    assert "PDF가 없는 공고 1건" in text and "| C | 상세에 공고문 링크 없음 |" in text


def test_check_raw_report_says_none_when_every_pdf_opens(tmp_path):
    raw = tmp_path / "raw"
    _notice(raw, "A", pdf=make_pdf())
    out = tmp_path / "raw.md"
    check_raw(raw, out)
    assert "열리지 않는 PDF 0건" in out.read_text(encoding="utf-8")
