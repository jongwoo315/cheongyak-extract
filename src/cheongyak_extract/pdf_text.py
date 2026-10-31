"""공고문 PDF에서 쪽마다 텍스트를 뽑는다. 리스트 인덱스 + 1이 쪽 번호다."""

from pathlib import Path

import pymupdf

# 텍스트 방식. T0는 sort=True 텍스트만, T1은 T0 뒤에 그 쪽 표를 markdown으로 붙인다.
TEXT_MODES = ("T0", "T1")


def _page_text(page: pymupdf.Page, sort: bool, tables: bool) -> str:
    text = page.get_text(sort=sort)
    if not tables:
        return text
    found = [t.to_markdown() for t in page.find_tables().tables]
    return text + "".join(f"\n[표]\n{md}" for md in found)


def pages(path: Path, sort: bool = True, tables: bool = False) -> list[str]:
    """sort=True는 읽는 순서로 준다. sort=False(pymupdf 기본)는 표 칸 글자를 흩어 놓는다.

    tables=True는 쪽 텍스트 뒤에 그 쪽 `find_tables()` 표를 markdown으로 붙인다.
    표는 머리글과 값이 같은 열에 놓여, 줄 단위 텍스트에서 떨어진 칸을 짝지을 수 있다.
    """
    with pymupdf.open(path) as doc:
        return [_page_text(page, sort, tables) for page in doc]


def has_text(path: Path) -> bool:
    """텍스트가 있는 쪽이 하나라도 있다. 첫 쪽을 찾으면 멈춘다(스캔 PDF는 끝까지 읽는다)."""
    with pymupdf.open(path) as doc:
        return any(page.get_text().strip() for page in doc)


def pdf_problem(path: Path) -> str | None:
    """열리지 않는 이유. 쪽 수 1 이상이고 마지막 쪽 텍스트까지 읽히면 None이다."""
    try:
        with pymupdf.open(path) as doc:
            if not doc.is_pdf:  # pymupdf는 HTML 같은 파일도 문서로 연다
                return "PDF가 아님"
            if len(doc) < 1:
                return "쪽 수가 0"
            doc[-1].get_text()
    except Exception as e:  # 열기·텍스트 뽑기 실패가 한 가지 예외가 아니다(#146 리뷰 13)
        return f"{type(e).__name__}: {e}"
    return None
