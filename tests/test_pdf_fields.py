import json

import pymupdf
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


def test_two_field_set_has_no_resident_field_and_a_head_that_says_two():
    fs = pf.TWO_FIELD_SET
    assert fs.names == (RESALE, INCOME)
    assert tuple(fs.schema["properties"]) == (RESALE, INCOME)
    assert "2개 필드" in fs.head and "8개" not in fs.head
    prompt = build_prompt(["쪽"], fs)
    assert RESIDENT not in prompt and "①지역" not in prompt and "해당지역" not in prompt


@pytest.mark.parametrize("fs", [pf.RESIDENT_BLOCK_SET, pf.RESIDENT_FULL_SET])
def test_resident_sets_ask_only_the_resident_field_with_the_value_form_rules(fs):
    assert fs.names == (RESIDENT,)
    assert fs.schema == pf.RESIDENT_BLOCK_SET.schema
    assert tuple(fs.schema["properties"]) == (RESIDENT,)
    assert "1개 필드" in fs.head
    help_ = fs.help[RESIDENT]
    assert "해당지역 100%" in help_ and "0%인 지역은 쓰지 않는다" in help_ and "더하면 100" in help_


def test_the_block_set_says_the_text_is_the_block_and_the_full_set_gives_rules_2_and_3():
    assert "일반공급 ①지역 묶음" in pf.RESIDENT_BLOCK_SET.head
    assert "전체 텍스트" in pf.RESIDENT_FULL_SET.head
    full = pf.RESIDENT_FULL_SET.help[RESIDENT]
    assert full.index("지역우선 공급기준 표") < full.index("해당지역 거주자 우선 문장")
    assert "다자녀" in full and "읽지 않는다" in full
    assert "한 줄, 길어도 연속된 두 줄" in full and "실제로 들어 있는 쪽의 번호" in full
    assert "한 줄, 길어도" not in pf.RESIDENT_BLOCK_SET.help[RESIDENT]  # 묶음 쪽은 고치지 않았다


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
# 묶음이 있는 공고. 묶음 밖(다자녀 줄)에 50%가 적혀 있다. 묶음 프롬프트에는 공고 이름 줄이
# 안 들어가므로 K단지·P단지 글자로 공고를 알아본다
K_TEXT = (
    "공고K\n다자녀 특별공급 ①지역 해당 시·도 거주자 50%\n"
    "- 2순위  : ①지역 → ②추첨\n"
    "■ ①지역 : K단지 해당지역 거주자 → 기타지역 거주자\n"
    "■ ②가점"
)
P_TEXT = K_TEXT.replace("공고K", "공고P").replace("K단지", "P단지")
Q_TEXT = "공고Q\n해당지역 거주자 우선 공급"


def write_raw(root, notices):
    for pbno, text in notices:
        (root / pbno).mkdir(parents=True)
        (root / pbno / "notice.pdf").write_bytes(make_pdf(text))
        (root / pbno / "detail.html").write_text("<html></html>", encoding="utf-8")


@pytest.fixture
def raw_and_labels(tmp_path):
    raw = tmp_path / "raw"
    write_raw(raw, (("T", T_TEXT), ("A", A_TEXT), ("B", B_TEXT), ("K", K_TEXT)))
    cells = {
        "T": {RESALE: cell("6개월", "전매제한 6개월", 1), RESIDENT: null(), INCOME: null()},
        "A": {
            RESALE: cell("3년", "전매제한 3년", 1),
            RESIDENT: cell("평택시 30% / 기타 70%", "평택시 30% 기타 70%", 1, "공통 표"),
            INCOME: cell("100% (맞벌이 120%)", "신혼부부 100% 맞벌이 120%", 1),
        },
        "B": {RESALE: null(), RESIDENT: null(), INCOME: null()},
        "K": {
            RESALE: null(),
            RESIDENT: cell("해당지역 100%", "해당지역 거주자 → 기타지역 거주자", 1),
            INCOME: null(),
        },
    }
    path = tmp_path / "labels.json"
    path.write_text(
        json.dumps({"tune": ["T"], "test": ["A", "B", "K"], "cells": cells}, ensure_ascii=False),
        encoding="utf-8",
    )
    return raw, path, pf.Split(["T"], ["A", "B", "K"])


@pytest.fixture
def resident_set(tmp_path):
    """새 30건 파일 꼴: tune 키가 없고 거주지 칸만 있다. P는 묶음이 있고 Q는 없다."""
    raw = tmp_path / "raw30"
    write_raw(raw, (("P", P_TEXT), ("Q", Q_TEXT)))
    cells = {
        "P": {RESIDENT: cell("해당지역 100%", "해당지역 거주자 → 기타지역 거주자", 1)},
        "Q": {RESIDENT: cell("해당지역 100%", "해당지역 거주자 우선", 1, "해당지역 우선 문장")},
    }
    path = tmp_path / "resident.json"
    path.write_text(
        json.dumps({"test": ["P", "Q"], "cells": cells}, ensure_ascii=False), encoding="utf-8"
    )
    return raw, path, pf.Split([], ["P", "Q"])


def fake_ask(prompt):
    asks_resident = "다음 1개 필드" in prompt
    names = (RESIDENT,) if asks_resident else (RESALE, INCOME)

    def reply(**cells):
        body = {f: {"value": None, "evidence": None, "page": None} for f in names}
        body.update(cells)
        return json.dumps(body, ensure_ascii=False)

    def c(value, evidence):
        return {"value": value, "evidence": evidence, "page": 1}

    if "공고A" in prompt:  # 전매제한 맞음 / 소득 다른 값 / 거주지 비움(전체 텍스트)
        return reply(**{RESALE: c("3년", "전매제한 3년"), INCOME: c("130%", "신혼부부 130%")})
    if "공고B" in prompt:  # 정답 null: 거주지에 값을 채움(전체 텍스트)
        return reply(**{RESIDENT: c("해당지역 100%", "해당지역 우선 공급")})
    if "K단지" in prompt:  # 묶음. 합이 100이 아닌 값을 낸다
        return reply(**{RESIDENT: c("해당지역 50% / 기타지역 60%", "해당지역 거주자")})
    if "P단지" in prompt:  # 묶음. 맞음
        return reply(**{RESIDENT: c("해당지역 100%", "해당지역 거주자 → 기타지역 거주자")})
    if "공고T" in prompt:
        return reply(**{RESALE: c("6개월", "전매제한 6개월")})
    return reply()  # 공고Q: 거주지 비움


def run_eval(raw_and_labels, set_name, tmp_path, ask=fake_ask, **kw):
    raw, labels_path, split = raw_and_labels
    out = tmp_path / "out.md"
    expected = 12 if set_name == "tune" else 2
    result = pf.evaluate_pdf(
        set_name, raw, labels_path, ask, out, split=split, expected=expected, **kw
    )
    return result, out.read_text(encoding="utf-8")


def test_eval_scores_all_five_cell_states(raw_and_labels, tmp_path):
    result, md = run_eval(raw_and_labels, "tune", tmp_path)
    got = {(c.pbno, c.field): c.state for c in result.cells}
    assert got == {
        ("T", RESALE): pf.RIGHT,
        ("T", RESIDENT): pf.NULL_BLANK,
        ("T", INCOME): pf.NULL_BLANK,
        ("A", RESALE): pf.RIGHT,
        ("A", RESIDENT): pf.BLANK,
        ("A", INCOME): pf.OTHER,
        ("B", RESALE): pf.NULL_BLANK,
        ("B", RESIDENT): pf.NULL_FILLED,
        ("B", INCOME): pf.NULL_BLANK,
        ("K", RESALE): pf.NULL_BLANK,
        ("K", RESIDENT): pf.OTHER,
        ("K", INCOME): pf.NULL_BLANK,
    }
    assert result.skipped == [] and result.label_problems == []


def test_tune_asks_every_notice_of_the_file_for_resident_and_the_other_two_separately(
    raw_and_labels, tmp_path
):
    asked = []
    run_eval(raw_and_labels, "tune", tmp_path, lambda p: asked.append(p) or fake_ask(p))
    resident = [p for p in asked if "다음 1개 필드" in p]
    others = [p for p in asked if "다음 2개 필드" in p]
    assert len(resident) == 4 and len(others) == 4  # tune 1건 + test 3건 = 파일의 4건 전부
    assert not any(RESIDENT in p for p in others)  # 두 필드 호출에 거주지 설명이 없다
    assert not any(RESALE in p or INCOME in p for p in resident)


def test_a_notice_with_a_block_gets_only_the_block_and_one_without_gets_the_whole_text(
    raw_and_labels, tmp_path
):
    asked = []
    run_eval(raw_and_labels, "tune", tmp_path, lambda p: asked.append(p) or fake_ask(p))
    resident = {q for q in asked if "다음 1개 필드" in q}
    block = next(q for q in resident if "K단지" in q)
    assert "일반공급 ①지역 묶음" in block
    assert "■ ①지역 : K단지 해당지역 거주자 → 기타지역 거주자" in block
    shown = block.split("공고문:")[1]  # 필드 설명의 예시(50%)가 아니라 공고문 부분만 본다
    assert "다자녀" not in shown and "50%" not in shown  # 묶음 밖은 LLM에 주지 않는다
    assert "<page 1>" in shown and shown.count("<page ") == 1
    whole = next(q for q in resident if "공고A" in q)
    assert "공고A" in whole and "전체 텍스트" in whole
    assert "지역우선 공급기준 표" in whole and "해당지역 거주자 우선 문장" in whole  # 규칙 2·3


def test_the_block_page_number_is_the_real_page_and_evidence_outside_it_is_blank(tmp_path):
    raw = tmp_path / "raw"
    doc_pages = ["표지 다자녀 ①지역 50%", K_TEXT.replace("공고K", "공고Z")]
    doc = pymupdf.open()
    for t in doc_pages:
        doc.new_page().insert_text((72, 72), t, fontname="korea")
    (raw / "Z").mkdir(parents=True)
    (raw / "Z" / "notice.pdf").write_bytes(doc.tobytes())
    (raw / "Z" / "detail.html").write_text("<html></html>", encoding="utf-8")
    labels = tmp_path / "l.json"
    labels.write_text(
        json.dumps(
            {
                "test": ["Z"],
                "cells": {"Z": {RESIDENT: cell("해당지역 100%", "해당지역 거주자", 2)}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    asked = []

    def ask(prompt):
        asked.append(prompt)
        # 1쪽의 글자를 근거로 댄다. 묶음(2쪽)에 없는 근거다
        cellv = {"value": "해당지역 50%", "evidence": "다자녀 ①지역 50%", "page": 1}
        return json.dumps({RESIDENT: cellv}, ensure_ascii=False)

    out = tmp_path / "out.md"
    result = pf.evaluate_pdf("test", raw, labels, ask, out, split=pf.Split([], ["Z"]), expected=1)
    assert "<page 2>" in asked[0] and "<page 1>" not in asked[0]
    (scored,) = result.cells
    assert scored.state == pf.BLANK and scored.source == pf.FROM_BLOCK
    assert scored.why is not None


def test_test_set_asks_only_the_resident_field_and_scores_only_resident_cells(
    resident_set, tmp_path
):
    asked = []
    result, md = run_eval(resident_set, "test", tmp_path, lambda p: asked.append(p) or fake_ask(p))
    assert len(asked) == 2 and all("다음 1개 필드" in p for p in asked)
    got = {(c.pbno, c.field, c.source): c.state for c in result.cells}
    assert got == {("P", RESIDENT, "묶음"): pf.RIGHT, ("Q", RESIDENT, "전체"): pf.BLANK}
    assert f"| {RESIDENT} | 2 | 1 | 1 | 0 | 0 | 0 | 0 |" in md.split("필드별")[1]
    assert RESALE not in md and INCOME not in md


def test_label_problems_are_counted_only_for_the_notices_of_the_set(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["T"][RESALE] = cell("6개월", "전매제한 9개월", 1)
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result, md = run_eval(raw_and_labels, "tune", tmp_path)
    assert [c.pbno for c in result.label_problems] == ["T"]
    assert "정답 검사에 걸린 칸 1개" in md


def test_report_counts_resident_cells_by_source_and_flags_a_sum_other_than_100(
    raw_and_labels, tmp_path
):
    result, md = run_eval(raw_and_labels, "tune", tmp_path)
    top = md.split("필드별")[0]
    assert "거주지 칸 4개를 읽은 곳(출처)별로 센다" in top
    # 묶음: K 하나(다른 값). 전체: T(null에 비움) A(비움) B(null에 값을 채움)
    assert "| 묶음 | 1 | 0 (0.0%) | 0 (0.0%) | 1 (100.0%) | 0 (—) | 0 (—) |" in top
    assert "| 전체 | 3 | 0 (0.0%) | 1 (100.0%) | 0 (0.0%) | 1 (50.0%) | 1 (50.0%) |" in top
    assert "100이 아닌 거주지 칸 1개" in top
    assert [c.sum_off for c in result.cells if c.field == RESIDENT and c.source == "묶음"] == [True]


def test_wrong_cell_table_has_truth_page_llm_page_source_and_sum_columns(raw_and_labels, tmp_path):
    _, md = run_eval(raw_and_labels, "tune", tmp_path)
    wrong = md.split("맞지 않은 칸")[1]
    head = "| 공고 | 필드 | 정답 값 | LLM 값 | LLM 근거 | 정답 쪽 | LLM 쪽 | 출처 | 합 100 아님 |"
    assert head in wrong
    assert (
        f"| K | {RESIDENT} | 해당지역 100% | 해당지역 50% / 기타지역 60% | 해당지역 거주자 "
        "| 1 | 1 | 묶음 | 예 | 다른 값으로 채움 |"
    ) in wrong
    assert f"| A | {RESIDENT} | 평택시 30% / 기타 70% | — | — | 1 | — | 전체 | — | 비움 |" in wrong
    assert (
        f"| B | {RESIDENT} | — | 해당지역 100% | 해당지역 우선 공급 | — | 1 | 전체 | — |" in wrong
    )
    assert "| 전매제한 기간 |" not in wrong  # 맞은 칸과 null에 비운 칸은 목록에 없다


def test_report_top_has_counts_with_percent_then_per_field(raw_and_labels, tmp_path):
    _, md = run_eval(raw_and_labels, "tune", tmp_path)
    top = md.split("필드별")[0]
    assert "정답에 값이 있는 칸 5개" in top  # T 전매, A 전매·거주지·소득, K 거주지
    assert "| 맞음 | 2 (40.0%) |" in top
    assert "| 비움 | 1 (20.0%) |" in top
    assert "| 다른 값으로 채움 | 2 (40.0%) |" in top
    assert "정답이 null인 칸 7개" in top
    assert "| null에 값을 채움 | 1 (14.3%) |" in top
    per_field = md.split("필드별")[1]
    assert f"| {RESALE} | 2 | 2 | 0 | 0 | 2 | 2 | 0 |" in per_field


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

    result, md = run_eval(raw_and_labels, "tune", tmp_path, Ask())
    assert "입력 토큰 합계: 6,000" in md  # 공고 T·A·K가 두 번씩 불렀다
    assert [p for p, _ in result.skipped] == ["B"]
    assert "B" in md.split("건너뛴 공고")[1]
    assert len(result.cells) == 9  # B를 뺀 세 공고의 세 칸씩


def test_the_two_asks_may_be_different_objects_and_tokens_are_read_from_each(
    raw_and_labels, tmp_path
):
    from cheongyak_extract.extract import Usage

    class Ask:
        def __init__(self, tokens):
            self.tokens, self.last_usage = tokens, None

        def __call__(self, prompt):
            self.last_usage = Usage(self.tokens, 1)
            return fake_ask(prompt)

    _, md = run_eval(raw_and_labels, "tune", tmp_path, Ask(100), resident_ask=Ask(7))
    assert "입력 토큰 합계: 428" in md  # (100 + 7) × 4공고


def test_eval_reports_label_problems_but_still_scores(raw_and_labels, tmp_path):
    raw, labels_path, split = raw_and_labels
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["A"][RESALE] = cell("3년", "전매제한 5년", 1)
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result, md = run_eval(raw_and_labels, "tune", tmp_path)
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
        run_eval(raw_and_labels, "tune", tmp_path, never)


@pytest.mark.parametrize("bad", ["not json", '{"거주지 우선 비율": 3}'])
def test_a_malformed_reply_skips_the_notice_instead_of_scoring_null_blank(
    raw_and_labels, tmp_path, bad
):
    # 응답을 못 읽은 것이 정답 null 칸에서 「null에 비움」(맞음)으로 세어지면 점수가 부풀려진다
    result, md = run_eval(
        raw_and_labels, "tune", tmp_path, lambda p: bad if "공고B" in p else fake_ask(p)
    )
    assert [p for p, _ in result.skipped] == ["B"]
    assert {c.pbno for c in result.cells} == {"T", "A", "K"}
    assert "B:" in md.split("건너뛴 공고")[1]


@pytest.mark.parametrize("pbno", ["A", "K"])  # A는 전체 텍스트, K는 묶음으로 거주지를 묻는다
@pytest.mark.parametrize("which", ["다음 1개 필드", "다음 2개 필드"])
def test_a_malformed_reply_from_only_one_of_the_two_calls_still_skips_the_notice(
    raw_and_labels, tmp_path, pbno, which
):
    # 두 호출 중 하나만 깨져도 그 호출의 빈 칸이 다른 호출 결과와 합쳐져 맞음으로 세어지면 안 된다
    def ask(prompt):
        if which in prompt and (f"공고{pbno}" in prompt or (pbno == "K" and "K단지" in prompt)):
            return "not json"
        return fake_ask(prompt)

    result, _ = run_eval(raw_and_labels, "tune", tmp_path, ask)
    assert [p for p, _ in result.skipped] == [pbno]
    assert pbno not in {c.pbno for c in result.cells}


def test_a_notice_over_the_context_limit_is_skipped_not_fatal(raw_and_labels, tmp_path):
    from cheongyak_extract.llm import ContextExceeded

    def ask(prompt):
        if "공고B" in prompt:
            raise ContextExceeded("입력이 너무 길다")
        return fake_ask(prompt)

    result, md = run_eval(raw_and_labels, "tune", tmp_path, ask)
    assert [p for p, _ in result.skipped] == ["B"]
    assert "컨텍스트 한도 초과" in md.split("건너뛴 공고")[1]
    assert len(result.cells) == 9


def test_a_value_with_no_ground_on_the_page_is_blank_and_the_reason_is_reported(
    raw_and_labels, tmp_path
):
    from cheongyak_extract.extract import NEITHER_IN_PAGE

    def ask(prompt):
        if "공고A" not in prompt or "다음 1개 필드" in prompt:
            return fake_ask(prompt)
        body = {f: {"value": None, "evidence": None, "page": None} for f in (RESALE, INCOME)}
        body[RESALE] = {"value": "7년", "evidence": "지어낸 문장", "page": 1}
        return json.dumps(body, ensure_ascii=False)

    result, md = run_eval(raw_and_labels, "tune", tmp_path, ask)
    cell_a = next(c for c in result.cells if (c.pbno, c.field) == ("A", RESALE))
    assert (cell_a.state, cell_a.value, cell_a.why) == (pf.BLANK, None, NEITHER_IN_PAGE)
    assert NEITHER_IN_PAGE in md


# --- 정답 파일 둘의 구조와 요약 ---


def test_a_label_file_without_tune_key_is_read_when_the_split_has_no_tune():
    pages = {"P": BLOCK_PAGES}
    data = {
        "test": ["P"],
        "cells": {"P": {RESIDENT: cell("해당지역 100%", "해당지역 거주자(수원시)", 3)}},
    }
    got = pf.check_labels(data, pf.Split([], ["P"]), pages, expected=1, fields=(RESIDENT,))
    assert [(c.pbno, c.field, c.problems, c.rule) for c in got] == [("P", RESIDENT, (), 1)]
    with pytest.raises(ValueError, match="test"):
        pf.check_labels({**data, "tune": []}, pf.Split([], ["P"]), pages, 1, (RESIDENT,))


def test_a_resident_only_file_with_another_field_is_an_error():
    pages = {"P": BLOCK_PAGES}
    data = {"test": ["P"], "cells": {"P": {RESALE: null(), RESIDENT: null()}}}
    with pytest.raises(ValueError, match="필드가 더 있다"):
        pf.check_labels(data, pf.Split([], ["P"]), pages, 1, (RESIDENT,))


def test_label_rule_is_1_with_a_block_else_2_or_3_from_the_note_else_none():
    def rule(pages, note):
        raw = cell("해당지역 100%", "해당지역 거주자 우선", 2, note)
        return pf._resident_rule(raw, pages)

    assert rule(BLOCK_PAGES, None) == 1
    assert rule(NO_BLOCK_PAGES, "p2 공통 표") == 2
    assert rule(NO_BLOCK_PAGES, "해당지역 우선 문장") == 3
    assert rule(NO_BLOCK_PAGES, "p2") is None
    assert pf._resident_rule(null(), NO_BLOCK_PAGES) is None


def test_pick_resident_takes_30_from_the_sorted_rest_with_seed_1522():
    import random

    pbnos = [f"2026{i:06d}" for i in range(100, 200)][::-1]
    used = sorted(pbnos)[:50]
    got = pf.pick_resident(pbnos, used)
    rest = sorted(set(pbnos) - set(used))
    assert got == pf.Split([], random.Random(1522).sample(rest, 30))
    assert len(got.test) == 30 and not set(got.test) & set(used)


def test_labels_report_counts_blocks_rules_reasons_and_both_files(
    raw_and_labels, resident_set, tmp_path
):
    raw, labels_path, split = raw_and_labels
    raw30, path30, split30 = resident_set
    for src in raw30.iterdir():  # 두 raw를 한 디렉터리에 합친다
        (raw / src.name).mkdir()
        for f in src.iterdir():
            (raw / src.name / f.name).write_bytes(f.read_bytes())
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    data["cells"]["A"][RESALE] = cell("6개월, 3년", "전매제한 3년", 1)  # 6이 quote에 없다
    labels_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "labels.md"
    cells = pf.check_pdf_labels(
        raw,
        labels_path,
        path30,
        out,
        tune_split=split,
        test_split=split30,
        tune_expected=12,
        test_expected=2,
    )
    md = out.read_text(encoding="utf-8")
    assert len(cells) == 14 and len([c for c in cells if c.problems]) == 1
    # 공고 6건(T A B K P Q) 중 K·P에 묶음이 있다
    assert "PDF 텍스트가 있는 공고 6건 중 일반공급 ①지역 묶음을 찾은 공고 2건" in md
    assert "정답 파일의 공고 6건 중 묶음이 있는 공고 2건, 없는 공고 4건" in md
    assert "| 숫자가 quote에 없음 | 1 |" in md  # 사유별 수
    assert "| 1 일반공급 ①지역 묶음 | 2 |" in md  # K·P
    assert "| 2 공통 표 | 1 |" in md  # A
    assert "| 3 해당지역 우선 문장 | 1 |" in md  # Q
    assert "| null (읽은 곳이 없다) | 2 |" in md  # T·B
    assert "labels.json" in md and "resident.json" in md
    assert f"| {RESIDENT} | 4 | 2 | 0 |" in md  # 거주지는 두 파일을 합쳐 6칸
    assert f"| {RESALE} | 2 | 2 | 1 |" in md


# --- 일반공급 ①지역 묶음(설계 §고르는 규칙 1) ---

MULTI_CHILD = (
    "  ■ 당첨자 선정 순서  : ①지역 → ②배점\n"
    "  ■ ①지역  : 해당 시·도 거주자 50% → 기타지역 거주자 50%\n"
    "  ■ ②배점\n"
)
ELDER = "  ■ ①지역  : 해당지역 거주자 → 기타지역 거주자\n"
GENERAL = (
    "                 - 1순위 가점제  : ①지역 → ②가점\n"
    "                 - 2순위  : ①지역 → ②추첨\n"
    "\n"
    "       ■ ①지역  : 해당지역 거주자(수원시 거주자) → 기타지역 거주자(경기도 거주자)\n"
    "       ■ ②가점\n"
    "                 - 전용면적별 적용비율\n"
)


def test_resident_block_picks_the_general_supply_one_not_the_multi_child_50_percent():
    pages = ["표지", MULTI_CHILD, ELDER, GENERAL]  # 2026000449 꼴
    got = pf.resident_block(pages)
    assert got.page == 4
    assert "해당지역 거주자(수원시 거주자)" in got.text
    assert "50%" not in got.text


def test_resident_block_runs_from_the_marker_to_just_before_the_next_marker_line():
    got = pf.resident_block([GENERAL])
    assert got.text.startswith("■ ①지역")
    assert "경기도 거주자)" in got.text
    assert "②가점" not in got.text and "전용면적" not in got.text


def test_resident_block_follows_the_line_after_a_marker_only_line():
    page = (
        "   - 2순위  : ①지역 → ②추첨\n\n"
        "       ■ ①지역\n"
        "  당첨자         - 해당지역 거주자 (춘천시 6개월 이상) → 기타지역 거주자\n"
        " 선정방법  ■ ②가점\n"
        "     - 적용비율\n"
    )  # 2026000312 꼴: 「■ ①지역」만 한 줄이고 내용은 다음 줄에 있다
    got = pf.resident_block(["표지", page])
    assert got.page == 2
    assert "춘천시 6개월 이상" in got.text
    assert "②가점" not in got.text and "적용비율" not in got.text


@pytest.mark.parametrize(
    "order,area",
    [
        ("- 2순위  : ① 지역 → ②추첨", "■ ① 지역 : 해당지역 거주자"),
        ("- 2 순위 :①지역 → ②추첨", "■ ①지역: 해당지역 거주자"),
    ],
)
def test_resident_block_allows_spaces_inside_the_markers(order, area):
    got = pf.resident_block([f"{order}\n{area}\n"])
    assert got is not None and "해당지역 거주자" in got.text


def test_resident_block_is_none_without_the_2nd_rank_line():
    assert pf.resident_block(["표지", MULTI_CHILD, ELDER]) is None
    assert pf.resident_block([]) is None


def test_resident_block_is_none_when_the_area_line_is_more_than_3_text_lines_below():
    # 빈 줄은 세지 않는다. 글이 든 줄 3개를 지나면 ①지역 줄이 아니다
    page = "- 2순위  : ①지역 → ②추첨\n\nㄱ\n\nㄴ\n\nㄷ\n\n■ ①지역 : 해당지역 거주자\n"
    assert pf.resident_block([page]) is None


# --- 규칙 1이 받는 꼴(#179 설계 §설계 결정 1) ---

REGION = "해당지역 거주자(수원시) → 기타지역 거주자(경기도)"


def test_resident_block_reads_a_bracketed_rank_line_and_skips_blank_lines_to_the_area_line():
    # 2026000103·162·502 꼴: 순위 줄이 `[ ① 지역 ▶ ② 추첨 ]`이고 ①지역 줄이 소제목 아래 있다
    page = (
        " - 1순위 가점제 : [ ① 지역 ▶ ② 가점 ]        - 2순위 : [ ① 지역 ▶ ② 추첨 ]\n"
        " - 1순위 추첨제 : [ ① 지역 ▶ ② 무주택자 우선공급 ▶ ③ 추첨 ]\n\n\n"
        "  일반공급 1순위 가점제 당첨자 선정방법\n\n\n"
        f" ① 지역 : {REGION}\n"
        " ② 가점\n"
    )
    got = pf.resident_block(["표지", page])
    assert got.page == 2
    assert got.text == f"① 지역 : {REGION}"


@pytest.mark.parametrize("mark", ["￭ ", "• ", "▌ ", ""])
def test_resident_block_allows_a_head_mark_other_than_the_square_or_none(mark):
    # 2026000116·274·342·382·445·455·471 꼴
    order = "        - 2순위  : ①지역 → ②추첨\n"
    page = f"{order}         {mark}①지역  : {REGION}\n         {mark}②가점\n"
    got = pf.resident_block([page])
    assert got.text.endswith(REGION) and "②" not in got.text
    assert got.text.startswith(mark.strip() or "①")


def test_resident_block_follows_a_rank_line_at_the_end_of_a_page_to_the_area_line_on_the_next():
    # 2026000454 꼴: 순위 줄은 8쪽 끝, ①지역 줄은 9쪽 첫 줄. 쪽 번호는 ①지역 줄이 있는 쪽이다
    pages = ["- 2순위  : ①지역 → ②추첨\n\n   - 8 -", f"■ ①지역  : {REGION}\n\n■ ②가점\n"]
    got = pf.resident_block(pages)
    assert got.page == 2 and REGION in got.text


def test_resident_block_goes_on_over_a_page_break_until_the_next_marker_line():
    # 2026000270·310 꼴: 묶음이 쪽 끝에서 잘렸다
    pages = [
        f"- 2순위  : ①지역 → ②추첨\n■ ①지역 : {REGION}\n  → 기타 거주자\n",
        "  (경기도 6개월 이상 거주자)\n※ 안내\n■ ②가점\n",
    ]
    got = pf.resident_block(pages)
    assert got.page == 1
    assert "(경기도 6개월 이상 거주자)" in got.text
    assert "안내" not in got.text


def test_resident_block_ends_at_a_line_that_starts_with_a_marker_or_has_the_circled_2():
    for stop in ("※ 안내", "• 안내", "￭ 안내", "▌ 안내", "당첨자  ②가점"):
        page = (
            f"- 2순위  : ①지역 → ②추첨\n■ ①지역 : {REGION}\n  이어지는 줄\n{stop}\n끝나고 난 줄\n"
        )
        got = pf.resident_block([page])
        assert "이어지는 줄" in got.text and "끝나고 난 줄" not in got.text, stop


# --- 거주지 값의 꼴·합·정답 검사(설계 §값의 꼴과 계산, §정답 검사에 더하는 것) ---


@pytest.mark.parametrize(
    "value,want",
    [
        ("제주특별자치도 100% / 기타지역 0%", "100"),  # 0%인 지역은 정규형에서 뺀다
        ("수원시 100% / 기타 0.0%", "100"),
        ("해당지역 100%", "100"),
        ("평택시 30% / 경기도 20% / 기타 50%", "30/20/50"),
        ("해당지역 0%", None),  # 빼고 나면 아무것도 안 남는다
    ],
)
def test_resident_normal_form_drops_zero_percent_regions(value, want):
    assert pf.normal_form(RESIDENT, value) == want


def test_zero_percent_is_kept_for_the_other_percent_fields():
    assert pf.normal_form(INCOME, "0% (맞벌이 120%)") == "0/120"


def test_an_old_form_label_and_the_new_form_value_compare_equal():
    assert pf.cell_state(RESIDENT, "제주특별자치도 100% / 기타지역 0%", "해당지역 100%") == pf.RIGHT


@pytest.mark.parametrize(
    "value,want",
    [
        ("해당 50% / 서울특별시 50% / 기타 50%", True),  # 2026000449의 150
        ("평택시 30% / 경기도 20% / 기타 50%", False),
        ("해당지역 100%", False),
        ("제주특별자치도 100% / 기타지역 0%", False),
        ("해당지역 70% / 기타 20%", True),
        ("해당지역 우선", False),  # %가 없으면 합을 말할 수 없다
        (None, False),
    ],
)
def test_percent_sum_is_not_100_is_recognised(value, want):
    assert pf.sum_is_not_100(value) is want


BLOCK_PAGES = [
    "표지",
    "■ ①지역 : 해당 시·도 거주자 50% → 기타지역 거주자 50%\n",  # 2쪽: 다자녀 특별공급
    "- 2순위  : ①지역 → ②추첨\n\n"
    "■ ①지역 : 해당지역 거주자(수원시) → 기타지역 거주자(서울)\n■ ②가점\n",
]
NO_BLOCK_PAGES = ["표지", "<표2> 지역우선 공급기준 해당지역 100% 기타지역 0%\n해당지역 거주자 우선"]


def resident_problems(value, quote, page, pages, note=None):
    raw = cell(value, quote, page, note)
    return pf._problems(RESIDENT, raw, pages)


def test_a_resident_cell_read_inside_the_block_has_no_problem():
    got = resident_problems("해당지역 100%", "해당지역 거주자(수원시)", 3, BLOCK_PAGES)
    assert got == ()


def test_a_resident_quote_outside_the_block_is_flagged_even_if_it_is_on_its_page():
    # 2쪽에는 있는 문장이지만 일반공급 ①지역 묶음(3쪽) 밖이다
    got = resident_problems("해당지역 50%", "해당 시·도 거주자 50%", 2, BLOCK_PAGES)
    assert pf.QUOTE_OUTSIDE_BLOCK in got
    assert pf.QUOTE_NOT_ON_PAGE not in got


@pytest.mark.parametrize(
    "value",
    [
        "제주특별자치도 100% / 기타지역 0%",  # 0%인 지역을 적었다
        "해당지역 100% / 기타 50%",  # 「해당지역 100%」와 %를 섞었다
        "수원시 100%",  # 한 지역 100%는 「해당지역 100%」로 쓴다
    ],
)
def test_a_value_that_is_not_in_the_table_form_is_flagged(value):
    got = resident_problems(value, "해당지역 거주자(수원시)", 3, BLOCK_PAGES)
    assert pf.BAD_SHAPE in got


def test_a_percent_sum_other_than_100_is_flagged_on_a_label():
    value = "해당 50% / 서울 50% / 기타 50%"
    got = resident_problems(value, "해당지역 거주자(수원시)", 3, BLOCK_PAGES)
    assert pf.SUM_NOT_100 in got


@pytest.mark.parametrize(
    "note,flagged",
    [
        ("p2 <표2> 공통 표", False),
        ("해당지역 우선 문장에서 읽었다", False),
        ("p2에서 읽었다", True),
        (None, True),
    ],
)
def test_without_a_block_the_note_says_which_of_rule_2_or_3_it_was_read_from(note, flagged):
    got = resident_problems("해당지역 100%", "해당지역 거주자 우선", 2, NO_BLOCK_PAGES, note)
    assert (pf.NO_RULE_NOTE in got) is flagged


def test_the_block_checks_do_not_apply_to_the_other_fields():
    raw = cell("3년", "전매제한 3년", 2)
    assert pf._problems(RESALE, raw, ["표지", "전매제한 3년"]) == ()


def test_load_without_a_split_picks_the_old_50_for_tune_and_30_new_ones_outside_them_for_test(
    tmp_path, monkeypatch
):
    # 운영 경로: split을 안 주면 eligible 목록에서 코드가 직접 뽑는다(다른 테스트는 split을 넘긴다)
    eligible = [f"N{i:03d}" for i in range(90)]
    monkeypatch.setattr(pf, "pdf_pages", lambda path: ["쪽"])
    first = pf.pick(eligible)
    second = pf.pick_resident(eligible, [*first.tune, *first.test])
    assert len(first.tune) + len(first.test) == 50 and len(second.test) == 30
    assert not set(second.test) & {*first.tune, *first.test}

    def write(name, body):
        path = tmp_path / name
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return path

    tune_file = write(
        "tune.json",
        {
            "tune": first.tune,
            "test": first.test,
            "cells": {p: {f: null() for f in pf.PDF_FIELDS} for p in [*first.tune, *first.test]},
        },
    )
    test_file = write(
        "test.json", {"test": second.test, "cells": {p: {RESIDENT: null()} for p in second.test}}
    )
    _, split, _, cells = pf._load(tmp_path, tune_file, "tune", None, None, eligible)
    assert split == first and len(cells) == 150
    _, split, _, cells = pf._load(tmp_path, test_file, "test", None, None, eligible)
    assert split == second and len(cells) == 30 and {c.field for c in cells} == {RESIDENT}
