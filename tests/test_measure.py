import json
from pathlib import Path

from cheongyak_extract import __main__ as cli
from cheongyak_extract.measure import Pair, load_pairs, render, tally

HTML = (Path(__file__).parent / "fixtures" / "detail.html").read_text(encoding="utf-8")


def test_tally_counts_strip_equal_pairs():
    pairs = [
        Pair("p1", "f", "A", " A "),  # strip 뒤 같다
        Pair("p1", "g", "A", "a"),  # 다르다
        Pair("p2", "f", "A", None),  # 모의값 없음 — 일치로 세지 않는다
    ]
    assert tally(pairs, lambda f, v: v.strip()) == 1


def test_load_pairs_joins_fixture_with_truth_by_pbno(tmp_path):
    raw = tmp_path / "raw" / "p1"
    raw.mkdir(parents=True)
    (raw / "detail.html").write_text(HTML, encoding="utf-8")
    fixture = tmp_path / "forms.json"
    forms = {"p1": {"공급규모": {"value": "10세대", "page": 3}}}
    fixture.write_text(json.dumps(forms, ensure_ascii=False), encoding="utf-8")
    (pair,) = load_pairs(tmp_path / "raw", fixture, fields=("공급규모",))
    assert (pair.pbno, pair.field, pair.mock) == ("p1", "공급규모", "10세대")
    assert pair.truth  # detail.html에서 읽은 정답


def test_render_shows_before_and_after_and_lists_mismatches():
    pairs = [Pair("p1", "f", "A", "A"), Pair("p1", "g", "B", "b")]
    md = render(pairs, lambda f, v: v.strip())
    assert "정규화 전 1/2" in md and "정규화 후 1/2" in md
    assert "| p1 | g | B | b | B | b |" in md  # 정답·모의값·두 정규형
    assert "| p1 | f |" not in md  # 맞은 쌍은 목록에 없다


def test_measure_normalize_subcommand_writes_report(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "measure_normalize", lambda *a: calls.append(a) or "리포트")
    assert cli.main(["measure-normalize"]) == 0
    raw, fixture, out = calls[0]
    assert (str(raw), str(out)) == ("data/raw", "reports/normalize.md")
    assert str(fixture) == "tests/fixtures/pdf_forms.json"
