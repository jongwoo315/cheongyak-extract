import pytest

from cheongyak_extract.extract import FIELDS, Extraction, grounded


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
