from cheongyak_extract.extract import Extraction
from cheongyak_extract.report import Doc, metrics, render_markdown

EMPTY = Extraction(None, None, None)


def doc(truth, ex, pages):
    return Doc(pbno="x", truth={"f": truth}, extracted={"f": ex}, pages=pages)


def test_metrics_follow_design_definitions():
    docs = [
        doc("A", Extraction("A", "foo", 1), ["foo bar"]),  # 맞음, 근거 위치 맞음
        doc("B", Extraction("X", "nope", 1), ["foo bar"]),  # 틀림, 지어낸 값, 근거 위치 틀림
        doc(None, Extraction("Y", "foo", 2), ["foo", "zzz"]),  # 비어야 하는데 채움, 근거 위치 틀림
        doc("C", EMPTY, ["foo"]),  # 빈 칸
    ]
    (m,) = metrics(docs, ("f",))
    assert m.field == "f"
    assert m.with_truth == 3
    assert m.accuracy == 1 / 3
    assert m.blank == 1 / 3
    assert m.fabricated == 1
    assert m.filled_empty == 1
    assert m.page_ok == 1 / 3


def test_compare_strips_but_does_not_normalize():
    (m,) = metrics([doc("2026-11-11", Extraction(" 2026-11-11 ", "e", 1), ["e"])], ("f",))
    assert m.accuracy == 1.0
    (m,) = metrics([doc("2026-11-11", Extraction("2026.11.11", "e", 1), ["e"])], ("f",))
    assert m.accuracy == 0.0


def test_evidence_match_ignores_line_breaks():
    (m,) = metrics([doc("A", Extraction("A", "foo bar", 1), ["foo\nbar"])], ("f",))
    assert m.fabricated == 0 and m.page_ok == 1.0


def test_denominator_zero_renders_dash():
    (m,) = metrics([doc(None, EMPTY, ["p"])], ("f",))
    assert m.with_truth == 0
    assert m.accuracy is None and m.blank is None and m.page_ok is None
    md = render_markdown([m])
    assert md.splitlines()[0].startswith("| 필드 | 정답 있음 | 정확도 | 빈 칸 |")
    assert "| f | 0 | — | — | 0 | 0 | — |" in md


def test_render_markdown_formats_percentages():
    (m,) = metrics([doc("A", EMPTY, ["p"])], ("f",))
    assert "| f | 1 | 0% | 100% | 0 | 0 | — |" in render_markdown([m])


def test_empty_evidence_counts_as_fabricated():
    for evidence in ("", "  "):
        (m,) = metrics([doc("A", Extraction("A", evidence, 1), ["foo"])], ("f",))
        assert m.fabricated == 1 and m.page_ok == 0.0

