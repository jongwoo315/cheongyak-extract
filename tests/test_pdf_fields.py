import json

import pytest

from cheongyak_extract import pdf_fields as pf
from cheongyak_extract.extract import build_prompt
from pdfs import make_pdf

RESALE, RESIDENT, INCOME = pf.PDF_FIELDS


@pytest.mark.parametrize(
    "value,want",
    [
        ("3년", "36"),
        ("6개월", "6"),
        ("없음", "0"),
        ("36개월", "36"),
        ("1년 6개월", "18"),
        ("6개월, 3년", "6,36"),  # 서로 다른 값은 작은 순으로 잇는다
        ("3년, 3년, 6개월", "6,36"),
        ("  3년 ", "36"),
        ("전매제한 있음", None),
        ("", None),
        (None, None),
    ],
)
def test_resale_period_normal_form_is_months(value, want):
    assert pf.normal_form(RESALE, value) == want


@pytest.mark.parametrize(
    "value,want",
    [
        ("평택시 30% / 경기도 20% / 기타 50%", "30/20/50"),
        ("해당지역 100%", "100"),
        ("해당지역 30.0% / 기타 70%", "30/70"),
        ("해당지역 우선", None),
        (None, None),
    ],
)
def test_resident_ratio_normal_form_is_the_percentages_in_order(value, want):
    assert pf.normal_form(RESIDENT, value) == want


@pytest.mark.parametrize(
    "value,want",
    [("100% (맞벌이 120%)", "100/120"), ("130%", "130"), ("소득 기준 없음", None)],
)
def test_newlywed_income_normal_form_is_the_percentages_in_order(value, want):
    assert pf.normal_form(INCOME, value) == want


def test_normal_form_of_an_unknown_field_is_an_error():
    with pytest.raises(ValueError):
        pf.normal_form("공급위치", "서울")


@pytest.mark.parametrize(
    "field,value,quote",
    [
        (RESALE, "3년", "전매제한 3년 거주의무 없음"),
        (RESALE, "6개월", "당첨자 발표일로부터 6개월"),
        (RESALE, "없음", "전매제한 없음"),
        (RESALE, "6개월, 3년", "전용 84㎡ 이하 3년 초과 6개월"),
        (RESIDENT, "평택시 30% / 경기도 20% / 기타 50%", "평택시 30% 경기도 20% 전국 50%"),
        # 비율이 안 적힌 경우의 약속: quote에 100이 없어도 된다
        (RESIDENT, "해당지역 100%", "해당 주택건설지역 거주자 우선 공급"),
        (INCOME, "100% (맞벌이 120%)", "100% 이하 (맞벌이 120% 이하)"),
    ],
)
def test_a_cell_whose_numbers_are_in_its_quote_has_no_problem(field, value, quote):
    assert pf.number_problems(field, value, quote) == []


@pytest.mark.parametrize(
    "field,value,quote,missing",
    [
        (RESALE, "3년", "전매제한 5년", ["3"]),
        (RESALE, "없음", "전매제한 3년", ["없"]),  # 없음에는 숫자 대신 「없」이 quote에 있어야 한다
        (RESIDENT, "평택시 30% / 경기도 20% / 기타 50%", "평택시 30% 경기도 20%", ["50"]),
        (INCOME, "130%", "소득 기준 1130%", ["130"]),  # 1130의 일부는 130이 아니다
        (INCOME, "100% (맞벌이 120%)", "100% 이하", ["120"]),
    ],
)
def test_a_number_that_is_not_in_the_quote_is_a_problem(field, value, quote, missing):
    assert pf.number_problems(field, value, quote) == missing


PAGES = ["표지", "전매제한 3년\n거주의무 없음", "소득 100% 맞벌이 120%"]


def cell(value, quote, page, note=None):
    return {"value": value, "quote": quote, "page": page, "note": note}


def null(note="2쪽 전매제한 칸에서 찾아봤으나 없다"):
    return cell(None, None, None, note)


GOOD = {
    "2026000001": {
        RESALE: cell("3년", "전매제한 3년", 2),
        RESIDENT: null(),
        INCOME: cell("100% (맞벌이 120%)", "소득 100% 맞벌이 120%", 3),
    },
    "2026000002": {RESALE: null(), RESIDENT: null(), INCOME: null()},
}
TEXTS = {"2026000001": PAGES, "2026000002": PAGES}
SPLIT = pf.Split(["2026000001"], ["2026000002"])


def labels(cells=None, **top):
    data = {"tune": SPLIT.tune, "test": SPLIT.test, "cells": cells if cells is not None else GOOD}
    data.update(top)
    return json.loads(json.dumps(data))


def check(data, **kw):
    return pf.check_labels(data, SPLIT, TEXTS, expected=kw.pop("expected", 6), **kw)


def test_good_labels_give_one_cell_per_notice_and_field_with_no_problem():
    cells = check(labels())
    assert len(cells) == 6
    assert [c.pbno for c in cells][:3] == ["2026000001"] * 3
    assert [c.field for c in cells][:3] == list(pf.PDF_FIELDS)
    assert all(c.problems == () for c in cells)


def test_a_cell_with_a_quote_that_is_not_on_its_page_is_flagged_not_raised():
    data = labels()
    data["cells"]["2026000001"][RESALE] = cell("3년", "전매제한 3년", 3)  # 3쪽에는 없다
    (flagged,) = [c for c in check(data) if c.problems]
    assert (flagged.pbno, flagged.field) == ("2026000001", RESALE)
    assert flagged.problems == (pf.QUOTE_NOT_ON_PAGE,)


def test_a_cell_whose_page_is_out_of_range_is_flagged():
    data = labels()
    data["cells"]["2026000001"][RESALE] = cell("3년", "전매제한 3년", 9)
    (flagged,) = [c for c in check(data) if c.problems]
    assert flagged.problems == (pf.QUOTE_NOT_ON_PAGE,)


def test_a_number_missing_from_the_quote_is_flagged():
    data = labels()
    data["cells"]["2026000001"][INCOME] = cell("100% (맞벌이 150%)", "소득 100% 맞벌이 120%", 3)
    (flagged,) = [c for c in check(data) if c.problems]
    assert flagged.problems == (f"{pf.NUMBER_NOT_IN_QUOTE}: 150",)


def test_a_value_with_no_normal_form_is_flagged():
    data = labels()
    data["cells"]["2026000001"][RESALE] = cell("있음", "전매제한 3년", 2)
    (flagged,) = [c for c in check(data) if c.problems]
    assert pf.NO_NORMAL_FORM in flagged.problems


def test_a_null_cell_is_never_flagged():
    assert all(not c.problems for c in check(labels()) if c.value is None)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda d: d["cells"].pop("2026000002"), "2026000002"),
        (lambda d: d["cells"]["2026000002"].pop(INCOME), INCOME),
        (lambda d: d["cells"]["2026000002"].update({"기타": null()}), "기타"),
        (lambda d: d["cells"].update({"2026000009": GOOD["2026000002"]}), "2026000009"),
        (lambda d: d.update(tune=["2026000002"], test=["2026000001"]), "다시 뽑은"),
        (lambda d: d.pop("test"), "test"),
        (lambda d: d["cells"]["2026000002"][RESALE].pop("note"), "note"),
        (lambda d: d["cells"]["2026000002"][RESALE].update(note=None), "note"),
        (lambda d: d["cells"]["2026000002"][RESALE].update(note="  "), "note"),
        (lambda d: d["cells"]["2026000001"][RESALE].update(quote=None), "모두"),
        (lambda d: d["cells"]["2026000001"][RESALE].update(page=0), "page"),
        (lambda d: d["cells"]["2026000001"][RESALE].update(value=""), "null"),
    ],
)
def test_broken_label_structure_raises(mutate, message):
    data = labels()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        check(data)


def test_cell_count_must_match_expected():
    with pytest.raises(ValueError, match="6개"):
        check(labels(), expected=150)


def test_pick_is_the_seed_152_sample_of_the_sorted_list_split_into_tune_and_test():
    import random

    pbnos = [f"2026{i:06d}" for i in range(100, 160)][::-1]  # 섞인 순서로 줘도 정렬해서 뽑는다
    got = pf.pick(pbnos)
    sample = random.Random(152).sample(sorted(pbnos), 50)
    assert got == pf.Split(sample[:20], sample[20:])
    assert len(got.tune) == 20 and len(got.test) == 30
    assert pf.pick(pbnos, n=4, tune=1).tune == random.Random(152).sample(sorted(pbnos), 4)[:1]


def test_eligible_notices_have_detail_and_a_pdf_with_text(tmp_path):
    for pbno, text in (("A1", "공고문"), ("B2", ""), ("C3", "공고문")):
        d = tmp_path / pbno
        d.mkdir()
        (d / "notice.pdf").write_bytes(make_pdf(text))
        if pbno != "C3":  # detail.html이 없으면 수집된 공고가 아니다
            (d / "detail.html").write_text("<html></html>", encoding="utf-8")
    assert pf.eligible_pbnos(tmp_path) == ["A1"]  # B2는 텍스트 없는 스캔 PDF


def test_field_set_has_three_fields_a_matching_schema_and_a_head_that_says_three():
    fs = pf.PDF_FIELD_SET
    assert fs.names == pf.PDF_FIELDS
    assert tuple(fs.schema["properties"]) == pf.PDF_FIELDS
    assert "3개 필드" in fs.head and "8개" not in fs.head
    assert set(fs.help) == set(pf.PDF_FIELDS)
    assert all(f in build_prompt(["쪽"], fs) for f in pf.PDF_FIELDS)


@pytest.mark.parametrize(
    "truth,got,want",
    [
        ("3년", "36개월", pf.RIGHT),
        ("3년", None, pf.BLANK),
        ("3년", "  ", pf.BLANK),
        ("3년", "6개월", pf.OTHER),
        ("3년", "있음", pf.OTHER),  # 정규형을 못 만드는 값은 다른 값이다
        (None, None, pf.NULL_BLANK),
        (None, "3년", pf.NULL_FILLED),
    ],
)
def test_cell_state_compares_normal_forms(truth, got, want):
    assert pf.cell_state(RESALE, truth, got) == want
