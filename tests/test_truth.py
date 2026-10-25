from pathlib import Path

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.truth import parse_truth

DETAIL = (Path(__file__).parent / "fixtures" / "detail.html").read_text(encoding="utf-8")


def test_parse_truth_has_every_field_as_key():
    assert tuple(parse_truth(DETAIL)) == FIELDS


def test_parse_truth_values_match_fixture():
    assert parse_truth(DETAIL) == {
        "공급위치": (
            "인천광역시 계양구 동양동 420-3번지 일원 (인천계양 테크노밸리 공공주택지구 AC4블록)"
        ),
        "공급규모": "496세대",
        "모집공고일": "2026-10-23 (헤럴드경제신문)",
        "당첨자 발표일": "2026-11-11 ( https://www.gy-bando.com )",
        "계약일": "2026-11-23 ~ 2026-11-25",
        "시행사": "(주)반도건설",
        "시공사": "(주)반도건설",
        "입주예정월": "2029.08",
    }


def test_missing_cell_is_none():
    html = DETAIL.replace("입주예정월 : 2029.08", "").replace(
        "<td>(주)반도건설</td>", "<td></td>", 1
    )
    out = parse_truth(html)
    assert out["입주예정월"] is None
    assert out["시행사"] is None
    assert out["시공사"] == "(주)반도건설"
