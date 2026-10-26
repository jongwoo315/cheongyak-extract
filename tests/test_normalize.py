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
