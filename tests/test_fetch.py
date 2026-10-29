from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

from cheongyak_extract.fetch import (
    BadPdf,
    Skipped,
    download,
    fetch_notices,
    filename_from_disposition,
    list_url,
    parse_list,
    pdf_links,
)
from pdfs import TRUNCATED_PDF, make_pdf

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


def _transport(pdf_name: str = "공고문.pdf", pdf_bytes: bytes | None = None):
    pdf_bytes = make_pdf() if pdf_bytes is None else pdf_bytes
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
    assert (out / "notice.pdf").read_bytes() == make_pdf()


def test_download_skips_non_pdf_attachment(tmp_path):
    with httpx.Client(transport=_transport(pdf_name="공고문.hwp", pdf_bytes=b"HWP 5.0")) as client:
        with pytest.raises(Skipped, match="PDF"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)


def test_download_skips_when_detail_has_no_pdf_link(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="<html><body>링크 없음</body></html>".encode())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Skipped, match="링크 없음"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)


def test_download_tries_next_link_when_first_is_not_pdf(tmp_path):
    base = "https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do"
    html = f'<a href="{base}?n=1">hwp</a><a href="{base}?n=2">pdf</a>'.encode()
    names = {"n=1": "a.hwp", "n=2": "b.pdf"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, content=html)
        name = names[str(request.url).split("?")[1]]
        disposition = f'attachment; filename="{name}"'
        content = make_pdf(name) if name.endswith(".pdf") else name.encode()
        return httpx.Response(200, content=content, headers={"content-disposition": disposition})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = download(client, "1", "1", "x", tmp_path, pause=lambda s: None)
    assert (out / "notice.pdf").read_bytes() == make_pdf("b.pdf")


# --- fetch_notices: 목록 N쪽부터 PDF 있는 공고를 n건 받는다 ---


def _list_html(pbnos):
    rows = "".join(f'<tr data-pbno="{p}" data-hmno="{p}" data-honm="단지{p}"></tr>' for p in pbnos)
    return f"<table><tbody>{rows}</tbody></table>"


def _site(pages, *, no_pdf=(), status=None):
    """pages: {쪽: [pbno, ...]}. status: {pbno: 상태 또는 "timeout"}. 그 상세 요청이 실패한다."""
    seen = []  # 요청 기록: ("list", 쪽) / ("detail", pbno) / ("pdf", pbno)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ListView" in url:
            page = int(url.rsplit("pageIndex=", 1)[1])
            seen.append(("list", page))
            return httpx.Response(200, text=_list_html(pages.get(page, [])))
        if request.method == "POST":
            pbno = request.content.decode().split("pblancNo=")[1].split("&")[0]
            seen.append(("detail", pbno))
            if (status or {}).get(pbno) == "timeout":
                raise httpx.ReadTimeout("", request=request)
            if pbno in (status or {}):
                return httpx.Response(status[pbno])
            link = (
                "" if pbno in no_pdf else f'<a href="https://x.kr/getAtchmnfl.do?n={pbno}">pdf</a>'
            )
            return httpx.Response(200, text=f"<html>{link}</html>")
        pbno = url.rsplit("n=", 1)[1]
        seen.append(("pdf", pbno))
        return httpx.Response(
            200,
            content=make_pdf(pbno),
            headers={"content-disposition": 'attachment; filename="a.pdf"'},
        )

    return httpx.MockTransport(handler), seen


def _fetch(tmp_path, pages, start_page=2, n=2, **site):
    transport, seen = _site(pages, **site)
    sleeps = []
    with httpx.Client(transport=transport) as client:
        result = fetch_notices(client, tmp_path, start_page, n, pause=sleeps.append)
    return result, seen, sleeps


def test_fetch_notices_starts_at_the_given_page_and_stops_at_n(tmp_path):
    result, seen, _ = _fetch(tmp_path, {1: ["A"], 2: ["B", "C", "D"]})
    assert result.fetched == ["B", "C"]
    assert result.stopped is None
    assert ("list", 1) not in seen and ("detail", "D") not in seen
    assert (tmp_path / "B" / "notice.pdf").read_bytes() == make_pdf("B")


def test_fetch_notices_goes_on_to_the_next_page_when_one_is_not_enough(tmp_path):
    result, seen, _ = _fetch(tmp_path, {2: ["B"], 3: ["C"]}, n=2)
    assert result.fetched == ["B", "C"]
    assert [s for s in seen if s[0] == "list"] == [("list", 2), ("list", 3)]


def test_fetch_notices_skips_notices_that_already_have_a_pdf_and_2026000531(tmp_path):
    (tmp_path / "B").mkdir()
    (tmp_path / "B" / "notice.pdf").write_bytes(make_pdf("old"))
    result, seen, _ = _fetch(tmp_path, {2: ["B", "2026000531", "C", "D"]})
    assert result.fetched == ["C", "D"]
    assert (tmp_path / "B" / "notice.pdf").read_bytes() == make_pdf("old")
    assert not any(s[1] in ("B", "2026000531") for s in seen if s[0] != "list")


def test_fetch_notices_does_not_count_notices_without_a_pdf(tmp_path):
    result, _, _ = _fetch(tmp_path, {2: ["B", "C", "D"]}, no_pdf=("B",))
    assert result.fetched == ["C", "D"]
    assert result.skipped == [("B", "상세에 공고문 링크 없음")]


def test_fetch_notices_ends_when_the_list_runs_out(tmp_path):
    result, _, _ = _fetch(tmp_path, {2: ["B"]}, n=5)
    assert result.fetched == ["B"]
    assert result.stopped == "목록 끝"


def test_fetch_notices_pauses_two_seconds_before_every_request(tmp_path):
    result, seen, sleeps = _fetch(tmp_path, {2: ["B"]}, n=1)
    assert len(sleeps) == len(seen) == 3  # 목록, 상세, PDF
    assert set(sleeps) == {2}


@pytest.mark.parametrize("code", [403, 429])
def test_fetch_notices_stops_after_three_blocks_in_a_row(tmp_path, code):
    pages = {2: ["B", "C", "D", "E", "F"]}
    result, seen, _ = _fetch(
        tmp_path, pages, n=5, status={"C": code, "D": code, "E": code, "F": code}
    )
    assert result.fetched == ["B"]
    assert result.stopped == f"{code} 3번 연속"
    assert ("detail", "F") not in seen


def test_fetch_notices_resets_the_block_count_after_a_success(tmp_path):
    pages = {2: ["B", "C", "D", "E", "F"]}
    result, _, _ = _fetch(tmp_path, pages, n=3, status={"B": 429, "C": 429, "E": 403, "F": 403})
    assert result.fetched == ["D"]
    assert result.stopped == "목록 끝"


def test_fetch_notices_does_not_stop_on_other_http_errors_however_many(tmp_path):
    pages = {2: ["B", "C", "D", "E", "F"]}
    result, _, _ = _fetch(tmp_path, pages, n=5, status={"B": 500, "C": 500, "D": 500, "E": 500})
    assert result.fetched == ["F"]
    assert result.stopped == "목록 끝"
    assert [p for p, _ in result.skipped] == ["B", "C", "D", "E"]
    assert all("500" in why for _, why in result.skipped)


def test_fetch_notices_counts_only_consecutive_blocks_so_another_error_resets_the_count(tmp_path):
    pages = {2: ["B", "C", "D", "E", "F"]}
    status = {"B": 403, "C": 500, "D": 403, "E": 403, "F": 429}
    result, _, _ = _fetch(tmp_path, pages, n=5, status=status)
    assert result.fetched == []
    assert result.stopped == "429 3번 연속"  # D·E·F가 이어진 3번. B와 D 사이에 500이 끼어 있다


def test_fetch_notices_counts_a_blocked_list_page_and_stops_after_three(tmp_path):
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(str(request.url))
        return httpx.Response(429)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_notices(client, tmp_path, 2, 5, pause=lambda s: None)
    assert len(attempts) == 3
    assert result.fetched == [] and result.stopped == "429 3번 연속"


def test_fetch_notices_stops_on_a_list_page_error_that_is_not_a_block(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_notices(client, tmp_path, 2, 5, pause=lambda s: None)
    assert result.fetched == [] and "목록 2쪽 요청 실패" in result.stopped


def test_list_url_takes_the_page_index():
    assert list_url(2).endswith("selectAPTLttotPblancListView.do?pageIndex=2")


def test_fetch_notices_names_the_exception_type_because_a_timeout_has_an_empty_message(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_notices(client, tmp_path, 2, 5, pause=lambda s: None)
    assert "ReadTimeout" in result.stopped


def test_fetch_notices_does_not_call_an_empty_first_page_the_end_of_the_list(tmp_path):
    result, _, _ = _fetch(tmp_path, {}, n=5)  # 200인데 공고 행이 없다: 차단 페이지나 마크업 변경
    assert result.fetched == []
    assert result.stopped != "목록 끝"
    assert "비어 있음" in result.stopped


def test_fetch_notices_stops_when_a_later_page_repeats_rows_it_has_seen(tmp_path):
    # 범위 밖 pageIndex가 마지막 쪽을 되돌려주면 seen이 걸러 끝낸다. 걸러 내지 않으면 끝없이 돈다
    result, _, _ = _fetch(tmp_path, {2: ["B"], 3: ["B"], 4: ["B"]}, n=5)
    assert result.fetched == ["B"]
    assert result.stopped == "목록 끝"


def test_fetch_notices_a_timeout_between_blocks_resets_the_block_count(tmp_path):
    pages = {2: ["B", "C", "D", "E", "F"]}
    status = {"B": 403, "C": 403, "D": "timeout", "E": 403, "F": 403}
    result, _, _ = _fetch(tmp_path, pages, n=5, status=status)
    assert result.stopped == "목록 끝"  # 403이 둘, 시간 초과, 403이 둘: 3번 연속이 아니다
    assert [p for p, _ in result.skipped] == ["B", "C", "D", "E", "F"]


# --- 잘린 PDF를 남기지 않는다 ---


def test_download_does_not_leave_a_truncated_pdf_or_a_part_file(tmp_path):
    with httpx.Client(transport=_transport(pdf_bytes=TRUNCATED_PDF)) as client:
        with pytest.raises(BadPdf, match="열리지 않는 PDF"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)
    out = tmp_path / "2026000532"
    assert not (out / "notice.pdf").exists()
    assert not (out / "notice.pdf.part").exists()


def test_a_notice_whose_pdf_does_not_open_counts_as_skipped_not_fetched(tmp_path):
    pdf_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "ListView" in str(request.url):
            return httpx.Response(200, text=_list_html(["B", "C"]))
        if request.method == "POST":
            return httpx.Response(200, text='<a href="https://x.kr/getAtchmnfl.do?n=1">pdf</a>')
        pdf_requests.append(request)
        content = TRUNCATED_PDF if len(pdf_requests) == 1 else make_pdf()
        return httpx.Response(
            200, content=content, headers={"content-disposition": 'attachment; filename="a.pdf"'}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_notices(client, tmp_path, 1, 1, pause=lambda s: None)
    assert result.fetched == ["C"]
    assert [p for p, _ in result.skipped] == ["B"]
    assert "열리지 않는 PDF" in result.skipped[0][1]
    assert not (tmp_path / "B" / "notice.pdf").exists()


def test_fetch_notices_requests_again_when_the_pdf_on_disk_does_not_open(tmp_path):
    (tmp_path / "B").mkdir()
    (tmp_path / "B" / "notice.pdf").write_bytes(TRUNCATED_PDF)
    result, seen, _ = _fetch(tmp_path, {2: ["B"]}, n=1)
    assert result.fetched == ["B"]
    assert ("detail", "B") in seen
    assert (tmp_path / "B" / "notice.pdf").read_bytes() == make_pdf("B")


# --- PDF 판정: 파일 이름이 .pdf이거나 본문이 %PDF-로 시작한다 ---


def test_download_accepts_a_body_that_starts_with_pdf_magic_without_content_disposition(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, content=(FIXTURES / "detail.html").read_bytes())
        return httpx.Response(200, content=make_pdf())  # content-disposition 없음

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)
    assert (out / "notice.pdf").read_bytes() == make_pdf()


def test_download_still_skips_when_neither_the_name_nor_the_body_says_pdf(tmp_path):
    with httpx.Client(transport=_transport(pdf_name="a.hwp", pdf_bytes=b"HWP 5.0")) as client:
        with pytest.raises(Skipped, match="PDF가 아님"):
            download(client, "2026000532", "2026000532", "계양", tmp_path, pause=lambda s: None)


# --- 일시 오류는 두 번까지 다시 시도한다(5초, 15초 쉰 뒤) ---


def _flaky_site(fail: dict[str, list]):
    """fail: {"list"|"detail"|"pdf": [앞 요청부터 차례로 낼 실패: 상태 코드 또는 예외 클래스]}."""
    queues = {kind: list(seq) for kind, seq in fail.items()}
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        kind = "list" if "ListView" in url else "detail" if request.method == "POST" else "pdf"
        requests.append(kind)
        if queues.get(kind):
            failure = queues[kind].pop(0)
            if isinstance(failure, type):
                raise failure("", request=request)
            return httpx.Response(failure)
        if kind == "list":
            return httpx.Response(200, text=_list_html(["B"] if "pageIndex=2" in url else []))
        if kind == "detail":
            return httpx.Response(200, text='<a href="https://x.kr/getAtchmnfl.do?n=1">pdf</a>')
        return httpx.Response(
            200,
            content=make_pdf("B"),
            headers={"content-disposition": 'attachment; filename="a.pdf"'},
        )

    return httpx.MockTransport(handler), requests


def _flaky_fetch(tmp_path, fail, n=1):
    transport, requests = _flaky_site(fail)
    sleeps = []
    with httpx.Client(transport=transport) as client:
        result = fetch_notices(client, tmp_path, 2, n, pause=sleeps.append)
    return result, requests, sleeps


@pytest.mark.parametrize("kind", ["list", "detail", "pdf"])
def test_a_500_twice_then_a_200_is_received_and_counts_two_retries(tmp_path, kind):
    result, requests, sleeps = _flaky_fetch(tmp_path, {kind: [500, 500]})
    assert result.fetched == ["B"] and result.skipped == [] and result.stopped is None
    assert result.retries == {kind: 2}
    assert requests.count(kind) == 3
    assert [s for s in sleeps if s != 2] == [5, 15]  # 첫 재시도 전 5초, 두 번째 전 15초


@pytest.mark.parametrize("exc", [httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError])
def test_a_timeout_or_dropped_connection_is_retried(tmp_path, exc):
    result, _, _ = _flaky_fetch(tmp_path, {"pdf": [exc]})
    assert result.fetched == ["B"] and result.retries == {"pdf": 1}


def test_three_500s_in_a_row_skip_that_notice_after_two_retries(tmp_path):
    result, requests, _ = _flaky_fetch(tmp_path, {"detail": [500, 500, 500]})
    assert result.fetched == []
    assert [p for p, _ in result.skipped] == ["B"] and "500" in result.skipped[0][1]
    assert result.retries == {"detail": 2}
    assert requests.count("detail") == 3  # 세 번째 실패 뒤 더 보내지 않는다


@pytest.mark.parametrize("code", [403, 429])
def test_blocks_are_not_retried(tmp_path, code):
    result, requests, _ = _flaky_fetch(tmp_path, {"detail": [code]})
    assert result.skipped and f"{code}" in result.skipped[0][1]
    assert result.retries == {}
    assert requests.count("detail") == 1


def test_a_404_is_not_retried(tmp_path):
    result, requests, _ = _flaky_fetch(tmp_path, {"detail": [404]})
    assert result.retries == {} and requests.count("detail") == 1


def test_retries_are_counted_per_request_kind(tmp_path):
    result, _, _ = _flaky_fetch(tmp_path, {"list": [502], "detail": [500, 500], "pdf": [503]})
    assert result.fetched == ["B"]
    assert result.retries == {"list": 1, "detail": 2, "pdf": 1}


def test_download_without_a_counter_still_retries(tmp_path):
    transport, requests = _flaky_site({"detail": [500]})
    with httpx.Client(transport=transport) as client:
        out = download(client, "B", "B", "x", tmp_path, pause=lambda s: None)
    assert (out / "notice.pdf").exists() and requests.count("detail") == 2
