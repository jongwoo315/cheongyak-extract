from cheongyak_extract.extract import FIELDS, Extraction
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


def test_unknown_field_is_only_stripped():
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


def test_page_out_of_range_is_not_ok_and_does_not_crash():
    for page in (0, 3):
        (m,) = metrics([doc("A", Extraction("A", "foo", page), ["foo", "bar"])], ("f",))
        assert m.page_ok == 0.0


def test_accuracy_compares_normalized_forms_of_both_sides():
    truth = {"모집공고일": "2026-10-23 (헤럴드경제신문)", "시행사": "(주)반도건설"}
    ex = {
        "모집공고일": Extraction("2026.10.23.(금)", "e", 1),
        "시행사": Extraction("반도종합건설", "e", 1),
    }
    docs = [Doc("x", truth, ex, ["e"])]
    date, company = metrics(docs, ("모집공고일", "시행사"))
    assert date.accuracy == 1.0
    assert company.accuracy == 0.0


def test_stub_extraction_stays_at_zero_accuracy_and_full_blank():
    truth = {f: "2026-11-10" for f in FIELDS}
    stub = {f: EMPTY for f in FIELDS}
    rows = metrics([Doc("x", truth, stub, ["p"])], FIELDS)
    assert all(m.accuracy == 0.0 and m.blank == 1.0 for m in rows)
