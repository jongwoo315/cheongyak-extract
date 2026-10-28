import pytest

from cheongyak_extract import extract as ex
from cheongyak_extract.extract import FIELDS, Extraction, Usage
from cheongyak_extract.report import (
    Doc,
    metrics,
    render_field_rates,
    render_markdown,
    render_rule_table,
    render_shape_errors,
    render_summary,
    render_usage,
    render_wrong,
    with_rule,
)

EMPTY = Extraction(None, None, None)


def doc(truth, ex, pages):
    return Doc(pbno="x", truth={"f": truth}, extracted={"f": ex}, pages=pages)


def test_metrics_follow_design_definitions():
    docs = [
        doc("A", Extraction("A", "foo", 1), ["foo bar"]),  # 맞음, 근거 위치 맞음
        doc("B", Extraction("X", "nope", 1), ["foo bar"]),  # 틀림, 지어낸 값, 근거 위치 틀림
        doc(None, Extraction("Y", "foo", 2), ["foo", "zzz"]),  # 비어야 하는데 채움, 근거 위치 틀림
        doc("C", EMPTY, ["foo"]),  # 빈 칸
    ]
    (m,) = metrics(docs, ("f",))
    assert m.field == "f"
    assert m.with_truth == 3
    assert m.accuracy == 1 / 3
    assert m.blank == 1 / 3
    assert m.fabricated == 1
    assert m.filled_empty == 1
    assert m.page_ok == 1 / 3


def test_unknown_field_is_only_stripped():
    (m,) = metrics([doc("2026-11-11", Extraction(" 2026-11-11 ", "e", 1), ["e"])], ("f",))
    assert m.accuracy == 1.0
    (m,) = metrics([doc("2026-11-11", Extraction("2026.11.11", "e", 1), ["e"])], ("f",))
    assert m.accuracy == 0.0


def test_evidence_match_ignores_line_breaks():
    (m,) = metrics([doc("A", Extraction("A", "foo bar", 1), ["foo\nbar"])], ("f",))
    assert m.fabricated == 0 and m.page_ok == 1.0


def test_denominator_zero_renders_dash():
    (m,) = metrics([doc(None, EMPTY, ["p"])], ("f",))
    assert m.with_truth == 0
    assert m.accuracy is None and m.blank is None and m.page_ok is None
    md = render_markdown([m])
    head = md.splitlines()[0]
    assert head.startswith("| 필드 | 정답 있음 | 정확도 | 빈 칸 |")
    assert head.endswith("| 근거 위치 맞음 | 틀리게 채움 | 근거 확인 못해 비움 |")
    assert "| f | 0 | — | — | 0 | 0 | — | 0 | 0 |" in md


def test_render_markdown_formats_percentages():
    (m,) = metrics([doc("A", EMPTY, ["p"])], ("f",))
    assert "| f | 1 | 0% | 100% | 0 | 0 | — | 0 | 0 |" in render_markdown([m])


def test_page_beyond_last_page_is_not_ok_and_does_not_crash():
    (m,) = metrics([doc("A", Extraction("A", "foo", 3), ["foo", "bar"])], ("f",))
    assert m.page_ok == 0.0


def test_accuracy_compares_normalized_forms_of_both_sides():
    truth = {"모집공고일": "2026-10-23 (헤럴드경제신문)", "시행사": "(주)반도건설"}
    ex = {
        "모집공고일": Extraction("2026.10.23.(금)", "e", 1),
        "시행사": Extraction("반도종합건설", "e", 1),
    }
    docs = [Doc("x", truth, ex, ["e"])]
    date, company = metrics(docs, ("모집공고일", "시행사"))
    assert date.accuracy == 1.0
    assert company.accuracy == 0.0


def test_stub_extraction_stays_at_zero_accuracy_and_full_blank():
    truth = {f: "2026-11-10" for f in FIELDS}
    stub = {f: EMPTY for f in FIELDS}
    rows = metrics([Doc("x", truth, stub, ["p"])], FIELDS)
    assert all(m.accuracy == 0.0 and m.blank == 1.0 for m in rows)


def test_wrong_fill_counts_only_filled_values_that_differ_from_truth():
    docs = [
        doc("A", Extraction("A", "foo", 1), ["foo"]),  # 맞음
        doc("B", Extraction("X", "foo", 1), ["foo"]),  # 틀리게 채움
        doc("C", EMPTY, ["foo"]),  # 비움
        doc(None, Extraction("Y", "foo", 1), ["foo"]),  # 정답 없음: 틀리게 채움이 아니다
    ]
    (m,) = metrics(docs, ("f",))
    assert m.wrong == 1 and m.filled_empty == 1


def test_ungrounded_counts_blanked_by_rule_4_among_cells_with_truth():
    blanked = {"f": ex.NOT_IN_PAGE}
    docs = [
        Doc("a", {"f": "A"}, {"f": EMPTY}, ["p"], blanked),
        Doc("b", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NO_VALUE}),
        Doc("c", {"f": None}, {"f": EMPTY}, ["p"], blanked),  # 정답 없는 칸은 세지 않는다
    ]
    (m,) = metrics(docs, ("f",))
    assert m.ungrounded == 1


def test_missing_keys_in_truth_or_extraction_do_not_raise():
    d = Doc("x", {}, {}, ["p"])
    (m,) = metrics([d], ("f",))
    assert m.with_truth == 0 and m.wrong == 0
    d = Doc("x", {"f": "A"}, {}, ["p"])
    (m,) = metrics([d], ("f",))
    assert m.with_truth == 1 and m.blank == 1.0


def test_wrong_table_lists_one_row_per_wrong_cell_with_evidence_and_page():
    docs = [
        Doc("p1", {"f": "A"}, {"f": Extraction("X|1", "근거\n문장", 2)}, ["a", "근거 문장"]),
        Doc("p2", {"f": "A"}, {"f": Extraction("A", "a", 1)}, ["a"]),
    ]
    md = render_wrong(docs, ("f",))
    assert md.splitlines()[0] == "| 공고 | 필드 | 정답 | 추출값 | 근거 | 쪽 |"
    assert "| p1 | f | A | X\\|1 | 근거 ⏎ 문장 | 2 |" in md
    assert "p2" not in md


def test_wrong_table_says_none_when_no_wrong_cells():
    docs = [doc("A", Extraction("A", "foo", 1), ["foo"])]
    assert "없음" in render_wrong(docs, ("f",))


def test_usage_table_has_per_doc_rows_and_total():
    docs = [
        Doc("p1", {}, {}, ["p"], usage=Usage(1000, 50)),
        Doc("p2", {}, {}, ["p"], usage=Usage(2500, 70)),
        Doc("p3", {}, {}, ["p"]),  # 토큰 수를 모르는 공고(가짜 ask)
    ]
    md = render_usage(docs)
    assert md.splitlines()[0] == "| 공고 | 입력 토큰 | 출력 토큰 |"
    assert "| p1 | 1,000 | 50 |" in md
    assert "| p3 | — | — |" in md
    assert "| 합계 | 3,500 | 120 |" in md


def test_summary_counts_cells_and_ungrounded_rate_over_values_the_llm_gave():
    ok = Extraction("A", "foo", 1)
    docs = [
        Doc("a", {"f": "A"}, {"f": ok}, ["foo"]),  # 맞음, LLM이 값을 줌
        Doc("b", {"f": "A"}, {"f": Extraction("X", "foo", 1)}, ["foo"]),  # 틀리게 채움, 값을 줌
        Doc("c", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NOT_IN_PAGE}),  # 값을 줬지만 거름
        Doc("d", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NO_VALUE}),  # LLM이 비움
    ]
    md = render_summary(docs, ("f",))
    assert "정답 있는 칸 4 · 맞음 1 · 비움 2 · 틀리게 채움 1" in md
    assert "LLM이 값을 준 3칸 중 근거를 확인 못해 비운 칸 1 (33%)" in md


def test_shape_errors_list_only_cells_blanked_for_a_broken_response():
    docs = [
        Doc("a", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.BAD_JSON}),
        Doc("b", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NO_KEY}),
        Doc("c", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.BAD_CELL}),
        Doc("d", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NO_VALUE}),  # LLM이 비움
        Doc("e", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NOT_IN_PAGE}),  # 근거 규칙
    ]
    md = render_shape_errors(docs)
    assert f"| a | f | {ex.BAD_JSON} |" in md
    assert f"| b | f | {ex.NO_KEY} |" in md
    assert f"| c | f | {ex.BAD_CELL} |" in md
    assert "| d |" not in md and "| e |" not in md


def test_shape_errors_section_is_absent_when_nothing_is_broken():
    assert (
        render_shape_errors([Doc("d", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NO_VALUE})]) == ""
    )


def test_summary_denominator_counts_every_rule_that_dropped_a_given_value():
    # 규칙 2·3·4는 LLM이 값을 줬다가 코드가 비운 칸이고, 응답 모양 오류·규칙 1·5는 아니다
    def blanked(pbno, why):
        return Doc(pbno, {"f": "A"}, {"f": EMPTY}, ["p"], {"f": why})

    docs = [
        blanked("a", ex.NO_EVIDENCE),
        blanked("b", ex.BAD_PAGE),
        blanked("c", ex.NOT_IN_PAGE),
        blanked("d", ex.BAD_JSON),
        blanked("e", ex.BAD_CELL),
        blanked("f", ex.NO_KEY),
        blanked("g", ex.NO_VALUE),
    ]
    assert "LLM이 값을 준 3칸 중 근거를 확인 못해 비운 칸 1 (33%)" in render_summary(docs, ("f",))


# --- 값을 남기는 조건 A·B·C안 비교 ---


OK = (Extraction("A", "foo", 1), None)
BAD = (Extraction("X", "foo", 1), None)
NIP = (EMPTY, ex.NOT_IN_PAGE)
VNE = (EMPTY, ex.VALUE_NOT_IN_EVIDENCE)
NOV = (EMPTY, ex.NO_VALUE)


def rule_doc(pbno, truth, by_rule):
    """by_rule: {안: (Extraction, 비운 이유 또는 None)}. 고른 안은 A."""
    rules = {
        r: ex.Extracted({"f": e}, {"f": why} if why else {}) for r, (e, why) in by_rule.items()
    }
    return Doc(pbno, {"f": truth}, rules["A"].fields, ["p"], rules["A"].blanked, rules=rules)


def test_with_rule_swaps_in_that_rules_cells_and_reasons():
    ok = Extraction("A", "foo", 1)
    d = rule_doc("a", "A", {"A": NIP, "B": NIP, "C": OK})
    c = with_rule(d, "C")
    assert c.extracted == {"f": ok} and c.blanked == {}
    assert with_rule(d, "A") == d


def test_with_rule_rejects_a_rule_the_doc_does_not_have():
    with pytest.raises(KeyError):
        with_rule(Doc("a", {}, {}, ["p"]), "B")


def test_rule_table_counts_right_blank_wrong_per_rule_over_cells_with_truth():
    docs = [
        # A: 맞음 / B: 비움(근거 안에 값 없음) / C: 맞음
        rule_doc("a", "A", {"A": OK, "B": VNE, "C": OK}),
        # 세 안 모두 틀리게 채움
        rule_doc("b", "A", {"A": BAD, "B": BAD, "C": BAD}),
        # A·B: 근거를 못 찾아 비움 / C: 값이 쪽에 있어 남김(맞음)
        rule_doc("c", "A", {"A": NIP, "B": NIP, "C": OK}),
        # 정답이 없는 칸은 세지 않는다
        rule_doc("d", None, {"A": BAD, "B": BAD, "C": BAD}),
    ]
    md = render_rule_table(docs, ("f",))
    assert (
        "| 안 | 정답 있는 칸 | 맞음 | 비움 | 틀리게 채움 | LLM이 값을 준 칸 | 그 조건으로 비운 칸 |"
        in md
    )
    assert "| A | 3 | 1 (33%) | 1 (33%) | 1 (33%) | 3 | 1 (33%) |" in md
    assert "| B | 3 | 0 (0%) | 2 (67%) | 1 (33%) | 3 | 2 (67%) |" in md
    assert "| C | 3 | 2 (67%) | 0 (0%) | 1 (33%) | 3 | 0 (0%) |" in md


def test_rule_table_is_empty_when_docs_have_no_rule_results():
    assert render_rule_table([Doc("a", {"f": "A"}, {"f": EMPTY}, ["p"])], ("f",)) == ""


def test_field_rate_table_lists_right_over_truth_per_field_and_rule():
    docs = [
        rule_doc("a", "A", {"A": OK, "B": VNE, "C": OK}),
        rule_doc(
            "b",
            "A",
            {"A": NOV, "B": NOV, "C": NOV},
        ),
    ]
    md = render_field_rates(docs, ("f",))
    assert "| 필드 | 정답 있는 칸 | A안 맞음 | B안 맞음 | C안 맞음 |" in md
    assert "| f | 2 | 1 (50%) | 0 (0%) | 1 (50%) |" in md


def test_summary_counts_the_new_rule_blanks_as_given_then_blanked():
    docs = [
        Doc("a", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.VALUE_NOT_IN_EVIDENCE}),
        Doc("b", {"f": "A"}, {"f": EMPTY}, ["p"], {"f": ex.NEITHER_IN_PAGE}),
        Doc("c", {"f": "A"}, {"f": Extraction("A", "foo", 1)}, ["foo"]),
    ]
    assert "LLM이 값을 준 3칸 중 근거를 확인 못해 비운 칸 2 (67%)" in render_summary(docs, ("f",))
    (m,) = metrics(docs, ("f",))
    assert m.ungrounded == 2
