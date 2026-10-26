"""비교 직전에 정답과 추출값을 같은 꼴로 맞춘다. 종류별 규칙은 설계 문서 §설계 결정."""

import re
from collections.abc import Callable

from cheongyak_extract.extract import KIND

_DATE = re.compile(r"(\d{4})\s*[-.]\s*(\d{1,2})\s*[-.]\s*(\d{1,2})")
_MONTH = re.compile(r"(\d{4})\s*(?:[-.]|년)\s*(\d{1,2})")


def _date(v: str) -> str | None:
    if m := _DATE.search(v):
        return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
    return None


def _period(v: str) -> str | None:
    found = _DATE.findall(v)
    if len(found) != 2:  # 시작만 있거나 셋 이상이면 기간으로 읽지 않는다
        return None
    return "~".join(f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in found)


def _month(v: str) -> str | None:
    if m := _MONTH.search(v):
        return f"{m[1]}-{int(m[2]):02d}"
    return None


KINDS: dict[str, Callable[[str], str | None]] = {
    "날짜": _date,
    "기간": _period,
    "월": _month,
}


def normalize(field: str, value: str | None) -> str | None:
    """비교용 정규형. 빈 값은 None, 못 읽거나 종류가 없으면 원본 `strip()`."""
    v = (value or "").strip()
    if not v:
        return None
    fn = KINDS.get(KIND.get(field, ""))
    return (fn(v) if fn else None) or v
