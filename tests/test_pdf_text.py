import pymupdf

from cheongyak_extract.pdf_text import pages


def make_pdf(path, texts):
    doc = pymupdf.open()
    for t in texts:
        doc.new_page().insert_text((72, 72), t)
    doc.save(path)
    doc.close()


def test_pages_returns_one_text_per_page(tmp_path):
    pdf = tmp_path / "notice.pdf"
    make_pdf(pdf, ["first page", "second page"])
    out = pages(pdf)
    assert len(out) == 2
    assert "first page" in out[0] and "second page" in out[1]


def test_pages_sorts_by_reading_order_by_default(tmp_path):
    # 아래 줄을 먼저 그린 PDF: 기본 순서는 그린 순서, sort=True는 위에서 아래로 읽는 순서
    pdf = tmp_path / "notice.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 200), "lower line")
    page.insert_text((72, 72), "upper line")
    doc.save(pdf)
    doc.close()
    assert pages(pdf)[0].index("upper") < pages(pdf)[0].index("lower")
    assert pages(pdf, sort=False)[0].index("lower") < pages(pdf, sort=False)[0].index("upper")


def make_table_pdf(path, rows):
    """1쪽에 본문 한 줄과 선으로 그린 표 하나, 2쪽에는 표 없이 문장 한 줄."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "본문 문장", fontname="korea")
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            rect = pymupdf.Rect(72 + c * 120, 100 + r * 30, 72 + (c + 1) * 120, 130 + r * 30)
            page.draw_rect(rect, width=0.8)
            page.insert_text((rect.x0 + 4, rect.y0 + 20), text, fontname="korea")
    doc.new_page().insert_text((72, 72), "표 없는 쪽", fontname="korea")
    doc.save(path)
    doc.close()


TABLE = [["구 분", "시행수탁자", "시공사"], ["상 호", "하나자산신탁", "아이파크현대산업개발"]]


def test_tables_true_appends_markdown_of_that_pages_table_after_the_text(tmp_path):
    pdf = tmp_path / "notice.pdf"
    make_table_pdf(pdf, TABLE)
    t0, t1 = pages(pdf), pages(pdf, tables=True)
    assert t1[0].startswith(t0[0])  # T0 텍스트를 지우지 않는다
    assert "|구 분|시행수탁자|시공사|" in t1[0]
    assert "|상 호|하나자산신탁|아이파크현대산업개발|" in t1[0]  # 머리글과 값이 같은 열에 있다
    assert "|구 분|" not in t0[0]


def test_tables_true_leaves_a_page_without_a_table_as_it_was(tmp_path):
    pdf = tmp_path / "notice.pdf"
    make_table_pdf(pdf, TABLE)
    assert pages(pdf, tables=True)[1] == pages(pdf)[1]


def test_tables_default_is_off():
    import inspect

    assert inspect.signature(pages).parameters["tables"].default is False
