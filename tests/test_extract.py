from cheongyak_extract.extract import FIELDS, Extraction, extract


def test_stub_returns_empty_extraction_for_every_field():
    out = extract(["아무 텍스트", "두 번째 쪽"])
    assert tuple(out) == FIELDS
    assert all(v == Extraction(None, None, None) for v in out.values())


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
