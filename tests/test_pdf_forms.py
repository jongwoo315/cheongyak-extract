"""모의 추출값(tests/fixtures/pdf_forms.json)이 PDF 해당 쪽에 실제로 있는지 확인한다.

정답에 맞춰 만든 값이 아니라 PDF에서 복사한 꼴이어야 한다. data/raw가 없으면 건너뛴다(CI).
"""

import json
from pathlib import Path

import pytest

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.pdf_text import pages

FIXTURE = Path(__file__).parent / "fixtures" / "pdf_forms.json"
RAW = Path(__file__).parent.parent / "data" / "raw"
FORMS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _squeeze(s: str) -> str:
    return "".join(s.split())


def test_fixture_has_24_pairs_over_eight_fields():
    assert len(FORMS) == 3
    for form in FORMS.values():
        assert tuple(form) == FIELDS
        # 못 찾은 필드는 null로 두되 이유(note)를 적는다. null만 가득한 fixture가 통과하지 않게 한다
        assert all(c["value"] is not None or c.get("note") for c in form.values())


@pytest.mark.parametrize("pbno", FORMS)
def test_every_value_is_on_its_page(pbno):
    pdf = RAW / pbno / "notice.pdf"
    if not pdf.exists():
        pytest.skip("data/raw 없음")
    text = pages(pdf)
    for field, cell in FORMS[pbno].items():
        if cell["value"] is None:
            continue
        assert 1 <= cell["page"] <= len(text), f"{pbno} {field} p{cell['page']} 쪽 범위 밖"
        page = text[cell["page"] - 1]
        assert _squeeze(cell["value"]) in _squeeze(page), f"{pbno} {field} p{cell['page']}"
