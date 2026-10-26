import pytest

from cheongyak_extract.extract import FIELDS, KIND
from cheongyak_extract.normalize import KINDS, normalize


def test_every_field_has_a_known_kind():
    assert set(KIND) == set(FIELDS)
    assert set(KIND.values()) <= set(KINDS)


@pytest.mark.parametrize(
    "raw",
    ["2026-10-23 (헤럴드경제신문)", "2026.10.23.(금)", "2026-10-23 ( https://www.gy-bando.com )"],
)
def test_date(raw):
    assert normalize("모집공고일", raw) == "2026-10-23"


@pytest.mark.parametrize(
    "raw",
    ["2026-11-23 ~ 2026-11-25", "2026.11.23.(월)~\n2026.11.25.(수)", "2026.11.23 ~ 2026.11.25"],
)
def test_period(raw):
    assert normalize("계약일", raw) == "2026-11-23~2026-11-25"


@pytest.mark.parametrize("raw", ["2029.08", "2029년08월", "2029년 8월", "2029-08"])
def test_month(raw):
    assert normalize("입주예정월", raw) == "2029-08"


@pytest.mark.parametrize("raw", ["(주)반도건설", "㈜반도건설", "주식회사 반도건설", "반도 건설"])
def test_company_drops_legal_form_and_spaces(raw):
    assert normalize("시행사", raw) == "반도건설"


def test_company_list_is_sorted_and_split_on_comma_or_line_break():
    truth = "주식회사 시티건설, 주식회사 시티, 주식회사 시티종합건설"
    pdf = "주식회사 시티건설\n주식회사 시티\n주식회사 시티종합건설"
    assert normalize("시공사", truth) == normalize("시공사", pdf)
    assert normalize("시공사", "㈜가, ㈜나") == normalize("시공사", "㈜나, ㈜가")


@pytest.mark.parametrize("raw", ["358세대", "358 세대", "총 358세대"])
def test_household_count(raw):
    assert normalize("공급규모", raw) == "358"


def test_address_only_tidies_spaces_around_parens():
    a = "인천광역시 계양구 동양동 458-3번지 일원 (인천계양 테크노밸리 AC3블록)"
    b = "인천광역시  계양구 동양동 458-3번지 일원(인천계양 테크노밸리 AC3블록)"
    assert normalize("공급위치", a) == normalize("공급위치", b)


def test_unreadable_value_falls_back_to_stripped_original():
    assert normalize("모집공고일", "  미정  ") == "미정"
    assert normalize("공급규모", " 해당 없음 ") == "해당 없음"


def test_empty_value_stays_empty_and_unknown_field_is_only_stripped():
    assert normalize("모집공고일", None) is None
    assert normalize("모집공고일", "  ") is None
    assert normalize("없는 필드", " 2026.11.11 ") == "2026.11.11"


# 설계 §정규화 결과가 같아지면 안 되는 것
@pytest.mark.parametrize(
    ("field", "a", "b"),
    [
        ("당첨자 발표일", "2026-11-10", "2026-11-11"),
        ("계약일", "2026-11-23 ~ 2026-11-25", "2026-11-23 ~ 2026-11-26"),
        ("시행사", "반도건설", "반도종합건설"),
        ("공급규모", "358세대", "385세대"),
    ],
)
def test_different_values_stay_different(field, a, b):
    assert normalize(field, a) != normalize(field, b)


@pytest.mark.parametrize("field", FIELDS)
def test_empty_never_equals_non_empty(field):
    for filled in ("2026-11-10", "358세대", "반도건설"):
        assert normalize(field, "") != normalize(field, filled)


@pytest.mark.parametrize(
    ("field", "a", "b"),
    [
        ("입주예정월", "2029.08", "12029.08"),
        ("입주예정월", "2029.08", "2029.0815"),
        ("입주예정월", "2029.08", "2029.08.15"),  # 일까지 적힌 날짜는 월이 아니다
        ("입주예정월", "2029.1", "2029.10"),
        ("모집공고일", "2026-10-23", "2026-10-235"),
        ("공급규모", "358세대", "1,358세대"),
    ],
)
def test_digits_around_a_match_keep_values_apart(field, a, b):
    assert normalize(field, a) != normalize(field, b)


# 값이 둘 이상 읽히면 하나를 골라 같게 만들지 않는다 — 원본 비교로 떨어진다
@pytest.mark.parametrize(
    ("field", "a", "b"),
    [
        ("모집공고일", "2026-10-23", "2026-10-23 ~ 2026-10-30"),
        ("모집공고일", "2026-11-10", "2026-11-10 2026-11-11"),
        ("입주예정월", "2029.08", "2029년 8월 ~ 2029년 12월"),
        ("입주예정월", "2029.08", "2029년 8월 15일"),
        ("입주예정월", "2029.08", "2029년 08월 ~ 09월"),
        ("입주예정월", "2029.08", "2029.08~09"),
        ("공급규모", "358세대", "358세대, 400세대"),
        ("공급규모", "100세대", "특별공급 100세대 총 358세대"),
        ("공급규모", "358세대", "3,58세대"),
        ("당첨자 발표일", "2026-11-10", "2026.11.10~11.11"),
        ("당첨자 발표일", "2026-11-10", "2026.11.10.(화) 10:00 ~ 11.11.(수)"),
    ],
)
def test_ambiguous_value_is_not_collapsed_to_one_candidate(field, a, b):
    assert normalize(field, a) != normalize(field, b)


def test_same_number_repeated_is_still_one_count():
    assert normalize("공급규모", "358세대 (일반 358세대)") == "358"


def test_trailing_text_after_one_month_is_ignored():
    raw = "2029년 08월 예정(정확한 입주일자는 추후 통보함)"
    assert normalize("입주예정월", raw) == "2029-08"
