import pytest

from cheongyak_extract.truth_check import check_cells

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
