import pytest

from cheongyak_extract.extract import FIELDS, KIND
from cheongyak_extract.normalize import normalize


def test_every_field_has_a_known_kind():
    assert set(KIND) == set(FIELDS)


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
