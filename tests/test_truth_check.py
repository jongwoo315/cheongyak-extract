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
    load_judge,
    merge_judge,
    missing_material,
    pick_cells,
    render,
    render_judge,
    reread,
    run_check,
    run_judge,
    ungrounded_judge,
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


def test_run_check_raises_when_the_wrong_cell_table_loses_a_row(tmp_path):
    raw, labels_path, md = write_raw(tmp_path)
    md.write_text(
        EXTRACT_NEW.replace("| 2026000001 | 공급규모 | 496세대 | 400세대 | 근거 | 1 |\n", "")
    )
    with pytest.raises(ValueError, match="틀리게 채운 칸"):
        run_check([PB], raw, labels_path, md, tmp_path / "x.md", expected=8)


# ---- #153 Task 1: 판정할 칸 고르기와 판정 파일 ----


def judge_cell(jw=None, jw_note=None, **over):
    base = {
        "pbno": PB,
        "field": "공급규모",
        "html": "100세대",
        "pdf": "90",
        "quote": "공급규모 : 100세대",
        "page": 2,
        "llm": "100세대",
        "jw": jw,
        "jw_note": jw_note,
    }
    return {**base, **over}


def test_pick_cells_keeps_only_cells_where_a_value_differs():
    # 공급규모: HTML 100세대 · PDF 90 · LLM(표에 없음 = HTML 값) → PDF만 다르다
    # 시공사: 정규화 뒤 셋 다 같다 → 고르지 않는다
    # 입주예정월: HTML·PDF는 같고 LLM만 다르다 → 고른다
    cells = run(labels(공급규모=cell("90", "공급규모 : 100세대", 2)))
    got = pick_cells(cells, {(PB, "입주예정월"): "2026.11"})
    assert [(p["field"], p["html"], p["pdf"], p["llm"]) for p in got] == [
        ("공급규모", "100세대", "90", "100세대"),
        ("입주예정월", "2026.10", "2026년 10월", "2026.11"),
    ]
    assert all(p["jw"] is None and p["jw_note"] is None for p in got)
    assert set(got[0]) == {"pbno", "field", "html", "pdf", "quote", "page", "llm", "jw", "jw_note"}


def test_pick_cells_treats_a_missing_llm_row_as_the_html_value():
    cells = run(labels())
    assert pick_cells(cells, {}) == []


def test_pick_cells_raises_on_an_llm_row_for_a_cell_that_is_not_compared():
    # 표에 필드 이름이 바뀐 행이 남아 있으면 그 행이 판정 파일에서 말없이 빠진다
    cells = run(labels())
    with pytest.raises(ValueError, match="3"):
        pick_cells(cells, {(PB, "없는필드"): "x"})


def test_pick_cells_normalizes_before_comparing():
    # LLM이 표기만 다르게 채운 칸(2026년 10월)은 같은 칸이다
    cells = run(labels())
    assert pick_cells(cells, {(PB, "입주예정월"): "2026년 10월"}) == []


def test_pick_cells_picks_a_cell_the_llm_left_empty():
    cells = run(labels())
    got = pick_cells(cells, {(PB, "시공사"): None})
    assert [(p["field"], p["llm"]) for p in got] == [("시공사", None)]


def write_json(tmp_path, data):
    path = tmp_path / "source-judge.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_judge_accepts_the_four_values_and_null(tmp_path):
    rows = [
        judge_cell(jw=v, field=f"f{i}")
        for i, v in enumerate(["HTML", "PDF", "둘 다", "둘 다 아님", None])
    ]
    assert load_judge(write_json(tmp_path, rows)) == rows


@pytest.mark.parametrize("bad", ["html", "맞음", "", 1, True])
def test_load_judge_rejects_other_jw_values(tmp_path, bad):
    with pytest.raises(ValueError, match="jw"):
        load_judge(write_json(tmp_path, [judge_cell(jw=bad)]))


@pytest.mark.parametrize(
    "bad",
    [
        {"pbno": PB},  # 키가 모자라다
        {**judge_cell(), "extra": 1},  # 키가 남는다
        judge_cell(jw_note=3),  # 메모는 문자열이거나 null
        judge_cell(page="2"),
        judge_cell(page=True),  # bool은 int지만 쪽 번호가 아니다
        judge_cell(page=0),
        judge_cell(page=-1),
        judge_cell(pbno=1),
        judge_cell(quote=3),
        "문자열",  # 객체가 아닌 칸
    ],
)
def test_load_judge_rejects_a_malformed_row(tmp_path, bad):
    with pytest.raises(ValueError, match="판정 파일|공급규모|2026000001"):
        load_judge(write_json(tmp_path, [bad]))


def test_load_judge_rejects_a_non_list(tmp_path):
    with pytest.raises(ValueError, match="목록"):
        load_judge(write_json(tmp_path, {"cells": []}))


def test_merge_judge_without_a_file_returns_the_picked_cells():
    picked = [judge_cell()]
    assert merge_judge(picked, None) == picked


def test_merge_judge_keeps_jw_and_note_from_the_file_and_never_overwrites_them():
    picked = [judge_cell()]
    filled = [judge_cell(jw="PDF", jw_note="PDF 줄이 맞다")]
    got = merge_judge(picked, filled)
    assert (got[0]["jw"], got[0]["jw_note"]) == ("PDF", "PDF 줄이 맞다")


@pytest.mark.parametrize(
    "key,value",
    [
        ("html", "바뀐 값"),
        ("pdf", "낡은 값"),
        ("llm", "바뀐 값"),
        ("quote", "다른 줄"),
        ("page", 9),
    ],
)
def test_merge_judge_raises_when_the_evidence_changed_under_a_saved_verdict(key, value):
    # jw가 본 값과 이번에 읽은 값이 다르면 그 판정을 새 값에 그대로 붙이지 않는다
    filled = [judge_cell(jw="PDF", **{key: value})]
    with pytest.raises(ValueError, match=f"공급규모.*{key}"):
        merge_judge([judge_cell()], filled)


def test_merge_judge_raises_on_a_duplicated_cell_in_the_file():
    with pytest.raises(ValueError, match="두 번"):
        merge_judge([judge_cell()], [judge_cell(jw="HTML"), judge_cell(jw="PDF")])


def test_merge_judge_raises_when_the_cells_differ_from_the_file():
    with pytest.raises(ValueError, match="공급규모"):
        merge_judge([judge_cell(field="시공사")], [judge_cell(jw="HTML")])
    with pytest.raises(ValueError, match="시공사"):
        merge_judge([judge_cell(), judge_cell(field="시공사")], [judge_cell()])


# ---- #153 Task 2: 근거 줄 검사와 리포트 ----


def test_ungrounded_judge_finds_a_quote_missing_from_its_page():
    ok = judge_cell(quote="공급규모 : 100세대", page=2)
    wrong_page = judge_cell(field="시공사", quote="공급규모 : 100세대", page=1)
    out_of_range = judge_cell(field="계약일", quote="공급규모 : 100세대", page=9)
    got = ungrounded_judge([ok, wrong_page, out_of_range], PAGES)
    assert [r["field"] for r in got] == ["시공사", "계약일"]


def test_ungrounded_judge_flags_a_quote_whose_page_is_missing_or_not_a_page_number():
    no_page = judge_cell(field="시공사", quote="공급규모 : 100세대", page=None)
    zero = judge_cell(field="계약일", quote="공급규모 : 100세대", page=0)  # body[-1]을 읽지 않는다
    got = ungrounded_judge([no_page, zero], PAGES)
    assert [r["field"] for r in got] == ["시공사", "계약일"]


def test_ungrounded_judge_does_not_flag_a_cell_without_a_quote():
    # 근거가 아예 없는 칸은 「못 찾은 칸」이 아니라 「재료가 빠진 칸」이다
    assert ungrounded_judge([judge_cell(pdf=None, quote=None, page=None)], PAGES) == []


def test_missing_material_counts_any_empty_value_quote_page_or_llm():
    assert not missing_material(judge_cell())
    for k in ("html", "pdf", "quote", "page", "llm"):
        assert missing_material(judge_cell(**{k: None})), k


def rows3():
    return [
        judge_cell(field="공급규모"),
        judge_cell(field="시공사", html="A건설", pdf="B건설", llm="A건설", quote="q", page=3),
        judge_cell(
            field="시공사", pbno="2026000002", html="C", pdf="D", llm="D", quote="q", page=3
        ),
    ]


def test_render_judge_top_states_the_assumption_and_the_same_cell_count():
    md = render_judge(rows3(), 160, [])
    head = md.split("\n\n## ")[0]
    assert "세 값이 모두 같은 칸은 두 방식 모두 맞다고 본다" in head
    assert "같은 칸 157/160" in head  # 가정 문장 옆에 센다
    assert "판정할 칸 3/160" in md
    assert "청약홈과 OpenAI에 요청하지 않았다" in md


def test_render_judge_lists_each_cell_with_values_page_llm_and_jw():
    rows = rows3()
    rows[1]["jw"] = "PDF"
    md = render_judge(rows, 160, [])
    assert "| 2026000001 | 시공사 | A건설 | B건설 | 3 | A건설 | PDF |" in md
    assert "| 2026000001 | 공급규모 | 100세대 | 90 | 2 | 100세대 | 판정 전 |" in md


def test_render_judge_before_any_judgment_says_so_and_writes_no_totals():
    md = render_judge(rows3(), 160, [])
    assert "jw 판정 전" in md.split("\n\n## ")[0]
    assert "방식별로 맞는 값을 가진 칸" not in md
    assert "| 판정 전 | 3 |" in md
    assert "| HTML | 0 |" in md and "| 둘 다 아님 | 0 |" in md


def test_render_judge_partly_filled_is_still_before_judgment():
    rows = rows3()
    rows[0]["jw"] = "HTML"
    md = render_judge(rows, 160, [])
    assert "jw 판정 전" in md and "방식별로 맞는 값을 가진 칸" not in md
    assert "| HTML | 1 |" in md and "| 판정 전 | 2 |" in md


def test_render_judge_after_judgment_counts_cells_per_method():
    rows = rows3()
    rows[0]["jw"], rows[1]["jw"], rows[2]["jw"] = "HTML", "둘 다", "둘 다 아님"
    md = render_judge(rows, 160, [])
    assert "jw 판정 전" not in md
    # 같은 칸 157 + HTML(1) + 둘 다(1) = 159, PDF는 157 + 둘 다(1) = 158. 둘 다 아님은 안 센다
    assert "- HTML 쪽이 맞는 값을 가진 칸: 159/160" in md
    assert "- PDF 쪽이 맞는 값을 가진 칸: 158/160" in md
    assert "| 판정 전 | 0 |" in md


def test_render_judge_counts_judged_cells_per_field_and_missing_material():
    rows = rows3()
    rows[0]["llm"] = None
    md = render_judge(rows, 160, [])
    assert "| 시공사 | 2 |" in md and "| 공급규모 | 1 |" in md
    assert "| 계약일 | 0 |" in md  # 판정할 칸이 없는 필드도 0으로 센다
    assert "재료(HTML 값·PDF 값·근거 줄·쪽·LLM 값)가 빠진 칸: 1" in md


def test_render_judge_writes_no_method_totals_while_a_quote_is_not_found():
    # 근거 줄이 쪽에 없는데 jw가 판정을 끝냈으면 합계는 근거 없는 판정을 센 숫자다
    rows = rows3()
    for r in rows:
        r["jw"] = "PDF"
    md = render_judge(rows, 160, [rows[0]])
    assert "방식별로 맞는 값을 가진 칸" not in md
    assert "근거 줄을 못 찾은 칸이 있어" in md
    clean = render_judge(rows, 160, [])
    assert "방식별로 맞는 값을 가진 칸" in clean and "근거 줄을 못 찾은 칸이 있어" not in clean


def test_render_judge_lists_ungrounded_cells_with_their_quote():
    rows = rows3()
    md = render_judge(rows, 160, [rows[0]])
    assert "근거 줄을 그 쪽에서 못 찾은 칸: 1" in md
    assert "| 2026000001 | 공급규모 | 2 | 공급규모 : 100세대 |" in md


def test_render_judge_says_there_is_nothing_to_judge():
    md = render_judge([], 160, [])
    assert "판정할 칸 0/160" in md
    assert "없음" in md


def test_render_judge_pdf_only_fields_section_cites_the_reports():
    md = render_judge(rows3(), 160, [])
    sec = md.split("## HTML에 없는 필드")[1]
    for f in ("전매제한 기간", "거주지 우선 비율", "신혼부부 소득 기준"):
        assert f in sec
    assert "HTML 쪽 값이 없다" in sec
    assert "reports/pdf-fields-tune-2.md" in sec and "reports/pdf-resident-test.md" in sec
    assert "| 전매제한 기간 | 47 | 47 |" in sec
    assert "| 거주지 우선 비율 | 49 | 48 |" in sec
    assert "| 거주지 우선 비율 | 30 | 29 |" in sec
    assert "| 신혼부부 소득 기준 | 46 | 42 |" in sec


# ---- #153 Task 3: run_judge ----


def judge_paths(tmp_path):
    raw, labels_path, md = write_raw(tmp_path)
    return raw, labels_path, md, tmp_path / "labels" / "source-judge.json", tmp_path / "r" / "j.md"


def test_run_judge_creates_the_judge_file_with_empty_jw_and_writes_the_report(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    got = run_judge([PB], raw, labels_path, md, judge, out, expected=8)
    filed = json.loads(judge.read_text(encoding="utf-8"))
    assert filed == got.rows
    assert "공급규모" in {r["field"] for r in filed}  # LLM 400세대 · HTML 496세대 · PDF 496
    assert all(r["jw"] is None and r["jw_note"] is None for r in filed)
    text = out.read_text(encoding="utf-8")
    assert "jw 판정 전" in text and f"판정할 칸 {len(filed)}/8" in text
    assert got.total == 8 and got.bad == []


def test_run_judge_reads_the_filled_file_without_overwriting_it(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    first = run_judge([PB], raw, labels_path, md, judge, out, expected=8)
    filed = first.rows
    for r in filed:
        r["jw"], r["jw_note"] = "PDF", "내가 봤다"
    judge.write_text(json.dumps(filed, ensure_ascii=False), encoding="utf-8")
    before = judge.read_text(encoding="utf-8")
    got = run_judge([PB], raw, labels_path, md, judge, out, expected=8)
    assert judge.read_text(encoding="utf-8") == before  # 다시 쓰지 않는다
    assert all((r["jw"], r["jw_note"]) == ("PDF", "내가 봤다") for r in got.rows)
    text = out.read_text(encoding="utf-8")
    assert "jw 판정 전" not in text and "PDF 쪽이 맞는 값을 가진 칸: 8/8" in text


def test_run_judge_report_counts_mixed_verdicts_per_method(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    rows = run_judge([PB], raw, labels_path, md, judge, out, expected=8).rows
    assert len(rows) >= 2
    verdicts = ["HTML"] + ["PDF"] * (len(rows) - 1)
    for r, v in zip(rows, verdicts, strict=True):
        r["jw"] = v
    judge.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    run_judge([PB], raw, labels_path, md, judge, out, expected=8)
    same, n = 8 - len(rows), len(rows)
    text = out.read_text(encoding="utf-8")
    assert f"- HTML 쪽이 맞는 값을 가진 칸: {same + 1}/8" in text
    assert f"- PDF 쪽이 맞는 값을 가진 칸: {same + n - 1}/8" in text


def test_run_judge_rejects_a_bad_jw_value_in_the_file(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    rows = run_judge([PB], raw, labels_path, md, judge, out, expected=8).rows
    rows[0]["jw"] = "html"
    judge.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="jw"):
        run_judge([PB], raw, labels_path, md, judge, out, expected=8)


def test_run_judge_rejects_a_file_whose_cells_differ_from_this_run(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    rows = run_judge([PB], raw, labels_path, md, judge, out, expected=8).rows
    judge.write_text(json.dumps(rows[1:], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="다르다"):
        run_judge([PB], raw, labels_path, md, judge, out, expected=8)


def test_run_judge_reports_a_quote_missing_from_its_page(tmp_path):
    raw, labels_path, md, judge, out = judge_paths(tmp_path)
    lab = json.loads(labels_path.read_text(encoding="utf-8"))
    lab[PB]["공급규모"] = cell("496", "없는 문장", 1)
    labels_path.write_text(json.dumps(lab, ensure_ascii=False), encoding="utf-8")
    got = run_judge([PB], raw, labels_path, md, judge, out, expected=8)
    assert [r["field"] for r in got.bad] == ["공급규모"]
    assert "근거 줄을 그 쪽에서 못 찾은 칸: 1" in out.read_text(encoding="utf-8")
