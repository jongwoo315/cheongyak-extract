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
DEFAULT_RULE = "C"  # 리포트 본 표와 extract()의 기본. reports/extract-tune.md에서 고른 안
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
    "공급위치": "'■ 공급위치' 줄의 소재지 전체(지번 주소, 단지·블록 이름). 괄호·기호도 글자 그대로",
    "공급규모": (
        "'■ 공급규모' 줄에서 이번에 분양하는 세대수 하나. "
        "'총 N세대 중 일반분양 M세대'면 M, '총 N세대'만 있으면 N. "
        "사전당첨자 취소분·특별공급 세부·동별 세대수는 고르지 않는다"
    ),
    "모집공고일": "입주자모집공고를 낸 날 하나(년.월.일). 접수·발표 일정의 날짜가 아니다",
    "당첨자 발표일": "당첨자 발표일 하나(년.월.일). 발표 방법·누리집 주소는 제외",
    "계약일": (
        "정당 계약 기간. 시작일~종료일 두 날짜 모두. "
        "끝 날짜에 연도가 없으면(월.일만 있으면) 시작 날짜의 연도를 붙여 쓴다"
        "(예: 원문이 '2030.05.07.(화) ~ 05.09.(목)'이면 "
        "value는 '2030.05.07.(화) ~ 2030.05.09.(목)'). "
        "예비입주자 등 다른 계약 일정이 아니다"
    ),
    "시행사": (
        "'사업주체 및 시공회사' 같은 표의 사업주체 칸 상호 하나. "
        "머리글이 시행수탁자(시행수탁사)와 시행위탁자(시행위탁사)로 나뉘어 있으면 "
        "시행수탁자 칸의 상호다('사업주체(시행수탁자)'도 시행수탁자 칸이다). "
        "머리글이 사업주체1·사업주체2면 사업주체1 칸의 상호다. "
        "머리글이 사업주체 하나뿐이면 그 칸의 상호이고, "
        "같은 공고에 신탁사가 따로 나와도 바꾸지 않는다. "
        "머리글 칸 순서와 상호 순서는 같다. 머리글에서 해당 칸이 몇 번째인지 센 뒤 "
        "상호 줄의 같은 번째 상호를 쓴다: 머리글이 '시행위탁자, 시행수탁자, 시공자'이고 "
        "상호가 'A, B, C'면 B, 머리글이 '시행수탁자, 시행위탁자, 시공사'이고 "
        "상호가 'A, B, C'면 A다. "
        "시공사·자금관리자·분양대금 납부계좌의 예금주·보증기관·분양대행사는 시행사가 아니다. "
        "상호는 하나다. 여러 상호를 잇지 않는다. 시행위탁자의 상호는 쓰지 않는다. "
        "상호 뒤에 붙은 사업명 같은 괄호 설명은 넣지 않는다"
    ),
    "시공사": (
        "사업주체 표의 시공사(시공자·시공업체) 칸 상호. 여럿이면 모두 ', '로 잇는다. "
        "시공사 머리글 뒤에 이름 없는 칸(Col4 등)이 이어지면 그 칸의 상호도 시공사다. "
        "머리글이 '사업주체, 시공사'이고 상호가 여러 개면 맨 앞 상호가 사업주체이고 "
        "나머지는 모두 시공사다. 사업주체와 시공사가 같은 회사면 둘 다 그 회사를 쓴다. "
        "사업자번호·법인번호는 넣지 않는다. "
        "사업주체·시행위탁자·분양대행사 칸의 회사는 넣지 않는다"
    ),
    "입주예정월": (
        "입주 예정 시기. 년·월까지만(일은 쓰지 않는다). "
        "연도가 두 자리('27)이면 네 자리(2027)로 쓴다"
    ),
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
  표에서 한 줄에 칸이 여럿 늘어서 있으면 value가 있는 줄 하나를 줄 그대로 복사한다.
  원문에 없는 '■'·'•' 같은 기호를 앞에 붙이지 않는다.
  같은 문구가 여러 쪽에 있을 수 있으니 page는 복사한 줄이 실제로 들어 있는 <page n>으로 적는다.
- value는 evidence 안의 글자를 쓴다. 글자·괄호·기호를 빼거나 고치지 않는다.
  필드 정의가 시키는 연도를 보충하고 회사를 쉼표로 잇는 것만 허용한다.
  필드 정의에 맞게 필요한 부분만 고른다.
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


def extract(pages: list[str], ask: Ask, rule: str = DEFAULT_RULE) -> Extracted:
    """LLM을 한 번 불러 8개 필드를 받고, rule안으로 근거를 못 찾는 칸을 비운다."""
    if rule not in RULES:
        raise ValueError(f"값을 남기는 조건은 {RULES} 중 하나다: {rule!r}")
    return extract_rules(pages, ask)[rule]
