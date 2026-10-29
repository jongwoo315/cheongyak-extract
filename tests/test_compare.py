import pytest

from cheongyak_extract.compare import (
    Cell,
    Counts,
    LlmNew,
    count,
    cross,
    parse_llm_new,
    parse_llm_tune,
    parse_regex_summary,
    parse_regex_tune_last,
    render,
)

LLM_NEW_MD = """\
값을 남기는 조건 A·B·C안 (같은 LLM 응답에 건 결과):

| 안 | 정답 있는 칸 | 맞음 | 비움 | 틀리게 채움 | LLM이 값을 준 칸 | 그 조건으로 비운 칸 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 160 | 150 (94%) | 5 (3%) | 5 (3%) | 160 | 5 (3%) |
| C | 160 | 154 (96%) | 0 (0%) | 6 (4%) | 160 | 0 (0%) |

필드별 맞은 칸:

| 필드 | 정답 있는 칸 | A안 맞음 | B안 맞음 | C안 맞음 |
| --- | --- | --- | --- | --- |
| 공급위치 | 20 | 18 (90%) | 18 (90%) | 18 (90%) |
| 당첨자 발표일 | 20 | 19 (95%) | 11 (55%) | 20 (100%) |

틀리게 채운 칸:

| 공고 | 필드 | 정답 | 추출값 | 근거 | 쪽 |
| --- | --- | --- | --- | --- | --- |
| 2026000443 | 공급위치 | a | b | c | 6 |
| 2026000454 | 입주예정월 | 2026.10 | 2025년 10월 | d | 6 |

토큰:

| 공고 | 입력 토큰 | 출력 토큰 |
| --- | --- | --- |
| 2026000494 | 89,831 | 623 |
"""

LLM_TUNE_MD = """\
## 수정마다 한 줄

| 수정 | 바꾼 것 | 안 | 맞음 | 비움 | 다른 값으로 채움 |
| --- | --- | --- | --- | --- | --- |
| 0 | 두 번째 시도 프롬프트 그대로(T0, 캐시) | C | 211 (90.9%) | 4 (1.7%) | 17 (7.3%) |
| 3 | 시행사는 상호 하나 | A | 209 (90.1%) | 16 (6.9%) | 7 (3.0%) |
| 3 | | C | 219 (94.4%) | 6 (2.6%) | 7 (3.0%) |

## 값을 남기는 조건 고르기

| 2 | | C | 1 (1.0%) | 1 (1.0%) | 1 (1.0%) |
"""


def test_parse_llm_new_reads_the_c_row_field_rates_and_wrong_cells():
    got = parse_llm_new(LLM_NEW_MD)
    assert got == LlmNew(
        counts=Counts(160, 154, 0, 6),
        right_by_field={"공급위치": (20, 18), "당첨자 발표일": (20, 20)},
        wrong_cells={("2026000443", "공급위치"), ("2026000454", "입주예정월")},
    )


def test_parse_llm_tune_takes_the_last_c_row_of_the_per_edit_table_only():
    assert parse_llm_tune(LLM_TUNE_MD) == Counts(232, 219, 6, 7)


def test_parse_regex_summary_reads_the_count_line():
    assert parse_regex_summary(
        "x\n정답 있는 칸 160 · 맞음 111 · 비움 34 · 틀리게 채움 15\n"
    ) == Counts(160, 111, 34, 15)


def test_parse_regex_tune_last_reads_the_last_edit_row():
    md = "| 수정 | 바꾼 것 | 맞음 | 비움 | 다른 값으로 채움 |\n| --- | --- | --- | --- | --- |\n"
    md += "| 0 | a | 155 (66.8%) | 56 (24.1%) | 21 (9.1%) |\n"
    md += "| 3 | b | 161 (69.4%) | 52 (22.4%) | 19 (8.2%) |\n"
    assert parse_regex_tune_last(md) == Counts(232, 161, 52, 19)


def test_parse_fails_loudly_when_the_report_format_changed():
    for fn in (parse_llm_new, parse_llm_tune, parse_regex_summary, parse_regex_tune_last):
        with pytest.raises(ValueError):
            fn("표가 없다")


def cell(pbno, field, state, value=None, truth="정답"):
    return Cell(pbno, field, state, value, truth)


def test_count_uses_the_three_states():
    cells = [cell("A", "f", "right"), cell("B", "f", "blank"), cell("C", "f", "wrong", "x")]
    assert count(cells) == Counts(3, 1, 1, 1)


def test_cross_splits_cells_by_regex_state_against_llm_wrong_cells():
    cells = [
        cell("A", "f", "right"),  # LLM도 맞음
        cell("B", "f", "right"),  # LLM만 틀림
        cell("C", "f", "blank"),  # 정규식만 틀림
        cell("D", "f", "wrong", "x"),  # 둘 다 틀림
    ]
    got = cross(cells, {("B", "f"), ("D", "f")})
    assert [(k, [c.pbno for c in v]) for k, v in got.items()] == [
        ("정규식 맞음, LLM 틀림", ["B"]),
        ("정규식 틀림, LLM 맞음", ["C"]),
        ("둘 다 틀림", ["D"]),
        ("둘 다 맞음", ["A"]),
    ]


def test_render_puts_regex_and_llm_numbers_side_by_side_and_names_the_source():
    cells = [cell("A", "공급위치", "right"), cell("B", "공급위치", "blank")]
    llm = LlmNew(Counts(2, 2, 0, 0), {"공급위치": (2, 2)}, set())
    md = render(
        new=cells,
        llm_new=llm,
        tune=cells,
        llm_tune=Counts(2, 1, 1, 0),
        more=cells,
        more_skipped=[("S", "스캔")],
        fields=("공급위치",),
    )
    assert "| 정규식 | 2 | 1 (50.0%) | 1 (50.0%) | 0 (0.0%) |" in md
    assert "| LLM(T0, C안) | 2 | 2 (100.0%) | 0 (0.0%) | 0 (0.0%) |" in md
    assert "| 공급위치 | 2 | 1 (50%) | 2 (100%) |" in md
    assert "reports/extract-new.md" in md and "reports/extract-tune.md" in md
    assert "LLM 없음" in md and "S: 스캔" in md
