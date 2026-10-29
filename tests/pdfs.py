"""테스트용 PDF 바이트."""

from functools import cache

import pymupdf


@cache  # pymupdf가 문서 ID를 매번 새로 넣으므로, 같은 글자는 같은 바이트로 돌려줘야 비교된다
def make_pdf(text: str = "공고문") -> bytes:
    """pymupdf로 연 뒤 마지막 쪽 텍스트까지 읽히는 1쪽짜리 PDF."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text, fontname="korea")
    data = doc.tobytes()
    doc.close()
    return data


TRUNCATED_PDF = make_pdf()[:60]  # `%PDF-1.7` 머리만 있고 뒤가 끊겼다
