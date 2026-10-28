"""공고문 PDF에서 쪽마다 텍스트를 뽑는다. 리스트 인덱스 + 1이 쪽 번호다."""

from pathlib import Path

import pymupdf


def pages(path: Path, sort: bool = True) -> list[str]:
    """sort=True는 읽는 순서로 준다. sort=False(pymupdf 기본)는 표 칸 글자를 흩어 놓는다."""
    with pymupdf.open(path) as doc:
        return [page.get_text(sort=sort) for page in doc]
