import json
from pathlib import Path
from urllib.parse import quote

import httpx
import pymupdf
import pytest

from cheongyak_extract import pipeline
from cheongyak_extract.extract import FIELDS, Usage
from cheongyak_extract.fetch import LIST_URL
from cheongyak_extract.llm import BadResponse, ContextExceeded
from cheongyak_extract.pipeline import evaluate, run

FIXTURES = Path(__file__).parent / "fixtures"


def blank_ask(prompt: str) -> str:
    return json.dumps({f: {"value": None, "evidence": None, "page": None} for f in FIELDS})


def scale_ask(prompt: str) -> str:
    """공급규모만 PDF 1쪽 문장에서 채우는 가짜 LLM."""
    body = {f: {"value": None, "evidence": None, "page": None} for f in FIELDS}
    body["공급규모"] = {"value": "496세대", "evidence": "일반분양 496세대", "page": 1}
    return json.dumps(body, ensure_ascii=False)


class CountingAsk:
    """토큰 수를 last_usage에 남기는 가짜 LLM(llm.LlmAsk와 같은 모양)."""

    model = "fake-model"

    def __init__(self):
        self.last_usage = None
        self.n = 0

    def __call__(self, prompt: str) -> str:
        self.n += 1
        self.last_usage = Usage(1000 * self.n, 10)
        return scale_ask(prompt)


def make_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "입주자모집공고 일반분양 496세대", fontname="korea")
    doc.new_page().insert_text((72, 72), "2쪽", fontname="korea")
    data = doc.tobytes()
    doc.close()
    return data


def make_transport(pdf_names: list[str], pdf: bytes | None = None) -> httpx.MockTransport:
    """PDF 요청이 올 때마다 pdf_names를 차례로 파일명으로 쓴다."""
    list_html = (FIXTURES / "list.html").read_bytes()
    detail_html = (FIXTURES / "detail.html").read_bytes()
    pdf = pdf if pdf is not None else make_pdf_bytes()
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


def test_run_goes_from_fetch_to_report_with_fake_llm_values(tmp_path, capsys):
    report_path = tmp_path / "reports" / "skeleton.md"
    with httpx.Client(transport=make_transport(["a.pdf"] * 3)) as client:
        result = run(3, client, tmp_path / "raw", report_path, scale_ask, pause=lambda s: None)

    assert result.processed == 3 and result.skipped == []
    assert [m.field for m in result.metrics] == list(FIELDS)
    for m in result.metrics:
        assert m.with_truth >= 1
        assert m.fabricated == 0 and m.filled_empty == 0
        scale = m.field == "공급규모"
        assert m.accuracy == (1.0 if scale else 0.0) and m.blank == (0.0 if scale else 1.0)
    for pbno in ("2026000532", "2026000531", "2026000530"):
        assert (tmp_path / "raw" / pbno / "notice.pdf").exists()
    text = report_path.read_text(encoding="utf-8")
    assert "| 필드 | 정답 있음 | 정확도 |" in text
    assert "| 공급위치 | 3 | 0% | 100% | 0 | 0 | — | 0 | 0 |" in text
    assert "| 공급규모 | 3 | 100% | 0% | 0 | 0 | 100% | 0 | 0 |" in text
    assert "틀리게 채운 칸 없음" in text
    assert capsys.readouterr().out.strip() == text.strip()


def test_run_skips_non_pdf_and_reports_reason(tmp_path):
    report_path = tmp_path / "skeleton.md"
    with httpx.Client(transport=make_transport(["a.hwp", "b.pdf", "c.pdf"])) as client:
        result = run(2, client, tmp_path / "raw", report_path, blank_ask, pause=lambda s: None)

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
        result = run(
            2, client, tmp_path / "raw", tmp_path / "r.md", blank_ask, pause=lambda s: None
        )

    assert result.processed == 2
    assert result.skipped[0][0] == "2026000532" and "다운로드 실패" in result.skipped[0][1]


def test_run_skips_announcement_when_pdf_is_corrupt(tmp_path):
    transport = make_transport(["a.pdf"] * 3, pdf=b"not a pdf")
    with httpx.Client(transport=transport) as client:
        result = run(
            3, client, tmp_path / "raw", tmp_path / "r.md", blank_ask, pause=lambda s: None
        )
    assert result.processed == 0
    assert len(result.skipped) == 3 and "PDF" in result.skipped[0][1]


def test_run_pauses_two_seconds_before_every_request(tmp_path):
    pauses: list[float] = []
    with httpx.Client(transport=make_transport(["a.pdf"] * 3)) as client:
        run(3, client, tmp_path / "raw", tmp_path / "r.md", blank_ask, pause=pauses.append)
    # 목록 1회 + 공고마다 (상세 1회 + PDF 1회)
    assert pauses == [2] * (1 + 3 * 2)


def make_raw(raw: Path, pbno: str, pdf: bytes | None = None, detail: bool = True) -> None:
    (raw / pbno).mkdir(parents=True)
    if detail:
        (raw / pbno / "detail.html").write_bytes((FIXTURES / "detail.html").read_bytes())
    if pdf is not None:
        (raw / pbno / "notice.pdf").write_bytes(pdf)


def blank_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page()  # 텍스트가 0자인 스캔 PDF를 흉내낸다
    data = doc.tobytes()
    doc.close()
    return data


def test_run_skips_scanned_pdf_without_calling_llm(tmp_path):
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return blank_ask(prompt)

    transport = make_transport(["a.pdf"] * 3, pdf=blank_pdf_bytes())
    with httpx.Client(transport=transport) as client:
        result = run(3, client, tmp_path / "raw", tmp_path / "r.md", ask, pause=lambda s: None)
    assert result.processed == 0 and calls == []
    assert "텍스트 없음(스캔 PDF로 보임)" in result.skipped[0][1]


def test_run_skips_announcement_when_pdf_text_extraction_raises_other_errors(tmp_path, monkeypatch):
    def boom(path):
        raise RuntimeError("잘못된 쪽 트리")

    monkeypatch.setattr(pipeline, "pages", boom)
    with httpx.Client(transport=make_transport(["a.pdf"] * 3)) as client:
        result = run(2, client, tmp_path / "raw", tmp_path / "r.md", blank_ask, lambda s: None)
    assert result.processed == 0
    assert "PDF를 열 수 없음" in result.skipped[0][1] and "잘못된 쪽 트리" in result.skipped[0][1]


def test_context_overflow_skips_only_that_announcement_and_keeps_the_rest(tmp_path):
    calls = iter([ContextExceeded("450000 tokens"), None, None])

    def ask(prompt):
        if (err := next(calls)) is not None:
            raise err
        return scale_ask(prompt)

    report_path = tmp_path / "r.md"
    with httpx.Client(transport=make_transport(["a.pdf"] * 3)) as client:
        result = run(2, client, tmp_path / "raw", report_path, ask, pause=lambda s: None)
    assert result.processed == 2
    ((pbno, why),) = result.skipped
    assert pbno == "2026000532" and "컨텍스트 한도 초과" in why and "450000" in why
    assert f"- {pbno}: 컨텍스트 한도 초과" in report_path.read_text(encoding="utf-8")


def test_report_has_token_table_and_model(tmp_path):
    transport = make_transport(["a.pdf"] * 3)
    with httpx.Client(transport=transport) as client:
        run(2, client, tmp_path / "raw", tmp_path / "r.md", CountingAsk(), lambda s: None)
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "| 공고 | 입력 토큰 | 출력 토큰 |" in text
    assert "| 2026000532 | 1,000 | 10 |" in text and "| 합계 | 3,000 | 20 |" in text
    assert "모델: fake-model" in text
    assert "정답 있는 칸" in text


def test_evaluate_reads_only_raw_dir_and_writes_report(tmp_path, capsys):
    raw = tmp_path / "raw"
    make_raw(raw, "A1", make_pdf_bytes())
    make_raw(raw, "B2", make_pdf_bytes())
    out = tmp_path / "reports" / "extract.md"
    result = evaluate(["A1", "B2"], raw, scale_ask, out)
    assert result.processed == 2 and result.skipped == []
    text = out.read_text(encoding="utf-8")
    assert "공고 2건: A1, B2" in text
    assert "| 공급규모 | 2 | 100% | 0% | 0 | 0 | 100% | 0 | 0 |" in text
    assert capsys.readouterr().out.strip() == text.strip()


def test_evaluate_skips_announcement_without_pdf_or_detail_and_says_why(tmp_path):
    raw = tmp_path / "raw"
    make_raw(raw, "OK", make_pdf_bytes())
    make_raw(raw, "NOPDF")  # 상세 HTML만 있다
    make_raw(raw, "NODETAIL", make_pdf_bytes(), detail=False)
    out = tmp_path / "e.md"
    result = evaluate(["OK", "NOPDF", "NODETAIL", "MISSING"], raw, scale_ask, out)
    assert result.processed == 1
    reasons = dict(result.skipped)
    assert set(reasons) == {"NOPDF", "NODETAIL", "MISSING"}
    assert "notice.pdf" in reasons["NOPDF"] and "detail.html" in reasons["NODETAIL"]
    assert "건너뛴 공고" in out.read_text(encoding="utf-8")


def test_unusable_llm_response_skips_only_that_announcement(tmp_path):
    raw = tmp_path / "raw"
    make_raw(raw, "A1", make_pdf_bytes())
    make_raw(raw, "B2", make_pdf_bytes())
    answers = iter([BadResponse("응답이 끝나지 않음: incomplete"), None])

    def ask(prompt):
        if (err := next(answers)) is not None:
            raise err
        return scale_ask(prompt)

    out = tmp_path / "e.md"
    result = evaluate(["A1", "B2"], raw, ask, out)
    assert result.processed == 1
    ((pbno, why),) = result.skipped
    assert pbno == "A1" and "응답이 끝나지 않음" in why
    assert "공고 1건: B2" in out.read_text(encoding="utf-8")


def test_report_says_when_a_response_was_not_json(tmp_path):
    raw = tmp_path / "raw"
    make_raw(raw, "A1", make_pdf_bytes())
    out = tmp_path / "e.md"
    result = evaluate(["A1"], raw, lambda prompt: "JSON이 아님", out)
    assert result.processed == 1  # 건너뛴 공고가 아니라 8칸 전부 비운 공고다
    text = out.read_text(encoding="utf-8")
    assert "응답 모양이 깨져 비운 칸" in text
    assert "| A1 | 공급규모 | 응답이 JSON 객체가 아님 |" in text


def test_evaluate_carries_blanked_reasons_and_wrong_cells_into_the_report(tmp_path):
    raw = tmp_path / "raw"
    make_raw(raw, "A1", make_pdf_bytes())
    body = {f: {"value": None, "evidence": None, "page": None} for f in FIELDS}
    # 근거가 1쪽에 없다 -> 규칙 4로 비운다
    body["공급규모"] = {"value": "496세대", "evidence": "1쪽에 없는 문장", "page": 1}
    # 근거는 있지만 값이 정답과 다르다 -> 틀리게 채움
    body["모집공고일"] = {"value": "1999.01.01", "evidence": "입주자모집공고", "page": 1}
    out = tmp_path / "e.md"
    evaluate(["A1"], raw, lambda prompt: json.dumps(body, ensure_ascii=False), out)
    text = out.read_text(encoding="utf-8")
    assert "| 공급규모 | 1 | 0% | 100% | 0 | 0 | — | 0 | 1 |" in text
    assert "| 모집공고일 | 1 | 0% | 0% | 0 | 0 | 100% | 1 | 0 |" in text
    assert "| A1 | 모집공고일 |" in text.split("틀리게 채운 칸:")[1]
    assert "LLM이 값을 준 2칸 중 근거를 확인 못해 비운 칸 1 (50%)" in text


def test_evaluate_stops_on_errors_other_than_skippable_ones(tmp_path):
    # 인증·한도 오류를 공고별 건너뜀으로 삼키면 키가 틀려도 빈 리포트와 exit 1만 남는다
    raw = tmp_path / "raw"
    make_raw(raw, "A1", make_pdf_bytes())

    def ask(prompt):
        raise PermissionError("401")

    with pytest.raises(PermissionError):
        evaluate(["A1"], raw, ask, tmp_path / "e.md")
