"""프롬프트 고정 시점의 다듬는 공고 9건의 실제 응답(tests/fixtures/llm/)을 가짜 LLM으로 재생한다.

CI에는 공고문 PDF가 없어서(data/raw/는 git 밖) 쪽 텍스트는 응답의 근거 문장으로 만든다.
거르는 규칙과 응답 모양을 재는 테스트지 정확도를 재는 테스트가 아니다.
"""

import json
from pathlib import Path

import pytest

from cheongyak_extract import extract as ex_reason
from cheongyak_extract.extract import FIELDS, RULES, extract

LLM_FIXTURES = Path(__file__).parent / "fixtures" / "llm"
TUNE_NOTICES = (
    "2026000518",
    "2026000530",
    "2026000532",
    "2026000517",
    "2026000496",
    "2026000502",
    "2026000514",
    "2026000513",
    "2026000509",
)


def load(pbno: str) -> tuple[str, dict]:
    text = (LLM_FIXTURES / f"{pbno}.json").read_text(encoding="utf-8")
    return text, json.loads(text)


def pages_from_evidence(body: dict) -> list[str]:
    """각 쪽에 그 쪽의 근거 문장을 놓는다. 줄바꿈은 공백으로 바꾼다."""
    last = max(c["page"] for c in body.values())
    pages = [""] * last
    for c in body.values():
        pages[c["page"] - 1] += c["evidence"].replace("\n", " ") + "\n"
    return pages


def test_there_is_one_recorded_response_per_tuning_notice():
    assert sorted(p.stem for p in LLM_FIXTURES.glob("*.json")) == sorted(TUNE_NOTICES)


@pytest.mark.parametrize("pbno", TUNE_NOTICES)
def test_recorded_response_has_strict_shape(pbno):
    _, body = load(pbno)
    assert tuple(body) == FIELDS
    for cell in body.values():
        assert set(cell) == {"value", "evidence", "page"}


@pytest.mark.parametrize("rule", ("A", "C"))
@pytest.mark.parametrize("pbno", TUNE_NOTICES)
def test_replay_passes_every_filter_rule_and_keeps_all_eight_fields(pbno, rule):
    text, body = load(pbno)
    out = extract(pages_from_evidence(body), lambda prompt: text, rule)
    assert out.blanked == {}
    assert tuple(out.fields) == FIELDS
    for f in FIELDS:
        got = out.fields[f]
        assert got.value == body[f]["value"].strip()
        assert got.page == body[f]["page"]


@pytest.mark.parametrize("pbno", TUNE_NOTICES)
def test_replay_under_b_blanks_only_values_missing_from_their_evidence(pbno):
    text, body = load(pbno)
    out = extract(pages_from_evidence(body), lambda prompt: text, "B")
    squash = ex_reason._squash
    expected = {f for f in FIELDS if squash(body[f]["value"]) not in squash(body[f]["evidence"])}
    assert set(out.blanked) == expected
    assert set(out.blanked.values()) <= {ex_reason.VALUE_NOT_IN_EVIDENCE}


def test_replay_has_values_that_are_not_in_their_evidence_so_the_b_test_is_not_vacuous():
    squash = ex_reason._squash
    missing = [
        (pbno, f)
        for pbno in TUNE_NOTICES
        for f, c in load(pbno)[1].items()
        if squash(c["value"]) not in squash(c["evidence"])
    ]
    assert missing


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("pbno", TUNE_NOTICES)
def test_replay_blanks_a_cell_when_neither_its_evidence_nor_its_value_is_on_the_page(pbno, rule):
    text, body = load(pbno)
    pages = pages_from_evidence(body)
    body["계약일"]["evidence"] = "원문에 없는 문장"
    body["계약일"]["value"] = "원문에 없는 값"
    out = extract(pages, lambda prompt: json.dumps(body, ensure_ascii=False), rule)
    assert "계약일" in out.blanked
    assert out.fields["계약일"].value is None
