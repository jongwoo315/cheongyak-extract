"""비교 직전에 정답과 추출값을 같은 꼴로 맞춘다.

종류 목록은 설계 문서 §설계 결정, 세부 규칙은 아래 함수와 tests/test_normalize.py.
"""

import re
from collections.abc import Callable

from cheongyak_extract.extract import KIND

_DATE = re.compile(r"(?<!\d)(\d{4})\s*[-.]\s*(\d{1,2})\s*[-.]\s*(\d{1,2})(?!\d)")
# 끝 연도를 생략한 범위(2026.11.10~11.11)는 날짜 하나로 읽지 않는다
_OPEN_DATE_RANGE = re.compile(r"~\s*\d{1,2}\s*[.-]\s*\d{1,2}")
# 끝 연도를 생략한 월 범위(2029년 8월~9월)는 월 하나로 읽지 않는다
_OPEN_MONTH_RANGE = re.compile(r"~\s*\d{1,2}(?!\d)")
# 일까지 적힌 날짜(2029.08.15)는 월로 읽지 않는다
_MONTH = re.compile(r"(?<!\d)(\d{4})\s*(?:[-.]|년)\s*(\d{1,2})(?!\d)(?!\s*[-.]\s*\d)")


def _date(v: str) -> str | None:
    found = _DATE.findall(v)
    if len(found) != 1 or _OPEN_DATE_RANGE.search(v):  # 신문명·URL은 떼도 되지만 둘째 날짜는 값이다
        return None
    y, m, d = found[0]
    return f"{y}-{int(m):02d}-{int(d):02d}"


def _period(v: str) -> str | None:
    found = _DATE.findall(v)
    if len(found) != 2:  # 시작만 있거나 셋 이상이면 기간으로 읽지 않는다
        return None
    return "~".join(f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in found)


def _month(v: str) -> str | None:
    found = _MONTH.findall(v)
    # 범위·일까지 적힌 날짜
    if len(found) != 1 or re.search(r"월\s*\d{1,2}\s*일", v) or _OPEN_MONTH_RANGE.search(v):
        return None
    y, m = found[0]
    return f"{y}-{int(m):02d}"


_LEGAL_FORM = re.compile(r"\(주\)|㈜|주식회사")
_COUNT = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})+|\d+)\s*세대")


def _company(v: str) -> str | None:
    # 회사가 여럿이면 쉼표나 줄바꿈으로 나뉜다. 순서만 다른 것은 같게 본다
    names = (re.sub(r"\s+", "", _LEGAL_FORM.sub("", n)) for n in re.split(r"[,\n]", v))
    return ",".join(sorted(n for n in names if n)) or None


def _count(v: str) -> str | None:
    found = {n.replace(",", "") for n in _COUNT.findall(v)}
    return found.pop() if len(found) == 1 else None  # 세대수가 여럿 적힌 문장은 고르지 않는다


def _address(v: str) -> str | None:
    return re.sub(r"\s*([()])\s*", r"\1", " ".join(v.split()))


KINDS: dict[str, Callable[[str], str | None]] = {
    "날짜": _date,
    "기간": _period,
    "월": _month,
    "회사명": _company,
    "세대수": _count,
    "주소": _address,
}


def normalize(field: str, value: str | None) -> str | None:
    """비교용 정규형. 빈 값은 None, 못 읽거나 종류가 없으면 원본 `strip()`."""
    v = (value or "").strip()
    if not v:
        return None
    fn = KINDS.get(KIND.get(field, ""))
    return (fn(v) if fn else None) or v
