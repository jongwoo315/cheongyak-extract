"""PDF에만 적힌 필드 3개: 필드 정의, 정규형, 수동 정답(labels/pdf-only-50.json) 검사, 점수.

필드의 뜻과 정규형은 docs/plans/152-1031-design-pdf-only-fields.md §필드 3개의 뜻.
"""

import random
import re
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import FieldSet, _blank, _squash, grounded
from cheongyak_extract.pdf_text import pages as pdf_pages
from cheongyak_extract.raw_check import scan

RESALE, RESIDENT, INCOME = PDF_FIELDS = ("전매제한 기간", "거주지 우선 비율", "신혼부부 소득 기준")

NOTICES, TUNE = 50, 20  # 공고 50건 중 앞 20건이 다듬는 공고, 나머지 30건이 재는 공고
SEED = 152
CELLS = NOTICES * len(PDF_FIELDS)

PDF_HEAD = """\
아래는 주택 입주자모집공고문 PDF 전체 텍스트다. 쪽마다 <page n> ... </page>로 감쌌다.
다음 3개 필드를 찾아 JSON으로 답한다.
필드마다 value(값), evidence(근거), page(근거가 있는 쪽 번호)를 쓴다.

- evidence는 value가 적힌 부분을 공고문 텍스트에서 글자 그대로 복사한 구절이다.
  줄바꿈과 띄어쓰기도 원문 그대로 둔다. 중간 줄을 건너뛰거나 여러 줄을 합쳐 쓰지 않는다.
  값이 여러 줄에 걸쳐 있으면 이어진 줄을 그대로 복사한다.
- value에 쓰는 숫자는 모두 evidence 안에 있어야 한다.
- value의 꼴은 아래 필드 정의가 정한다. 정의가 시키는 단위·괄호·구분 기호는 원문에 없어도 쓴다.
- page는 복사한 줄이 실제로 들어 있는 <page n>의 n이다.
- 공고문에 없거나 확실하지 않으면 value, evidence, page를 모두 null로 둔다. 추측하지 않는다.

필드:
"""

_FIELD_HELP = {
    RESALE: (
        "일반공급 당첨자의 전매제한 기간 하나. 1쪽 요약 표에 '전매제한' 칸이 있으면 그 값이다. "
        "없으면 전매행위 제한 안내 문장의 기간이다. '6개월', '3년'처럼 단위까지 쓴다. "
        "제한이 없다고 적혀 있으면 '없음'. 주택형·공급 유형마다 기간이 다르면 "
        "서로 다른 기간을 짧은 것부터 ', '로 잇는다"
    ),
    RESIDENT: (
        "일반공급 물량을 거주 지역별로 나눈 비율. 우선순위가 높은 지역부터 "
        "'평택시 30% / 경기도 20% / 기타 50%'처럼 쓴다. "
        "비율 없이 해당지역 거주자 우선만 적혀 있으면 '해당지역 100%'. "
        "특별공급·기관추천의 거주 조건이 아니다"
    ),
    INCOME: (
        "신혼부부 특별공급에서 소득 조건이 가장 낮은 첫 단계(우선공급·1단계)의 "
        "도시근로자 월평균소득 대비 %와 맞벌이 %. '100% (맞벌이 120%)'처럼 쓴다. "
        "맞벌이 기준이 없으면 '130%'처럼 하나만 쓴다. 신혼부부 특별공급이 없으면 null"
    ),
}

PDF_FIELD_SET = FieldSet(PDF_FIELDS, _FIELD_HELP, PDF_HEAD)

_YEARS = re.compile(r"(\d+)\s*년")
_MONTHS = re.compile(r"(\d+)\s*개월")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _months(piece: str) -> int | None:
    if _squash(piece) == "없음":
        return 0
    years, months = _YEARS.findall(piece), _MONTHS.findall(piece)
    if not years and not months:
        return None
    return 12 * sum(map(int, years)) + sum(map(int, months))


def _plain(number: str) -> str:
    return number.rstrip("0").rstrip(".") if "." in number else number


def normal_form(field: str, value: str | None) -> str | None:
    """비교용 정규형. 못 읽으면 None. 꼴은 설계 §필드 3개의 뜻 표."""
    if field not in PDF_FIELDS:
        raise ValueError(f"세 필드가 아니다: {field!r}")
    if _blank(value):
        return None
    if field == RESALE:
        found = [_months(p) for p in value.split(",")]
        if any(m is None for m in found):
            return None
        return ",".join(str(m) for m in sorted(set(found)))
    percents = _PERCENT.findall(value)
    return "/".join(_plain(p) for p in percents) if percents else None


def _has_number(number: str, text: str) -> bool:
    """text 안에 number가 다른 숫자의 일부가 아닌 채로 있다(130은 1130 안에 있지 않다)."""
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)", text) is not None


def number_problems(field: str, value: str, quote: str) -> list[str]:
    """value에 쓴 숫자 중 quote에 없는 것. 단위를 바꾼 값(3년 -> 36)도 바꾸기 전 숫자로 본다.

    예외 둘: `해당지역 100%`는 비율이 안 적힌 경우의 약속이라 quote에 100이 없어도 된다.
    `없음`은 숫자가 없으므로 quote에 「없」이 있는지 본다.
    """
    flat, text = _squash(value), _squash(quote)
    if field == RESIDENT and flat == "해당지역100%":
        return []
    if flat == "없음":
        return [] if "없" in text else ["없"]
    return [n for n in dict.fromkeys(_NUMBER.findall(value)) if not _has_number(n, text)]


class Split(NamedTuple):
    tune: list[str]
    test: list[str]


def eligible_pbnos(raw_dir: Path) -> list[str]:
    """수집된 공고 중 PDF 텍스트가 있는 것. 텍스트 없는 스캔 PDF(2026000235)는 뺀다."""
    return [
        p
        for p in scan(raw_dir).collected
        if any(t.strip() for t in pdf_pages(raw_dir / p / "notice.pdf"))
    ]


def pick(pbnos: list[str], n: int = NOTICES, tune: int = TUNE) -> Split:
    """정렬한 목록에서 `Random(152).sample`로 n건. 앞 tune건이 다듬는 공고, 나머지가 재는 공고."""
    sample = random.Random(SEED).sample(sorted(pbnos), n)
    return Split(sample[:tune], sample[tune:])


# 정답 검사에 걸린 이유
QUOTE_NOT_ON_PAGE = "quote가 그 쪽 텍스트에 없음"
NUMBER_NOT_IN_QUOTE = "숫자가 quote에 없음"
NO_NORMAL_FORM = "값의 정규형을 만들 수 없음"

_KEYS = {"value", "quote", "page", "note"}


class LabelCell(NamedTuple):
    pbno: str
    field: str
    value: str | None
    quote: str | None
    page: int | None
    note: str | None
    problems: tuple[str, ...]  # 값이 있는 칸이 정답 검사 둘에 걸린 이유. 없으면 빈 튜플


def _check_cell(where: str, raw: object) -> dict:
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ValueError(f"{where}: 칸은 {sorted(_KEYS)} 키를 모두 가진 객체여야 한다")
    if not all(raw[k] is None or isinstance(raw[k], str) for k in ("value", "quote", "note")):
        raise ValueError(f"{where}: value·quote·note는 문자열이거나 null이어야 한다")
    page = raw["page"]
    if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
        raise ValueError(f"{where}: page는 1 이상의 정수이거나 null이어야 한다")
    if any(raw[k] is not None and not raw[k].strip() for k in ("value", "quote")):
        raise ValueError(f"{where}: 값이 없으면 빈 문자열이 아니라 null로 적는다")
    has_value = raw["value"] is not None
    if has_value != (raw["quote"] is not None) or has_value != (page is not None):
        raise ValueError(f"{where}: value·quote·page는 모두 있거나 모두 null이어야 한다")
    if not has_value and _blank(raw["note"]):
        raise ValueError(f"{where}: 값이 null인 칸은 note에 찾아본 쪽을 적는다")
    return raw


def _problems(field: str, raw: dict, texts: list[str]) -> tuple[str, ...]:
    if raw["value"] is None:
        return ()
    found: list[str] = []
    page = raw["page"]
    if not (1 <= page <= len(texts) and grounded(raw["quote"], texts[page - 1])):
        found.append(QUOTE_NOT_ON_PAGE)
    if normal_form(field, raw["value"]) is None:
        found.append(NO_NORMAL_FORM)
    if missing := number_problems(field, raw["value"], raw["quote"]):
        found.append(f"{NUMBER_NOT_IN_QUOTE}: {', '.join(missing)}")
    return tuple(found)


def check_labels(
    data: object, split: Split, texts: dict[str, list[str]], expected: int = CELLS
) -> list[LabelCell]:
    """정답 파일 구조를 확인하고 칸 목록을 만든다. 구조가 틀리면 ValueError.

    값이 있는 칸이 검사 둘(quote가 그 쪽에 있다, 숫자가 quote에 있다)에 걸리면
    에러가 아니라 칸의 problems에 적는다. split은 코드가 다시 뽑은 50건 목록이다.
    """
    if not isinstance(data, dict) or set(data) != {"tune", "test", "cells"}:
        raise ValueError("정답 파일은 tune·test·cells 키를 가진 객체여야 한다")
    if data["tune"] != split.tune or data["test"] != split.test:
        raise ValueError("tune·test가 다시 뽑은 목록과 다르다")
    cells = data["cells"]
    if not isinstance(cells, dict):
        raise ValueError("cells는 공고번호를 키로 하는 객체여야 한다")
    out: list[LabelCell] = []
    for pbno in [*split.tune, *split.test]:
        got = cells.get(pbno)
        if got is None:
            raise ValueError(f"{pbno}: 정답에 이 공고가 없다")
        if not isinstance(got, dict):
            raise ValueError(f"{pbno}: 공고의 정답은 필드를 키로 하는 객체여야 한다")
        if extra := set(got) - set(PDF_FIELDS):
            raise ValueError(f"{pbno}: 정답에 필드가 더 있다: {sorted(extra)}")
        for f in PDF_FIELDS:
            if f not in got:
                raise ValueError(f"{pbno}: 정답에 필드 {f}이(가) 없다")
            raw = _check_cell(f"{pbno} {f}", got[f])
            out.append(
                LabelCell(
                    pbno,
                    f,
                    raw["value"],
                    raw["quote"],
                    raw["page"],
                    raw["note"],
                    _problems(f, raw, texts[pbno]),
                )
            )
    if extra := set(cells) - {*split.tune, *split.test}:
        raise ValueError(f"정답에 50건 밖의 공고가 있다: {sorted(extra)}")
    if len(out) != expected:
        raise ValueError(f"칸이 {len(out)}개다. {expected}개여야 한다")
    return out


# 칸 상태 다섯. 정답에 값이 있는 칸은 앞 셋, 정답이 null인 칸은 뒤 둘
RIGHT, BLANK, OTHER = "맞음", "비움", "다른 값으로 채움"
NULL_BLANK, NULL_FILLED = "null에 비움", "null에 값을 채움"
STATES = (RIGHT, BLANK, OTHER, NULL_BLANK, NULL_FILLED)


def cell_state(field: str, truth: str | None, got: str | None) -> str:
    if truth is None:
        return NULL_BLANK if _blank(got) else NULL_FILLED
    if _blank(got):
        return BLANK
    want = normal_form(field, truth)
    return RIGHT if want is not None and normal_form(field, got) == want else OTHER
