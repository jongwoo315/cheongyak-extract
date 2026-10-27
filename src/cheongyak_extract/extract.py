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
NOT_IN_PAGE = "근거 문장이 그 쪽에 없음"  # 규칙 4 (A안·B안)
VALUE_NOT_IN_EVIDENCE = "값이 근거 문장 안에 없음"  # B안의 추가 조건
NEITHER_IN_PAGE = "근거 문장도 값도 그 쪽에 없음"  # 규칙 4 (C안)
NO_KEY = "응답에 이 필드 키가 없음"  # 규칙 5
BAD_JSON = "응답이 JSON 객체가 아님"
BAD_CELL = "응답 칸의 모양이 다름"

# 규칙 4를 대신하는 값을 남기는 조건(설계 §값을 남기는 조건). 같은 응답에 셋을 모두 걸어 비교한다.
#   A: 근거 문장이 그 쪽에 있다.  B: A + 값이 근거 문장 안에 있다.
#   C: 근거 문장이 그 쪽에 있거나, 값이 그 쪽에 있다.
RULES = ("A", "B", "C")
# 이 조건으로 값을 비운 이유. 구조 규칙(1·2·3·5)이나 응답 모양 오류와 구분한다
RULE_BLANKS = (NOT_IN_PAGE, VALUE_NOT_IN_EVIDENCE, NEITHER_IN_PAGE)

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

- evidence는 value가 적힌 부분을 공고문 텍스트에서 글자 그대로 복사한 짧은 구절이다.
  한 줄이면 충분하고 길어도 연속된 두 줄이다. 줄바꿈과 띄어쓰기도 원문 그대로 둔다.
- 중간 줄을 건너뛰거나 여러 줄을 합쳐 쓰지 않는다. 길면 value 앞뒤 한 구절만 복사한다.
- value가 되는 숫자·날짜·이름이 evidence 안에 들어 있어야 한다.
  `구분`, `사업주체` 같은 표 머리글만 복사하지 않는다.
  값이 머리글과 떨어진 줄에 있으면 값이 있는 줄을 복사한다.
  날짜나 숫자만 복사하지 말고, 그 값이 무엇인지 알려 주는 라벨이 같은 줄에 있으면 함께 복사한다.
  같은 문구가 여러 쪽에 있을 수 있으니 page는 복사한 줄이 실제로 들어 있는 <page n>으로 적는다.
- 원문에 없는 문장을 만들어 쓰지 않는다. 복사할 수 없으면 value, evidence, page를 null로 둔다.
- page는 그 evidence가 들어 있는 <page n>의 n이다.
- 청약홈 공고 상세 표에 들어갈 값 하나를 value로 고른다.
- 공고문에 없거나 확실하지 않으면 value, evidence, page를 모두 null로 둔다. 추측하지 않는다.

필드:
"""


def build_prompt(pages: list[str]) -> str:
    helps = "".join(f"- {f}: {_FIELD_HELP[f]}\n" for f in FIELDS)
    body = "".join(f"<page {i}>\n{t}\n</page>\n" for i, t in enumerate(pages, start=1))
    return f"{PROMPT_HEAD}{helps}\n공고문:\n{body}"


def _text(v: object) -> bool:
    return v is None or isinstance(v, str)


def _contains(text: str, part: str) -> bool:
    return _squash(part) in _squash(text)


def _check(raw: object, pages: list[str], rule: str) -> tuple[Extraction, str | None]:
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
    text = pages[page - 1]
    if rule == "C":
        if not (grounded(evidence, text) or _contains(text, value)):
            return EMPTY, NEITHER_IN_PAGE
    elif not grounded(evidence, text):
        return EMPTY, NOT_IN_PAGE
    elif rule == "B" and not _contains(evidence, value):
        return EMPTY, VALUE_NOT_IN_EVIDENCE
    return Extraction(value.strip(), evidence, page), None


def extract_rules(pages: list[str], ask: Ask) -> dict[str, Extracted]:
    """LLM을 한 번 불러 8개 필드를 받고, 같은 응답에 A·B·C안을 각각 걸어 결과를 돌려준다."""
    raw = ask(build_prompt(pages))  # 호출 쪽 예외를 응답 모양 오류로 삼키지 않는다
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    out = {}
    for rule in RULES:
        if not isinstance(data, dict):
            out[rule] = Extracted({f: EMPTY for f in FIELDS}, {f: BAD_JSON for f in FIELDS})
            continue
        fields: dict[str, Extraction] = {}
        blanked: dict[str, str] = {}
        for f in FIELDS:
            fields[f], why = _check(data[f], pages, rule) if f in data else (EMPTY, NO_KEY)
            if why:
                blanked[f] = why
        out[rule] = Extracted(fields, blanked)
    return out


def extract(pages: list[str], ask: Ask, rule: str = "A") -> Extracted:
    """LLM을 한 번 불러 8개 필드를 받고, rule안으로 근거를 못 찾는 칸을 비운다."""
    if rule not in RULES:
        raise ValueError(f"값을 남기는 조건은 {RULES} 중 하나다: {rule!r}")
    return extract_rules(pages, ask)[rule]
