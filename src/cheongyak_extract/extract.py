"""공고문 쪽별 텍스트에서 필드를 뽑는다."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple


def _blank(s: str | None) -> bool:
    return not (s or "").strip()


@dataclass(frozen=True)
class Extraction:
    value: str | None
    evidence: str | None
    page: int | None  # 1부터

    def __post_init__(self) -> None:
        if _blank(self.value):
            if not _blank(self.evidence) or self.page is not None:
                raise ValueError("값이 없는데 근거나 쪽이 있다")
        elif _blank(self.evidence) or self.page is None:
            raise ValueError("값이 있는데 근거나 쪽이 없다")
        elif self.page < 1:
            raise ValueError(f"쪽은 1부터다: {self.page}")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def grounded(evidence: str | None, text: str) -> bool:
    """근거 문장이 text 안에 있다. PDF는 줄이 끊기므로 양쪽 공백을 모두 지우고 비교한다."""
    if _blank(evidence):
        return False
    return _squash(evidence) in _squash(text)


# 상세 HTML 표에서 한 칸 값으로 읽히는 필드. 정답(truth.py)과 같은 키를 쓴다.
FIELDS = (
    "공급위치",
    "공급규모",
    "모집공고일",
    "당첨자 발표일",
    "계약일",
    "시행사",
    "시공사",
    "입주예정월",
)

# 필드마다 정규화 종류를 하나 붙인다. 종류별 함수는 normalize.py에 있다.
KIND = {
    "공급위치": "주소",
    "공급규모": "세대수",
    "모집공고일": "날짜",
    "당첨자 발표일": "날짜",
    "계약일": "기간",
    "시행사": "회사명",
    "시공사": "회사명",
    "입주예정월": "월",
}


# 값을 비운 이유. 설계 문서 §코드가 거르는 규칙 5개 + 응답 모양 오류
NO_VALUE = "값이 비어 있음"  # 규칙 1
NO_EVIDENCE = "근거 문장이나 쪽 번호가 없음"  # 규칙 2
BAD_PAGE = "쪽 번호가 범위 밖"  # 규칙 3
NOT_IN_PAGE = "근거 문장이 그 쪽에 없음"  # 규칙 4
NO_KEY = "응답에 이 필드 키가 없음"  # 규칙 5
BAD_JSON = "응답이 JSON 객체가 아님"
BAD_CELL = "응답 칸의 모양이 다름"

EMPTY = Extraction(None, None, None)

Ask = Callable[[str], str]  # 프롬프트 -> 응답 JSON 문자열


class Usage(NamedTuple):
    input_tokens: int
    output_tokens: int


class Extracted(NamedTuple):
    fields: dict[str, Extraction]
    blanked: dict[str, str]  # 비운 필드 -> 이유(LLM이 비운 칸도 들어 있다)


_NULLABLE = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_CELL = {
    "type": "object",
    "properties": {
        "value": _NULLABLE,
        "evidence": _NULLABLE,
        "page": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["value", "evidence", "page"],
    "additionalProperties": False,
}
# structured outputs(strict)용 응답 모양. 8개 키 전부 required
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {f: _CELL for f in FIELDS},
    "required": list(FIELDS),
    "additionalProperties": False,
}

_FIELD_HELP = {
    "공급위치": "공급(분양)하는 단지의 소재지. 지번 주소와 단지·블록 이름을 공고문에 적힌 대로",
    "공급규모": "일반분양 세대수 하나. 특별공급·기관추천·총 세대수·동별 세대수는 고르지 않는다",
    "모집공고일": "입주자모집공고를 낸 날 하나(년.월.일)",
    "당첨자 발표일": "당첨자 발표일 하나(년.월.일). 발표 방법·누리집 주소는 제외",
    "계약일": "정당 계약 기간. 시작일~종료일 두 날짜 모두",
    "시행사": "사업주체(시행사) 이름. 시공사와 다른 회사일 수 있다",
    "시공사": "시공사 이름. 여럿이면 모두",
    "입주예정월": "입주 예정 시기. 년·월까지만(일은 쓰지 않는다)",
}

PROMPT_HEAD = """\
아래는 주택 입주자모집공고문 PDF 전체 텍스트다. 쪽마다 <page n> ... </page>로 감쌌다.
다음 8개 필드를 찾아 JSON으로 답한다.
필드마다 value(값), evidence(근거), page(근거가 있는 쪽 번호)를 쓴다.

- evidence는 공고문 텍스트에서 그대로 복사한 문장이나 구절이다. 고쳐 쓰거나 요약하지 않는다.
- page는 그 evidence가 들어 있는 <page n>의 n이다.
- value는 evidence에서 고른 값이다. 청약홈 공고 상세 표에 들어갈 값 하나를 기준으로 고른다.
- 공고문에 없거나 확실하지 않으면 value, evidence, page를 모두 null로 둔다. 추측하지 않는다.

필드:
"""


def build_prompt(pages: list[str]) -> str:
    helps = "".join(f"- {f}: {_FIELD_HELP[f]}\n" for f in FIELDS)
    body = "".join(f"<page {i}>\n{t}\n</page>\n" for i, t in enumerate(pages, start=1))
    return f"{PROMPT_HEAD}{helps}\n공고문:\n{body}"


def _text(v: object) -> bool:
    return v is None or isinstance(v, str)


def _check(raw: object, pages: list[str]) -> tuple[Extraction, str | None]:
    """응답 칸 하나를 거른다. (결과, 비운 이유)."""
    if not isinstance(raw, dict) or not _text(raw.get("value")) or not _text(raw.get("evidence")):
        return EMPTY, BAD_CELL
    value, evidence, page = raw.get("value"), raw.get("evidence"), raw.get("page")
    if _blank(value):
        return EMPTY, NO_VALUE
    if _blank(evidence) or not isinstance(page, int) or isinstance(page, bool):
        return EMPTY, NO_EVIDENCE
    if not 1 <= page <= len(pages):
        return EMPTY, BAD_PAGE
    if not grounded(evidence, pages[page - 1]):
        return EMPTY, NOT_IN_PAGE
    return Extraction(value.strip(), evidence, page), None


def extract(pages: list[str], ask: Ask) -> Extracted:
    """LLM을 한 번 불러 8개 필드를 받고, 근거를 못 찾는 칸은 비운다."""
    try:
        data = json.loads(ask(build_prompt(pages)))
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return Extracted({f: EMPTY for f in FIELDS}, {f: BAD_JSON for f in FIELDS})
    fields: dict[str, Extraction] = {}
    blanked: dict[str, str] = {}
    for f in FIELDS:
        fields[f], why = _check(data[f], pages) if f in data else (EMPTY, NO_KEY)
        if why:
            blanked[f] = why
    return Extracted(fields, blanked)
