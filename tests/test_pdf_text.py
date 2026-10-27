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
