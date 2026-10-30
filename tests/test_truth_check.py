import json
import shutil
from pathlib import Path

import pytest

from cheongyak_extract.extract import FIELDS as ALL_FIELDS
from cheongyak_extract.truth_check import (
    Checked,
    Reread,
    cause,
    check_cells,
    llm_values,
    render,
    reread,
    run_check,
)
from pdfs import make_pdf

FIELDS = ("공급규모", "시공사", "입주예정월")
PB = "2026000001"
TRUTH = {PB: {"공급규모": "100세대", "시공사": "(주)가나건설", "입주예정월": "2026.10"}}
PAGES = {PB: ["표지", "공급규모 : 100세대\n시공사 : 가나건설 주식회사\n입주 2026년 10월"]}


def cell(value, quote=None, page=None, note=None):
    return {"value": value, "quote": quote, "page": page, "note": note}


def labels(**over):
    base = {
        "공급규모": cell("100", "공급규모 : 100세대", 2),
        "시공사": cell("가나건설 주식회사", "시공사 : 가나건설 주식회사", 2),
        "입주예정월": cell("2026년 10월", "입주 2026년 10월", 2),
    }
    return {PB: {**base, **over}}


def run(lab, fields=FIELDS, cells=3, truth=TRUTH, pages=PAGES):
    return check_cells(lab, truth, pages, fields, cells)


def by_field(result):
    return {c.field: c for c in result}


def test_same_after_normalize_counts_as_same():
    got = by_field(run(labels()))
    # "100세대" vs "100", "(주)가나건설" vs "가나건설 주식회사", "2026.10" vs "2026년 10월"
    assert all(c.same for c in got.values())
    assert not any(c.ungrounded for c in got.values())


def test_different_value_is_not_same_and_keeps_both_values():
    got = by_field(run(labels(공급규모=cell("90", "공급규모 : 100세대", 2, "다른 값: 예"))))
    c = got["공급규모"]
    assert (c.same, c.html, c.pdf, c.note) == (False, "100세대", "90", "다른 값: 예")


def test_value_missing_in_pdf_is_not_same():
    c = by_field(run(labels(시공사=cell(None, note="PDF에 없음: 전 쪽"))))["시공사"]
    assert (c.same, c.pdf, c.page, c.ungrounded) == (False, None, None, False)


def test_quote_not_on_that_page_is_ungrounded():
    c = by_field(run(labels(공급규모=cell("100", "공급규모 : 100세대", 1))))["공급규모"]
    assert c.ungrounded and c.same


def test_page_out_of_range_is_ungrounded():
    c = by_field(run(labels(공급규모=cell("100", "공급규모 : 100세대", 9))))["공급규모"]
    assert c.ungrounded


def test_quote_matches_across_line_breaks():
    lab = labels(공급규모=cell("100", "공급규모:100 세대", 2))
    assert not by_field(run(lab))["공급규모"].ungrounded


@pytest.mark.parametrize(
    "bad",
    [
        cell("100", None, 2),  # 값은 있는데 근거가 없다
        cell("100", "공급규모 : 100세대", None),  # 쪽이 없다
        cell(None, "공급규모 : 100세대", 2),  # 값이 없는데 근거가 있다
        {"value": "100", "quote": "공급규모 : 100세대", "page": 2},  # note 키가 없다
        cell("100", "공급규모 : 100세대", "2"),  # 쪽이 문자열이다
        cell("100", "공급규모 : 100세대", 0),  # 쪽은 1부터다
        cell("100", "공급규모 : 100세대", True),  # bool은 쪽 번호가 아니다
        cell(100, "공급규모 : 100세대", 2),  # 값이 문자열이 아니다
        cell("", "", None),  # 빈 문자열은 null로 적는다
        cell("  ", "  ", None),
        cell("100", "  ", 2),
    ],
)
def test_malformed_label_cell_raises(bad):
    with pytest.raises(ValueError):
        run(labels(공급규모=bad))


def test_missing_field_raises():
    lab = labels()
    del lab[PB]["시공사"]
    with pytest.raises(ValueError, match="시공사"):
        run(lab)


def test_missing_notice_raises():
    with pytest.raises(ValueError, match="2026000002"):
        run(labels(), truth={**TRUTH, "2026000002": TRUTH[PB]}, pages={**PAGES, "2026000002": [""]})


def test_extra_field_in_labels_raises():
    lab = labels()
    lab[PB]["계약일"] = cell(None)
    with pytest.raises(ValueError, match="계약일"):
        run(lab)


def test_cell_count_must_match_expected():
    # 빈 파일이 「0/0」으로 깨끗해 보이지 않게 한다
    with pytest.raises(ValueError, match="160"):
        run(labels(), cells=160)
    with pytest.raises(ValueError, match="0"):
        check_cells({}, {}, {}, FIELDS, 3)


# ---- Task 2: 리포트와 명령 ----


def test_cause_reads_the_note_prefix():
    assert cause("표기 차이: 쉼표 하나") == "표기 차이"
    assert cause("PDF에 없음: 전 쪽") == "PDF에 없음"
    assert cause("정정: 2쪽 정정 공고") == "정정"
    assert cause("다른 값: 예") == "다른 값"
    assert cause(None) == "원인 미기재"
    assert cause("그냥 메모") == "원인 미기재"


LLM_MD = """\
틀리게 채운 칸:

| 공고 | 필드 | 정답 | 추출값 | 근거 | 쪽 |
| --- | --- | --- | --- | --- | --- |
| 2026000001 | 공급규모 | 100세대 | 90세대 | 근거 | 2 |
| 2026000001 | 시공사 | (주)가나건설 | 가나건설 \\| 다라건설 | 근거 | 2 |

토큰:
"""


def test_llm_values_reads_the_extracted_column_with_escaped_bars():
    assert llm_values(LLM_MD) == {
        ("2026000001", "공급규모"): "90세대",
        ("2026000001", "시공사"): "가나건설 | 다라건설",
    }


def test_reread_compares_extracted_value_with_pdf_value_after_normalize():
    cells = run(labels(공급규모=cell("90", "공급규모 : 100세대", 2)))
    got = reread(
        cells,
        {(PB, "공급규모"): "90세대", (PB, "시공사"): "다라건설"},
    )
    assert got == [
        Reread(PB, "공급규모", "90세대", "90", True),
        Reread(PB, "시공사", "다라건설", "가나건설 주식회사", False),
    ]


def test_render_top_lines_causes_fields_and_unequal_cells():
    cells = run(
        labels(
            공급규모=cell("90", "공급규모 : 100세대", 2, "다른 값: 예"),
            시공사=cell(None, note="PDF에 없음: 전 쪽"),
            입주예정월=cell("2026년 10월", "없는 문장", 2),
        )
    )
    md = render(Checked(cells, [Reread(PB, "공급규모", "90세대", "90", True)], []), FIELDS)
    assert "정규화 뒤 같은 칸: 1/3 (33.3%)" in md
    assert "근거를 그 쪽에서 못 찾은 칸: 1" in md
    assert "| 다른 값 | 1 |" in md and "| PDF에 없음 | 1 |" in md
    assert "| 표기 차이 | 0 |" in md and "| 정정 | 0 |" in md
    assert "| 공급규모 | 1 | 0 |" in md  # 필드별: 칸 1, 같은 칸 0
    assert "| 입주예정월 | 1 | 1 |" in md
    # 같지 않은 칸 전부: HTML 값·PDF 값·쪽·note
    assert "| 2026000001 | 공급규모 | 100세대 | 90 | 2 | 다른 값: 예 |" in md
    assert "| 2026000001 | 시공사 | (주)가나건설 | — | — | PDF에 없음: 전 쪽 |" in md
    # 합계 줄
    assert "LLM 1칸 중 PDF 값과 같은 칸 1" in md
    assert "정규식 0칸 중 PDF 값과 같은 칸 0" in md


def test_render_reference_ratio_counts_notation_differences_as_same():
    cells = run(labels(공급규모=cell("90", "공급규모 : 100세대", 2, "표기 차이: 가짜")))
    md = render(Checked(cells, [], []), FIELDS)
    assert "표기 차이를 같은 칸으로 쳤을 때: 3/3 (100.0%)" in md


def test_render_lists_ungrounded_cells_with_their_quote():
    cells = run(labels(공급규모=cell("100", "없는 문장", 2)))
    md = render(Checked(cells, [], []), FIELDS)
    assert "| 2026000001 | 공급규모 | 2 | 없는 문장 |" in md


RAW_HTML = Path("tests/fixtures/detail.html")
EXTRACT_NEW = """\
| C | 8 | 7 (88%) | 0 (0%) | 1 (12%) |
| 공급위치 | 8 | 7 (88%) | 7 (88%) | 7 (88%) |

틀리게 채운 칸:

| 공고 | 필드 | 정답 | 추출값 | 근거 | 쪽 |
| --- | --- | --- | --- | --- | --- |
| 2026000001 | 공급규모 | 496세대 | 400세대 | 근거 | 1 |

토큰:
"""


def write_raw(tmp_path):
    raw = tmp_path / "raw" / PB
    raw.mkdir(parents=True)
    shutil.copy(RAW_HTML, raw / "detail.html")
    (raw / "notice.pdf").write_bytes(make_pdf("supply 496"))
    md = tmp_path / "extract-new.md"
    md.write_text(EXTRACT_NEW, encoding="utf-8")
    lab = {
        PB: {
            f: {"value": None, "quote": None, "page": None, "note": "PDF에 없음: 시험"}
            for f in ALL_FIELDS
        }
    }
    lab[PB]["공급규모"] = cell("496", "supply 496", 1)
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(lab, ensure_ascii=False), encoding="utf-8")
    return tmp_path / "raw", path, md


def test_run_check_writes_the_report_from_files_without_network(tmp_path):
    raw, labels_path, md = write_raw(tmp_path)
    out = tmp_path / "out" / "truth-check.md"
    got = run_check([PB], raw, labels_path, md, out, expected=8)
    text = out.read_text(encoding="utf-8")
    assert "정규화 뒤 같은 칸: 1/8 (12.5%)" in text
    assert "근거를 그 쪽에서 못 찾은 칸: 0" in text
    assert len(got.cells) == 8
    assert [(r.field, r.same) for r in got.llm] == [("공급규모", False)]


def test_run_check_with_wrong_cell_count_raises(tmp_path):
    raw, labels_path, md = write_raw(tmp_path)
    with pytest.raises(ValueError, match="160"):
        run_check([PB], raw, labels_path, md, tmp_path / "x.md")  # 기본 160칸


def test_run_check_raises_when_regex_skips_a_notice(tmp_path):
    raw, labels_path, md = write_raw(tmp_path)
    (raw / PB / "notice.pdf").write_bytes(make_pdf(""))  # 텍스트가 없어 정규식이 건너뛴다
    with pytest.raises(ValueError, match=PB):
        run_check([PB], raw, labels_path, md, tmp_path / "x.md", expected=8)


def test_llm_values_keeps_a_value_with_a_form_feed_whole():
    row = "| 2026000001 | 공급규모 | 496세대 | 서울시\x0c강남구 | 근거 | 1 |"
    md = f"틀리게 채운 칸:\n\n{row}\n\n토큰:\n"
    assert llm_values(md) == {("2026000001", "공급규모"): "서울시\x0c강남구"}


def test_llm_values_rejects_a_row_that_does_not_split_into_six_columns():
    md = "틀리게 채운 칸:\n\n| 2026000001 | 공급규모 | 496세대 | 경기도 A\\ | 근거 | 1 |\n\n토큰:\n"
    with pytest.raises(ValueError, match="열"):
        llm_values(md)


@pytest.mark.parametrize("bad", [[], {PB: []}])
def test_labels_with_the_wrong_shape_raise_value_error(bad):
    with pytest.raises(ValueError, match="객체"):
        check_cells(bad, TRUTH, PAGES, FIELDS, 3)
