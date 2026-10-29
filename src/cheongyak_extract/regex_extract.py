"""정규식 baseline. 라벨 뒤의 값을 줍는 단순한 패턴만 쓴다. extract.py와 같은 꼴을 돌려준다.

공고별 예외는 두지 않는다(설계 문서 §정규식 추출기의 모양). 시행사·시공사만 예외로 상호 줄을
칸으로 나눠 첫 칸을 시행사, 나머지를 시공사로 읽는다. 시공사가 약한 이유가 이것이다.
근거는 패턴이 걸린 줄, 쪽은 그 줄이 있는 쪽이다. 필드마다 파인더를 순서대로 써서
값이 나오는 첫 줄을 쓴다(라벨만 있고 값이 없는 줄은 건너뛴다).
"""

import re
from collections.abc import Callable

from cheongyak_extract.extract import EMPTY, FIELDS, Extraction

_DATE = r"\d{4}\s*[.-]\s*\d{1,2}\s*[.-]\s*\d{1,2}\.?"
_COUNT = r"(?<![\d,])(\d{1,3}(?:,\d{3})+|\d+)\s*세대"

_LOCATION = re.compile(r"공급위치\s*:\s*(?P<v>\S.*)")
_SCALE = re.compile(r"공급규모(?:\s*및\s*내역)?\s*:\s*(?P<v>\S.*)")
_NOTICE_DATE = re.compile(rf"모집\s*공고일\s*(?:은|인|는|:)?\s*(?P<v>{_DATE})")
_WINNER_DATE = re.compile(rf"당첨자\s*발표일?\s*(?:은|인|는|:)?\s*(?P<v>{_DATE})")
_CONTRACT = re.compile(
    rf"(?:정당\s*계약|계약\s*(?:체결\s*)?(?:기간|일)|계약\s*체결)\s*[:(]?\s*(?P<s>{_DATE})"
    r"(?:\s*\([^)]*\))?\s*[~∼-]\s*(?:(?P<y>\d{4})\s*[.-]\s*)?"
    r"(?P<m>\d{1,2})\s*[.-]\s*(?P<d>\d{1,2})\.?"
)
_MOVE_IN = re.compile(
    r"입주\s*(?:시기|예정(?:시기|일|월)?)\s*:?\s*"
    r"(?P<v>\d{4}\s*(?:년\s*\d{1,2}\s*월|\.\s*\d{1,2}))"
)
_OWNER_HEADER = re.compile(r"구\s*분.*(?:사업주체|시행)")
_COMPANY_ROW = re.compile(r"^\s*상\s*호(?:\s*명)?\s{2,}(?P<v>\S.*)$")
_OWNER_LABEL = re.compile(r"^\s*사업주체\s{2,}(?P<v>\S.*)$")
_HEADER_LOOKBACK = 3

Finder = Callable[[list[str], int], str | None]


def _find(pages: list[str], finder: Finder) -> Extraction:
    for page_no, text in enumerate(pages, start=1):
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if (value := finder(lines, i)) and value.strip():
                return Extraction(value.strip(), line.strip(), page_no)
    return EMPTY


def _labelled(pattern: re.Pattern[str]) -> Finder:
    def finder(lines: list[str], i: int) -> str | None:
        m = pattern.search(lines[i])
        return m.group("v") if m else None

    return finder


def _scale(lines: list[str], i: int) -> str | None:
    m = _SCALE.search(lines[i])
    if not m:
        return None
    rest = m.group("v")
    if sale := re.search(rf"일반분양\s*{_COUNT}", rest):
        return f"{sale.group(1)}세대"
    counts = re.findall(_COUNT, rest)
    return f"{counts[-1]}세대" if counts else None


def _contract(lines: list[str], i: int) -> str | None:
    m = _CONTRACT.search(lines[i])
    if not m:
        return None
    start = m.group("s").rstrip(".")
    year = m.group("y") or re.match(r"\d{4}", start).group()
    return f"{start}. ~ {year}.{m.group('m')}.{m.group('d')}."


def _company_cells(lines: list[str], i: int) -> list[str]:
    """사업주체·시행 머리글 바로 아래 상호 줄의 칸들. 감리 표처럼 머리글이 다르면 빈 목록."""
    m = _COMPANY_ROW.match(lines[i])
    if not m:
        return []
    above = [ln for ln in lines[max(0, i - _HEADER_LOOKBACK) : i] if ln.strip()]
    if not any(_OWNER_HEADER.search(ln) for ln in above):
        return []
    row = re.sub(r"주\(\s*\)", "(주)", m.group("v"))  # ㈜가 `주(   )`로 풀려 나오는 PDF 텍스트
    return re.split(r"\s{2,}", row.strip())


def _owner(lines: list[str], i: int) -> str | None:
    cells = _company_cells(lines, i)
    return cells[0] if cells else None


def _builders(lines: list[str], i: int) -> str | None:
    return ", ".join(_company_cells(lines, i)[1:]) or None


def _owner_label(lines: list[str], i: int) -> str | None:
    m = _OWNER_LABEL.match(lines[i])
    return re.split(r"\s{2,}", m.group("v").strip())[0] if m else None


# 앞 파인더가 못 찾을 때만 다음 파인더를 쓴다
_FINDERS: dict[str, tuple[Finder, ...]] = {
    "공급위치": (_labelled(_LOCATION),),
    "공급규모": (_scale,),
    "모집공고일": (_labelled(_NOTICE_DATE),),
    "당첨자 발표일": (_labelled(_WINNER_DATE),),
    "계약일": (_contract,),
    "시행사": (_owner, _owner_label),
    "시공사": (_builders,),
    "입주예정월": (_labelled(_MOVE_IN),),
}


def regex_extract(pages: list[str]) -> dict[str, Extraction]:
    """pages(쪽마다 텍스트)에서 FIELDS 8개를 뽑는다. 못 찾은 필드는 EMPTY."""
    return {
        f: next((x for fn in _FINDERS[f] if (x := _find(pages, fn)) != EMPTY), EMPTY)
        for f in FIELDS
    }
