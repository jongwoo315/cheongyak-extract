import json
from pathlib import Path

import pytest

from cheongyak_extract import __main__ as cli
from cheongyak_extract.measure import Pair, load_pairs, measure_normalize, render, tally
from cheongyak_extract.normalize import normalize

HTML = (Path(__file__).parent / "fixtures" / "detail.html").read_text(encoding="utf-8")
RAW = Path(__file__).parent.parent / "data" / "raw"
FORMS = Path(__file__).parent / "fixtures" / "pdf_forms.json"


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
    assert "| p1 | g | B | b | B | b | — |" in md  # 정답·모의값·두 정규형·비고
    assert "| p1 | f |" not in md  # 맞은 쌍은 목록에 없다


def test_measure_normalize_subcommand_writes_report(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "measure_normalize", lambda *a: calls.append(a) or "리포트")
    assert cli.main(["measure-normalize"]) == 0
    raw, fixture, out = calls[0]
    assert (str(raw), str(out)) == ("data/raw", "reports/normalize.md")
    assert str(fixture) == "tests/fixtures/pdf_forms.json"


def test_measure_normalize_counts_form_differences_as_matches(tmp_path):
    raw = tmp_path / "raw" / "p1"
    raw.mkdir(parents=True)
    (raw / "detail.html").write_text(HTML, encoding="utf-8")
    fixture = tmp_path / "forms.json"
    forms = {"p1": {"모집공고일": {"value": "2026.10.23.(금)", "page": 1}}}
    fixture.write_text(json.dumps(forms, ensure_ascii=False), encoding="utf-8")
    md = measure_normalize(tmp_path / "raw", fixture, tmp_path / "out" / "normalize.md")
    assert "정규화 전 0/8" in md and "정규화 후 1/8" in md
    assert (tmp_path / "out" / "normalize.md").read_text(encoding="utf-8") == md


def test_render_says_so_when_every_pair_matches():
    md = render([Pair("p1", "f", "A", "A")], lambda f, v: v.strip())
    assert "안 맞는 쌍 없음" in md


def test_note_in_fixture_is_shown_next_to_the_mismatch():
    pairs = [Pair("p1", "g", "B", "b", note="정답 쪽 차이")]
    assert "| p1 | g | B | b | B | b | 정답 쪽 차이 |" in render(pairs, lambda f, v: v.strip())


def test_load_pairs_reads_optional_note(tmp_path):
    raw = tmp_path / "raw" / "p1"
    raw.mkdir(parents=True)
    (raw / "detail.html").write_text(HTML, encoding="utf-8")
    fixture = tmp_path / "forms.json"
    cell = {"value": "10세대", "page": 3, "note": "메모"}
    fixture.write_text(json.dumps({"p1": {"공급규모": cell}}, ensure_ascii=False), encoding="utf-8")
    (pair,) = load_pairs(tmp_path / "raw", fixture, fields=("공급규모",))
    assert pair.note == "메모"


def test_load_pairs_rejects_an_empty_fixture(tmp_path):
    fixture = tmp_path / "forms.json"
    fixture.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_pairs(tmp_path, fixture)


def test_real_fixture_matches_more_pairs_after_normalizing_than_before():
    if not (RAW / "2026000530" / "detail.html").exists():
        pytest.skip("data/raw 없음")  # 정답 HTML이 커밋돼 있지 않아 CI에서는 못 돈다
    pairs = load_pairs(RAW, FORMS)
    before = tally(pairs, lambda f, v: v.strip())
    after = tally(pairs, normalize)
    assert len(pairs) == 24
    assert after >= 22 and after > before  # plan 실패 징후 1의 「통과」 구간
