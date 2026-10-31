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
        (RESALE, "3년", "전매제한 5년", ["3년"]),
        (RESALE, "없음", "전매제한 3년", ["없"]),  # 없음에는 숫자 대신 「없」이 quote에 있어야 한다
        (
            RESALE,
            "없음",
            "전매제한 3년 거주의무 없음",
            ["없"],
        ),  # 「없」이 전매와 다른 항목의 것이다
        (RESALE, "3년", "전매제한 3개월", ["3년"]),  # 숫자는 같아도 단위가 다르다
        (RESALE, "6개월, 3년", "전매 6개월 또는 3개월", ["3년"]),
        (RESALE, "6개월", "전매제한 36개월", ["6개월"]),  # 36개월의 일부는 6개월이 아니다
        (RESALE, "3년", "2023년 12월 공고, 전매제한 10년", ["3년"]),
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


# --- eval-pdf: 가짜 ask와 테스트 안에서 만든 PDF ---

A_TEXT = "공고A\n전매제한 3년\n평택시 30% 기타 70%\n신혼부부 100% 맞벌이 120%\n신혼부부 130%"
B_TEXT = "공고B\n해당지역 우선 공급"
T_TEXT = "공고T\n전매제한 6개월"


@pytest.fixture
def raw_and_labels(tmp_path):
    raw = tmp_path / "raw"
    for pbno, text in (("T", T_TEXT), ("A", A_TEXT), ("B", B_TEXT)):
        (raw / pbno).mkdir(parents=True)
        (raw / pbno / "notice.pdf").write_bytes(make_pdf(text))
        (raw / pbno / "detail.html").write_text("<html></html>", encoding="utf-8")
    cells = {
        "T": {RESALE: cell("6개월", "전매제한 6개월", 1), RESIDENT: null(), INCOME: null()},
        "A": {
            RESALE: cell("3년", "전매제한 3년", 1),
            RESIDENT: cell("평택시 30% / 기타 70%", "평택시 30% 기타 70%", 1),
            INCOME: cell("100% (맞벌이 120%)", "신혼부부 100% 맞벌이 120%", 1),
        },
        "B": {RESALE: null(), RESIDENT: null(), INCOME: null()},
    }
    path = tmp_path / "labels.json"
    path.write_text(
        json.dumps({"tune": ["T"], "test": ["A", "B"], "cells": cells}, ensure_ascii=False),
        encoding="utf-8",
    )
    return raw, path, pf.Split(["T"], ["A", "B"])


def fake_ask(prompt):
    def reply(**cells):
        body = {f: {"value": None, "evidence": None, "page": None} for f in pf.PDF_FIELDS}
        body.update(cells)
        return json.dumps(body, ensure_ascii=False)

    def c(value, evidence):
        return {"value": value, "evidence": evidence, "page": 1}

    if "공고A" in prompt:  # 맞음 / 비움 / 다른 값
        return reply(**{RESALE: c("3년", "전매제한 3년"), INCOME: c("130%", "신혼부부 130%")})
    if "공고B" in prompt:  # null에 비움(전매제한·소득) / null에 값을 채움(거주지)
        return reply(**{RESIDENT: c("해당지역 100%", "해당지역 우선 공급")})
    return reply(**{RESALE: c("6개월", "전매제한 6개월")})


def run_eval(raw_and_labels, set_name, tmp_path, ask=fake_ask):
    raw, labels_path, split = raw_and_labels
    out = tmp_path / "out.md"
    result = pf.evaluate_pdf(set_name, raw, labels_path, ask, out, split=split, expected=9)
    return result, out.read_text(encoding="utf-8")


def test_eval_scores_all_five_cell_states(raw_and_labels, tmp_path):
    result, md = run_eval(raw_and_labels, "test", tmp_path)
    got = {(c.pbno, c.field): c.state for c in result.cells}
    assert got == {
        ("A", RESALE): pf.RIGHT,
        ("A", RESIDENT): pf.BLANK,
        ("A", INCOME): pf.OTHER,
        ("B", RESALE): pf.NULL_BLANK,
        ("B", RESIDENT): pf.NULL_FILLED,
        ("B", INCOME): pf.NULL_BLANK,
    }
    assert result.skipped == [] and result.label_problems == []


def test_label_problems_are_counted_only_for_the_chosen_set(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["T"][RESALE] = cell("6개월", "전매제한 9개월", 1)  # tune 쪽 문제
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert run_eval(raw_and_labels, "test", tmp_path)[0].label_problems == []
    assert [c.pbno for c in run_eval(raw_and_labels, "tune", tmp_path)[0].label_problems] == ["T"]


def test_eval_only_asks_the_notices_of_the_chosen_set(raw_and_labels, tmp_path):
    asked = []
    run_eval(raw_and_labels, "tune", tmp_path, lambda p: asked.append(p) or fake_ask(p))
    assert len(asked) == 1 and "공고T" in asked[0]
    assert "3개 필드" in asked[0]  # 세 필드 프롬프트다


def test_report_top_has_counts_with_percent_then_per_field_then_every_wrong_cell(
    raw_and_labels, tmp_path
):
    _, md = run_eval(raw_and_labels, "test", tmp_path)
    top = md.split("필드별")[0]
    assert "정답에 값이 있는 칸 3개" in top
    assert "| 맞음 | 1 (33.3%) |" in top
    assert "| 비움 | 1 (33.3%) |" in top
    assert "| 다른 값으로 채움 | 1 (33.3%) |" in top
    assert "정답이 null인 칸 3개" in top
    assert "| null에 비움 | 2 (66.7%) |" in top
    assert "| null에 값을 채움 | 1 (33.3%) |" in top
    per_field = md.split("필드별")[1]
    assert f"| {RESALE} | 1 | 1 | 0 | 0 | 1 | 1 | 0 |" in per_field
    assert f"| {INCOME} | 1 | 0 | 0 | 1 | 1 | 1 | 0 |" in per_field
    wrong = md.split("맞지 않은 칸")[1]
    assert wrong.count("\n| A |") == 2 and wrong.count("\n| B |") == 1
    assert "| A | 신혼부부 소득 기준 | 100% (맞벌이 120%) | 130% | 신혼부부 130% | 1 |" in wrong
    assert "| A | 거주지 우선 비율 | 평택시 30% / 기타 70% | — | — | — |" in wrong
    assert "| B | 거주지 우선 비율 | — | 해당지역 100% | 해당지역 우선 공급 | 1 |" in wrong
    assert "| 전매제한 기간 |" not in wrong  # 맞은 칸과 null에 비운 칸은 목록에 없다


def test_report_sums_input_tokens_and_lists_skipped_notices(raw_and_labels, tmp_path):
    from cheongyak_extract.extract import Usage
    from cheongyak_extract.llm import BadResponse

    class Ask:
        last_usage = None

        def __call__(self, prompt):
            if "공고B" in prompt:
                raise BadResponse("응답 본문이 비어 있음")
            self.last_usage = Usage(1000, 10)
            return fake_ask(prompt)

    result, md = run_eval(raw_and_labels, "test", tmp_path, Ask())
    assert "입력 토큰 합계: 1,000" in md
    assert [p for p, _ in result.skipped] == ["B"]
    assert "B" in md.split("건너뛴 공고")[1]
    assert len(result.cells) == 3  # A의 세 칸만 잰다


def test_eval_reports_label_problems_but_still_scores(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["A"][RESALE] = cell("3년", "전매제한 5년", 1)
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result, md = run_eval(raw_and_labels, "test", tmp_path)
    assert [(c.pbno, c.field) for c in result.label_problems] == [("A", RESALE)]
    assert "정답 검사에 걸린 칸 1개" in md


def test_eval_refuses_a_set_name_that_is_not_tune_or_test(raw_and_labels, tmp_path):
    with pytest.raises(ValueError, match="tune"):
        run_eval(raw_and_labels, "all", tmp_path)


def test_eval_raises_before_asking_when_labels_are_broken(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    del data["cells"]["B"]
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def never(prompt):
        raise AssertionError("정답이 깨졌으면 LLM을 부르지 않는다")

    with pytest.raises(ValueError, match="B"):
        run_eval(raw_and_labels, "test", tmp_path, never)


def test_labels_report_counts_filled_null_flagged_and_multi_period_cells(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["A"][RESALE] = cell("6개월, 3년", "전매제한 3년", 1)  # 6이 quote에 없다
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "labels.md"
    cells = pf.check_pdf_labels(raw, labels_path, out, split=split, expected=9)
    md = out.read_text(encoding="utf-8")
    assert len([c for c in cells if c.problems]) == 1
    assert f"| {RESALE} | 2 | 1 | 1 |" in md  # 값 있는 칸 2(T·A), null 칸 1(B), 걸린 칸 1
    assert f"| {RESIDENT} | 1 | 2 | 0 |" in md
    assert "`,`로 이은 칸 1개" in md
    assert "숫자가 quote에 없음: 6" in md


@pytest.mark.parametrize("bad", ["not json", '{"전매제한 기간": 3}'])
def test_a_malformed_reply_skips_the_notice_instead_of_scoring_null_blank(
    raw_and_labels, tmp_path, bad
):
    # 응답을 못 읽은 것이 정답 null 칸에서 「null에 비움」(맞음)으로 세어지면 점수가 부풀려진다
    result, md = run_eval(
        raw_and_labels, "test", tmp_path, lambda p: bad if "공고B" in p else fake_ask(p)
    )
    assert [p for p, _ in result.skipped] == ["B"]
    assert {c.pbno for c in result.cells} == {"A"}
    assert "B:" in md.split("건너뛴 공고")[1]


def test_a_notice_over_the_context_limit_is_skipped_not_fatal(raw_and_labels, tmp_path):
    from cheongyak_extract.llm import ContextExceeded

    def ask(prompt):
        if "공고B" in prompt:
            raise ContextExceeded("입력이 너무 길다")
        return fake_ask(prompt)

    result, md = run_eval(raw_and_labels, "test", tmp_path, ask)
    assert [p for p, _ in result.skipped] == ["B"]
    assert "컨텍스트 한도 초과" in md.split("건너뛴 공고")[1]
    assert len(result.cells) == 3


def test_input_tokens_add_up_across_notices(raw_and_labels, tmp_path):
    from cheongyak_extract.extract import Usage

    class Ask:
        last_usage = None

        def __call__(self, prompt):
            self.last_usage = Usage(1000, 10)
            return fake_ask(prompt)

    # test 집합은 공고 둘(A·B)이다. 마지막 값(1,000)이 아니라 합(2,000)이어야 한다
    _, md = run_eval(raw_and_labels, "test", tmp_path, Ask())
    assert "입력 토큰 합계: 2,000" in md
