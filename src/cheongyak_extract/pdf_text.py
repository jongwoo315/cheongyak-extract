"""공고문 PDF에서 쪽마다 텍스트를 뽑는다. 리스트 인덱스 + 1이 쪽 번호다."""

from pathlib import Path

import pymupdf


def pages(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]
