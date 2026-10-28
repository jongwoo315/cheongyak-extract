import json

import pytest

from cheongyak_extract import extract as ex
from cheongyak_extract.extract import FIELDS, Extraction, build_prompt, extract, grounded


def test_fields_are_the_eight_single_cell_values():
    assert FIELDS == (
        "공급위치",
        "공급규모",
        "모집공고일",
        "당첨자 발표일",
        "계약일",
        "시행사",
        "시공사",
        "입주예정월",
    )


def test_extraction_accepts_empty_and_filled_forms():
    assert Extraction(None, None, None).value is None
    assert Extraction("358세대", "일반분양 358세대", 7).page == 7


@pytest.mark.parametrize(
    "args",
    [
        (None, "근거", None),  # 값 없음 + 근거
        (None, None, 3),  # 값 없음 + 쪽
        ("", "근거", 1),  # 빈 문자열도 값 없음
        ("  ", None, 1),
        ("값", None, 1),  # 값 있음 + 근거 없음
        ("값", "  ", 1),
        ("값", "근거", None),  # 값 있음 + 쪽 없음
        ("값", "근거", 0),  # 쪽 < 1
        ("값", "근거", -2),
    ],
)
def test_extraction_rejects_contradictions(args):
    with pytest.raises(ValueError):
        Extraction(*args)


def test_grounded_ignores_all_whitespace_on_both_sides():
    page = "계약일 2026.11.23 ~ 2026.11.29\n입주"
    assert grounded("2026.11.23~\n2026.11.29", page)  # 줄이 끊긴 근거, 공백이 있는 쪽
    assert grounded("계약일\u00a02026.11.23 ~ 2026.11.29", page)


def test_grounded_is_false_when_text_differs_or_evidence_is_empty():
    assert not grounded("2026.11.30", "2026.11.29")
    assert not grounded("", "아무 텍스트")
    assert not grounded(None, "아무 텍스트")
    assert not grounded("   ", "아무 텍스트")


PAGES = ["입주자모집공고 모집공고일 2026.10.23", "계약일 2026.11.23 ~\n2026.11.25 일반분양 358세대"]


def cell(value, evidence, page):
    return {"value": value, "evidence": evidence, "page": page}


def respond(**cells):
    """FIELDS 전부 null인 응답에 cells(필드 이름의 공백은 _)를 덮어쓴다."""
    body = {f: cell(None, None, None) for f in FIELDS}
    body.update({k.replace("_", " "): v for k, v in cells.items()})
    return json.dumps(body, ensure_ascii=False)


def run(response: str, pages=PAGES):
    return extract(pages, lambda prompt: response, rule="A")  # 규칙 1~5의 기본 동작은 A안 기준


def test_prompt_marks_every_page_and_names_every_field():
    prompt = build_prompt(PAGES)
    assert "<page 1>" in prompt and "<page 2>" in prompt
    assert PAGES[1] in prompt
    assert all(f in prompt for f in FIELDS)


def test_output_schema_requires_all_eight_keys_strictly():
    schema = ex.OUTPUT_SCHEMA
    assert tuple(schema["properties"]) == FIELDS
    assert schema["required"] == list(FIELDS)
    assert schema["additionalProperties"] is False
    for sub in schema["properties"].values():
        assert sub["additionalProperties"] is False
        assert sub["required"] == ["value", "evidence", "page"]


def test_extract_asks_once_and_returns_every_field():
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return respond(계약일=cell("2026.11.23 ~ 2026.11.25", "2026.11.23 ~ 2026.11.25", 2))

    out = extract(PAGES, ask)
    assert len(calls) == 1 and calls[0] == build_prompt(PAGES)
    assert tuple(out.fields) == FIELDS
    assert out.fields["계약일"] == Extraction(
        "2026.11.23 ~ 2026.11.25", "2026.11.23 ~ 2026.11.25", 2
    )
    assert out.fields["시행사"] == Extraction(None, None, None)
    assert out.blanked["시행사"] == ex.NO_VALUE
    assert "계약일" not in out.blanked


def test_rule_5_missing_key_is_blank_not_keyerror():
    body = json.loads(respond())
    del body["시공사"]
    out = run(json.dumps(body, ensure_ascii=False))
    assert tuple(out.fields) == FIELDS
    assert out.fields["시공사"] == Extraction(None, None, None)
    assert out.blanked["시공사"] == ex.NO_KEY


def test_rule_1_empty_value_is_blank_even_with_evidence():
    out = run(respond(시행사=cell("  ", "계약일", 1)))
    assert out.fields["시행사"] == Extraction(None, None, None)
    assert out.blanked["시행사"] == ex.NO_VALUE


@pytest.mark.parametrize("evidence,page", [(None, 1), ("  ", 1), ("계약일", None)])
def test_rule_2_missing_evidence_or_page_is_blank(evidence, page):
    out = run(respond(계약일=cell("2026.11.23", evidence, page)))
    assert out.fields["계약일"] == Extraction(None, None, None)
    assert out.blanked["계약일"] == ex.NO_EVIDENCE


@pytest.mark.parametrize("page", [0, 3, -1])
def test_rule_3_page_outside_range_is_blank(page):
    out = run(respond(계약일=cell("2026.11.23", "계약일", page)))
    assert out.fields["계약일"] == Extraction(None, None, None)
    assert out.blanked["계약일"] == ex.BAD_PAGE


def test_rule_4_evidence_not_on_that_page_is_blank():
    # 근거는 2쪽에 있는데 1쪽이라고 적었다
    out = run(respond(계약일=cell("2026.11.23", "계약일 2026.11.23", 1)))
    assert out.fields["계약일"] == Extraction(None, None, None)
    assert out.blanked["계약일"] == ex.NOT_IN_PAGE
    # 어느 쪽에도 없는 문장
    out = run(respond(계약일=cell("2026.12.01", "계약일 2026.12.01", 2)))
    assert out.blanked["계약일"] == ex.NOT_IN_PAGE


def test_rule_4_matches_across_line_breaks():
    out = run(respond(계약일=cell("2026.11.23 ~ 2026.11.25", "2026.11.23 ~ 2026.11.25", 2)))
    assert out.fields["계약일"].page == 2


def test_value_need_not_appear_inside_evidence():
    out = run(respond(공급규모=cell("358세대", "일반분양 358세대", 2)))
    assert out.fields["공급규모"] == Extraction("358세대", "일반분양 358세대", 2)


@pytest.mark.parametrize("response", ["not json", "", "[1, 2]", "null", '{"공급위치": '])
def test_non_json_or_non_object_blanks_everything_with_reason(response):
    out = run(response)
    assert tuple(out.fields) == FIELDS
    assert all(v == Extraction(None, None, None) for v in out.fields.values())
    assert set(out.blanked) == set(FIELDS)
    assert set(out.blanked.values()) == {ex.BAD_JSON}


@pytest.mark.parametrize(
    "bad",
    ["문자열", None, [1], cell(5, "계약일", 1), cell("v", 7, 1), cell("v", "계약일", "1")],
)
def test_malformed_cell_is_blank_and_does_not_crash(bad):
    out = run(respond(계약일=bad))
    assert out.fields["계약일"] == Extraction(None, None, None)
    assert "계약일" in out.blanked


def test_error_raised_by_ask_is_not_swallowed_as_bad_json():
    def ask(prompt: str) -> str:
        raise json.JSONDecodeError("캐시가 깨짐", "{", 1)

    with pytest.raises(json.JSONDecodeError):
        ex.extract(["p"], ask)


# --- 값을 남기는 조건 A·B·C안 (설계 §값을 남기는 조건) ---

RULE_PAGES = ["구분\n사업주체 (주)가나건설\n시공사 (주)다라건설", "일반분양 358세대 공급"]


def run_rule(rule, **cells):
    return extract(RULE_PAGES, lambda prompt: respond(**cells), rule=rule)


def test_rules_are_a_b_c_and_the_default_is_one_of_them():
    assert ex.RULES == ("A", "B", "C")
    assert ex.DEFAULT_RULE in ex.RULES
    # 근거는 쪽에 없고 값만 있는 응답: 기본 안이 어느 쪽 동작인지 고정한다(C안이면 남긴다)
    only_value = respond(공급규모=cell("358세대", "엉뚱한 근거", 2))
    default = extract(RULE_PAGES, lambda p: only_value)
    assert default == extract(RULE_PAGES, lambda p: only_value, ex.DEFAULT_RULE)
    assert default.fields["공급규모"].value == "358세대"


def test_unknown_rule_is_a_value_error():
    with pytest.raises(ValueError):
        extract(RULE_PAGES, lambda p: respond(), rule="D")


@pytest.mark.parametrize("rule", ex.RULES)
def test_every_rule_keeps_a_value_that_is_inside_an_evidence_that_is_on_the_page(rule):
    out = run_rule(rule, 공급규모=cell("358세대", "일반분양 358\n세대", 2))
    assert out.fields["공급규모"].value == "358세대"
    assert "공급규모" not in out.blanked


def test_rule_a_keeps_a_value_that_is_not_in_its_evidence_but_b_blanks_it():
    # 표 머리글만 근거로 준 값(첫 시도 리뷰 지적 3): 근거는 그 쪽에 있고 값은 근거 안에 없다
    cells = {"시행사": cell("(주)가나건설", "구분", 1)}
    assert run_rule("A", **cells).fields["시행사"].value == "(주)가나건설"
    assert run_rule("C", **cells).fields["시행사"].value == "(주)가나건설"
    b = run_rule("B", **cells)
    assert b.fields["시행사"] == Extraction(None, None, None)
    assert b.blanked["시행사"] == ex.VALUE_NOT_IN_EVIDENCE


def test_rule_c_keeps_a_value_on_the_page_when_its_evidence_is_not_but_a_and_b_blank_it():
    cells = {"시공사": cell("(주)다라건설", "시공사는 (주)다라건설이다", 1)}
    for rule in ("A", "B"):
        out = run_rule(rule, **cells)
        assert out.fields["시공사"].value is None
        assert out.blanked["시공사"] == ex.NOT_IN_PAGE
    c = run_rule("C", **cells)
    assert c.fields["시공사"] == Extraction("(주)다라건설", "시공사는 (주)다라건설이다", 1)
    assert "시공사" not in c.blanked


def test_rule_c_compares_the_value_with_the_page_ignoring_whitespace():
    c = run_rule("C", 공급규모=cell("358 세대", "엉뚱한 근거", 2))
    assert c.fields["공급규모"].value == "358 세대"


def test_rule_c_blanks_when_neither_evidence_nor_value_is_on_the_page():
    c = run_rule("C", 공급규모=cell("999세대", "일반분양 999세대", 2))
    assert c.fields["공급규모"].value is None
    assert c.blanked["공급규모"] == ex.NEITHER_IN_PAGE


def test_rule_c_looks_for_the_value_only_on_the_page_the_response_names():
    # 358세대는 2쪽에만 있다. 1쪽이라고 적은 응답은 근거도 값도 그 쪽에 없으므로 비운다
    c = run_rule("C", 공급규모=cell("358세대", "엉뚱한 근거", 1))
    assert c.fields["공급규모"].value is None
    assert c.blanked["공급규모"] == ex.NEITHER_IN_PAGE


@pytest.mark.parametrize("rule", ex.RULES)
def test_structural_rules_apply_to_every_rule(rule):
    out = run_rule(
        rule, 공급규모=cell("358세대", "일반분양 358세대", 9), 시행사=cell("가", "가", None)
    )
    assert out.blanked["공급규모"] == ex.BAD_PAGE
    assert out.blanked["시행사"] == ex.NO_EVIDENCE


def test_extract_rules_asks_once_and_returns_one_result_per_rule():
    calls = []
    body = respond(시행사=cell("(주)가나건설", "구분", 1))

    def ask(prompt):
        calls.append(prompt)
        return body

    out = ex.extract_rules(RULE_PAGES, ask)
    assert len(calls) == 1
    assert tuple(out) == ex.RULES
    assert out["A"].fields["시행사"].value == "(주)가나건설"
    assert out["B"].fields["시행사"].value is None
