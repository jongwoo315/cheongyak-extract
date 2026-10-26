"""설계에 쓴 공고 3건의 실제 응답(tests/fixtures/llm/)을 가짜 LLM으로 재생한다.

CI에는 공고문 PDF가 없어서(data/raw/는 git 밖) 쪽 텍스트는 응답의 근거 문장으로 만든다.
거르는 규칙과 응답 모양을 재는 테스트지 정확도를 재는 테스트가 아니다.
"""

import json
from pathlib import Path

import pytest

from cheongyak_extract.extract import FIELDS, extract

LLM_FIXTURES = Path(__file__).parent / "fixtures" / "llm"
DESIGN_NOTICES = ("2026000518", "2026000530", "2026000532")


def load(pbno: str) -> tuple[str, dict]:
    text = (LLM_FIXTURES / f"{pbno}.json").read_text(encoding="utf-8")
    return text, json.loads(text)


def pages_from_evidence(body: dict) -> list[str]:
    """근거가 있는 쪽까지 빈 쪽을 두고 각 쪽에 그 쪽의 근거 문장을 놓는다. 줄바꿈은 공백으로 바꾼다."""
    last = max(c["page"] for c in body.values())
    pages = [""] * last
    for c in body.values():
        pages[c["page"] - 1] += c["evidence"].replace("\n", " ") + "\n"
    return pages


def test_there_is_one_recorded_response_per_design_notice():
    assert sorted(p.stem for p in LLM_FIXTURES.glob("*.json")) == sorted(DESIGN_NOTICES)


@pytest.mark.parametrize("pbno", DESIGN_NOTICES)
def test_recorded_response_has_strict_shape(pbno):
    _, body = load(pbno)
    assert tuple(body) == FIELDS
    for cell in body.values():
        assert set(cell) == {"value", "evidence", "page"}


@pytest.mark.parametrize("pbno", DESIGN_NOTICES)
def test_replay_passes_every_filter_rule_and_keeps_all_eight_fields(pbno):
    text, body = load(pbno)
    out = extract(pages_from_evidence(body), lambda prompt: text)
    assert out.blanked == {}
    assert tuple(out.fields) == FIELDS
    for f in FIELDS:
        got = out.fields[f]
        assert got.value == body[f]["value"].strip()
        assert got.page == body[f]["page"]


@pytest.mark.parametrize("pbno", DESIGN_NOTICES)
def test_replay_blanks_a_cell_when_its_evidence_is_not_on_the_page(pbno):
    text, body = load(pbno)
    pages = pages_from_evidence(body)
    body["계약일"]["evidence"] = "원문에 없는 문장"
    out = extract(pages, lambda prompt: json.dumps(body, ensure_ascii=False))
    assert set(out.blanked) == {"계약일"}
