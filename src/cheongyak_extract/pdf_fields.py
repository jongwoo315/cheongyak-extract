"""PDF에만 적힌 필드 3개: 필드 정의, 정규형, 수동 정답(labels/pdf-only-50.json) 검사, 점수.

필드의 뜻과 정규형은 docs/plans/152-1031-design-pdf-only-fields.md §필드 3개의 뜻.
"""

import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import (
    BAD_CELL,
    BAD_JSON,
    NO_KEY,
    Ask,
    Extraction,
    FieldSet,
    _blank,
    _squash,
    extract,
    grounded,
)
from cheongyak_extract.llm import BadResponse, ContextExceeded
from cheongyak_extract.pdf_text import has_text
from cheongyak_extract.pdf_text import pages as pdf_pages
from cheongyak_extract.raw_check import scan
from cheongyak_extract.report import _table

RESALE, RESIDENT, INCOME = PDF_FIELDS = ("전매제한 기간", "거주지 우선 비율", "신혼부부 소득 기준")

NOTICES, TUNE = 50, 20  # 공고 50건 중 앞 20건이 다듬는 공고, 나머지 30건이 재는 공고
SEED = 152
CELLS = NOTICES * len(PDF_FIELDS)

_RULES_OF_EVIDENCE = """\
- evidence는 value가 적힌 부분을 공고문 텍스트에서 글자 그대로 복사한 구절이다.
  줄바꿈과 띄어쓰기도 원문 그대로 둔다. 중간 줄을 건너뛰거나 여러 줄을 합쳐 쓰지 않는다.
  값이 여러 줄에 걸쳐 있으면 이어진 줄을 그대로 복사한다.
- value에 쓰는 숫자는 모두 evidence 안에 있어야 한다.
- value의 꼴은 아래 필드 정의가 정한다. 정의가 시키는 단위·괄호·구분 기호는 원문에 없어도 쓴다.
- page는 복사한 줄이 실제로 들어 있는 <page n>의 n이다.
- 공고문에 없거나 확실하지 않으면 value, evidence, page를 모두 null로 둔다. 추측하지 않는다.

필드:
"""


def _head(what: str, count: int) -> str:
    return (
        f"{what} 쪽마다 <page n> ... </page>로 감쌌다.\n"
        f"다음 {count}개 필드를 찾아 JSON으로 답한다.\n"
        "필드마다 value(값), evidence(근거), page(근거가 있는 쪽 번호)를 쓴다.\n\n"
        f"{_RULES_OF_EVIDENCE}"
    )


_WHOLE = "아래는 주택 입주자모집공고문 PDF 전체 텍스트다."
_BLOCK = "아래는 주택 입주자모집공고문 PDF에서 일반공급 ①지역 묶음만 잘라 낸 텍스트다."

# 거주지 값의 꼴(설계 §값의 꼴과 계산). 묶음으로 묻는 것과 전체 텍스트로 묻는 것이 같이 쓴다
_RESIDENT_FORM = (
    "지역마다 %가 적혀 있으면 우선순위가 높은 지역부터 "
    "'평택시 30% / 경기도 20% / 기타 50%'처럼 쓴다. 0%인 지역은 쓰지 않는다. "
    "쓴 %를 모두 더하면 100이어야 한다. "
    "% 없이 해당지역 거주자 우선만 적혀 있거나 한 지역이 100%이고 나머지가 0%면 "
    "value는 정확히 '해당지역 100%'로 쓰고, evidence는 해당지역 거주자 우선을 적은 문장을 복사한다"
)

_FIELD_HELP = {
    RESALE: (
        "일반공급 당첨자의 전매제한 기간 하나. 1쪽 요약표에 '전매제한' 칸이 있으면 그 값이다. "
        "없으면 전매행위 제한 안내 문장의 기간이다. '6개월', '3년'처럼 단위까지 쓴다. "
        "제한이 없다고 적혀 있으면 '없음'. 주택형·공급 유형마다 기간이 다르면 "
        "서로 다른 기간을 짧은 것부터 ', '로 잇는다. "
        "기간(년·개월)이나 '없음'이 아닌 값(임대의무기간, 분양전환 시기 등)이면 null"
    ),
    INCOME: (
        "'신혼부부 특별공급' 제목의 절 안에 있는 소득 기준에서 첫 단계(소득 %가 가장 낮은 "
        "우선공급 1단계)의 '월평균소득 N% 이하'와 맞벌이(부부 모두 소득이 있는 경우) %. "
        "생애최초·신생아·다자녀·노부모부양 특별공급의 소득 기준이 아니다. "
        "'100% (맞벌이 120%)'처럼 쓴다. 맞벌이 기준이 없으면 '130%'처럼 하나만 쓴다. "
        "evidence는 맞벌이 %가 적힌 한 줄만 복사한다. 그 줄에 두 % 숫자가 모두 있다"
        "(예: '(부부 모두 소득이 있는 경우 120% 이하, 단 부부 중 1인의 소득은 100% 이하여야 함)'). "
        "다른 줄을 이어 붙이지 않는다. 신혼부부 특별공급이 없으면 null"
    ),
}

# 전매제한·신혼부부 소득 기준은 전체 텍스트로 한 번에 묻는다. 거주지는 따로 묻는다
TWO_FIELD_SET = FieldSet((RESALE, INCOME), _FIELD_HELP, _head(_WHOLE, 2))

# 거주지 ①: 일반공급 ①지역 묶음이 있으면 그 묶음만 준다
RESIDENT_BLOCK_SET = FieldSet(
    (RESIDENT,),
    {
        RESIDENT: (
            "이 텍스트의 일반공급 '① 지역' 줄 하나. 이 묶음이 일반공급의 것이므로 "
            "다른 곳을 찾지 않는다. " + _RESIDENT_FORM
        )
    },
    _head(_BLOCK, 1),
)

# 거주지 ②: 묶음이 없으면 전체 텍스트를 주고 설계 §고르는 규칙 2·3 순서로 읽게 한다
RESIDENT_FULL_SET = FieldSet(
    (RESIDENT,),
    {
        RESIDENT: (
            "일반공급 당첨자의 거주지(해당지역) 우선 비율 하나. "
            "아래 순서로 처음 걸리는 곳에서 읽는다. "
            "(1) 특별공급과 일반공급에 같이 적용된다고 적힌 지역우선 공급기준 표. "
            "(2) 일반공급 안내의 해당지역 거주자 우선 문장. "
            "특별공급 유형별(다자녀·노부모부양·신혼부부·생애최초 등) 절의 '① 지역' 줄에서는 "
            "읽지 않는다. " + _RESIDENT_FORM
        )
    },
    _head(_WHOLE, 1),
)

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
    if field == RESIDENT:  # 0%인 지역은 쓰지 않는 꼴이라 정규형에서 뺀다
        percents = [p for p in percents if float(p) != 0]
    return "/".join(_plain(p) for p in percents) if percents else None


def sum_is_not_100(value: str | None) -> bool:
    """거주지 값의 %를 모두 더하면 100이 아니다. %가 없으면 합을 말할 수 없으므로 False."""
    percents = _PERCENT.findall(value or "")
    return bool(percents) and abs(sum(map(float, percents)) - 100) > 1e-9


_ONE_REGION = re.compile(r"[^/%]*\S[^/%]*\d+(?:\.\d+)?\s*%")  # 「지역 이름 N%」 한 토막


def _resident_shape_ok(value: str) -> bool:
    """설계 §값의 꼴과 계산 표의 꼴이다: `해당지역 100%` 하나, 또는 `이름 N% / 이름 N% ...` 둘 이상.

    0%인 지역은 쓰지 않는다. `해당지역 100%`를 다른 토막과 섞지 않는다.
    한 지역 100%는 `해당지역 100%`로 쓴다.
    """
    if _squash(value) == "해당지역100%":
        return True
    parts = value.split("/")
    if len(parts) < 2 or any(not _ONE_REGION.fullmatch(p.strip()) for p in parts):
        return False
    return all(float(x) != 0 for x in _PERCENT.findall(value)) and not any(
        _squash(p) == "해당지역100%" for p in parts
    )


def _has_number(number: str, text: str) -> bool:
    """text 안에 number가 다른 숫자의 일부가 아닌 채로 있다(130은 1130 안에 있지 않다)."""
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\d|\.\d)", text) is not None


def number_problems(field: str, value: str, quote: str) -> list[str]:
    """value에 쓴 숫자 중 quote에 없는 것. 정규형으로 바꾸기 전, value에 적은 글자 그대로 본다.

    전매제한은 숫자와 단위(년·개월)를 짝으로 본다. 예외 둘: `해당지역 100%`는 비율이 안 적힌
    경우의 약속이라 quote에 100이 없어도 된다. `없음`은 숫자가 없으므로 quote에서 「전매」 뒤
    숫자 없이 가까이 「없」이 있는지 본다.
    """
    flat, text = _squash(value), _squash(quote)
    if field == RESIDENT and flat == "해당지역100%":
        return []
    if flat == "없음":
        return [] if re.search(r"전매\D{0,10}없", text) else ["없"]
    if field == RESALE:  # 숫자만 같고 단위가 다른 오타(3년 대 3개월)를 걸러낸다
        pairs = dict.fromkeys(f"{n}{u}" for n, u in re.findall(r"(\d+)\s*(년|개월)", value))
        return [x for x in pairs if not re.search(rf"(?<![\d.]){re.escape(x)}", text)]
    return [n for n in dict.fromkeys(_NUMBER.findall(value)) if not _has_number(n, text)]


class Block(NamedTuple):
    page: int  # 1부터
    text: str


_ORDER_LINE = re.compile(r"2\s*순위\s*:\s*①\s*지역")  # 일반공급 절에만 있다. 특별공급 절에는 없다
_AREA_MARK = re.compile(r"■\s*①\s*지역")
_BELOW = 3  # 「2순위」 줄 아래 이 줄 수 안에 「■ ①지역」 줄이 온다


def resident_block(pages: list[str]) -> Block | None:
    """일반공급 ①지역 묶음(설계 §고르는 규칙 1). 없으면 None.

    「2순위 : ①지역」 줄 아래 3줄 안의 「■ ①지역」 줄부터, 다음 「■」가 든 줄 앞까지다.
    """
    for n, page in enumerate(pages, start=1):
        lines = page.split("\n")
        for i, line in enumerate(lines):
            if not _ORDER_LINE.search(line):
                continue
            for j in range(i + 1, min(i + 1 + _BELOW, len(lines))):
                if not (mark := _AREA_MARK.search(lines[j])):
                    continue
                body = [lines[j][mark.start() :]]
                for rest in lines[j + 1 :]:
                    if "■" in rest:
                        break
                    body.append(rest)
                return Block(n, "\n".join(body).rstrip())
    return None


class Split(NamedTuple):
    tune: list[str]
    test: list[str]


def eligible_pbnos(raw_dir: Path) -> list[str]:
    """수집된 공고 중 PDF 텍스트가 있는 것. 텍스트 없는 스캔 PDF(2026000235)는 뺀다."""
    return [p for p in scan(raw_dir).collected if has_text(raw_dir / p / "notice.pdf")]


def pick(pbnos: list[str], n: int = NOTICES, tune: int = TUNE) -> Split:
    """정렬한 목록에서 `Random(152).sample`로 n건. 앞 tune건이 다듬는 공고, 나머지가 재는 공고."""
    sample = random.Random(SEED).sample(sorted(pbnos), n)
    return Split(sample[:tune], sample[tune:])


RESIDENT_SEED, RESIDENT_NOTICES = 1522, 30
RESIDENT_CELLS = RESIDENT_NOTICES  # 새 30건은 거주지 칸만 적는다


def pick_resident(pbnos: list[str], used: list[str], n: int = RESIDENT_NOTICES) -> Split:
    """used(기존 50건)를 뺀 목록을 정렬해 `Random(1522).sample`로 n건. 전부 재는 공고다."""
    rest = sorted(set(pbnos) - set(used))
    return Split([], random.Random(RESIDENT_SEED).sample(rest, n))


# 정답 검사에 걸린 이유
QUOTE_NOT_ON_PAGE = "quote가 그 쪽 텍스트에 없음"
NUMBER_NOT_IN_QUOTE = "숫자가 quote에 없음"
NO_NORMAL_FORM = "값의 정규형을 만들 수 없음"
QUOTE_OUTSIDE_BLOCK = "일반공급 ①지역 묶음 밖"
BAD_SHAPE = "값의 꼴이 표와 다름"
SUM_NOT_100 = "%의 합이 100이 아님"
NO_RULE_NOTE = "묶음이 없는 공고인데 note에 규칙 2·3 표시가 없음"
RULE_2_MARK, RULE_3_MARK = "공통 표", "해당지역 우선 문장"  # 묶음이 없을 때 note에 적는 말

_KEYS = {"value", "quote", "page", "note"}


class LabelCell(NamedTuple):
    pbno: str
    field: str
    value: str | None
    quote: str | None
    page: int | None
    note: str | None
    problems: tuple[str, ...]  # 값이 있는 칸이 정답 검사에 걸린 이유. 없으면 빈 튜플
    rule: int | None = None  # 거주지 값이 있는 칸이 고르는 규칙 1·2·3 중 어디서 왔나. 모르면 None


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
    if field == RESIDENT:
        found += _resident_problems(raw, texts)
    return tuple(found)


def _resident_problems(raw: dict, texts: list[str]) -> list[str]:
    found = []
    if block := resident_block(texts):
        if not grounded(raw["quote"], block.text):
            found.append(QUOTE_OUTSIDE_BLOCK)
    elif not any(mark in (raw["note"] or "") for mark in (RULE_2_MARK, RULE_3_MARK)):
        found.append(NO_RULE_NOTE)
    if not _resident_shape_ok(raw["value"]):
        found.append(BAD_SHAPE)
    if sum_is_not_100(raw["value"]):
        found.append(SUM_NOT_100)
    return found


def _resident_rule(raw: dict, texts: list[str]) -> int | None:
    if raw["value"] is None:
        return None
    if resident_block(texts):
        return 1
    note = raw["note"] or ""
    return 2 if RULE_2_MARK in note else 3 if RULE_3_MARK in note else None


def check_labels(
    data: object,
    split: Split,
    texts: dict[str, list[str]],
    expected: int = CELLS,
    fields: tuple[str, ...] = PDF_FIELDS,
) -> list[LabelCell]:
    """정답 파일 구조를 확인하고 칸 목록을 만든다. 구조가 틀리면 ValueError.

    값이 있는 칸이 정답 검사(quote가 그 쪽에 있다, 숫자가 quote에 있다, 거주지는 묶음·꼴·합)에
    걸리면 에러가 아니라 칸의 problems에 적는다. split은 코드가 다시 뽑은 목록이다.
    split.tune이 비어 있으면(새 30건 파일) tune 키가 없는 파일이다.
    """
    keys = ("tune", "test", "cells") if split.tune else ("test", "cells")
    if not isinstance(data, dict) or set(data) != set(keys):
        raise ValueError(f"정답 파일은 {'·'.join(keys)} 키를 가진 객체여야 한다")
    if (split.tune and data["tune"] != split.tune) or data["test"] != split.test:
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
        if extra := set(got) - set(fields):
            raise ValueError(f"{pbno}: 정답에 필드가 더 있다: {sorted(extra)}")
        for f in fields:
            if f not in got:
                raise ValueError(f"{pbno}: 정답에 필드 {f}이(가) 없다")
            raw = _check_cell(f"{pbno} {f}", got[f])
            rule = _resident_rule(raw, texts[pbno]) if f == RESIDENT else None
            out.append(
                LabelCell(
                    pbno,
                    f,
                    raw["value"],
                    raw["quote"],
                    raw["page"],
                    raw["note"],
                    _problems(f, raw, texts[pbno]),
                    rule,
                )
            )
    if extra := set(cells) - {*split.tune, *split.test}:
        raise ValueError(f"정답에 대상 밖의 공고가 있다: {sorted(extra)}")
    if len(out) != expected:
        raise ValueError(f"칸이 {len(out)}개다. {expected}개여야 한다")
    return out


# 칸 상태 다섯. 정답에 값이 있는 칸은 앞 셋, 정답이 null인 칸은 뒤 둘
RIGHT, BLANK, OTHER = "맞음", "비움", "다른 값으로 채움"
NULL_BLANK, NULL_FILLED = "null에 비움", "null에 값을 채움"
STATES = (RIGHT, BLANK, OTHER, NULL_BLANK, NULL_FILLED)

# 거주지를 읽은 곳: 일반공급 ①지역 묶음을 찾아 그것만 줬나, 못 찾아 전체 텍스트를 줬나
FROM_BLOCK, FROM_WHOLE = "묶음", "전체"
SOURCES = (FROM_BLOCK, FROM_WHOLE)


def cell_state(field: str, truth: str | None, got: str | None) -> str:
    if truth is None:
        return NULL_BLANK if _blank(got) else NULL_FILLED
    if _blank(got):
        return BLANK
    want = normal_form(field, truth)
    return RIGHT if want is not None and normal_form(field, got) == want else OTHER


def _load(
    raw_dir: Path,
    labels_path: Path,
    set_name: str,
    split: Split | None,
    expected: int | None,
    eligible: list[str] | None = None,
) -> tuple[dict, Split, dict[str, list[str]], list[LabelCell]]:
    """tune는 기존 50건 세 필드 파일, test는 새 30건 거주지 파일이다."""
    tune = set_name == "tune"
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    if split is None:
        eligible = eligible if eligible is not None else eligible_pbnos(raw_dir)
        first = pick(eligible)
        split = first if tune else pick_resident(eligible, [*first.tune, *first.test])
    texts = {p: pdf_pages(raw_dir / p / "notice.pdf") for p in [*split.tune, *split.test]}
    fields = PDF_FIELDS if tune else (RESIDENT,)
    want = expected or (CELLS if tune else RESIDENT_CELLS)
    cells = check_labels(data, split, texts, want, fields)
    return data, split, texts, cells


def _pct(n: int, total: int) -> str:
    return f"{n} ({n / total:.1%})" if total else f"{n} (—)"


def _problem_table(flagged: list[LabelCell]) -> str:
    return _table(
        ("공고", "필드", "쪽", "이유", "quote"),
        [(c.pbno, c.field, c.page, "; ".join(c.problems), c.quote) for c in flagged],
    )


def _reason_kind(reason: str) -> str:
    return reason.split(":")[0]  # 「숫자가 quote에 없음: 150」은 숫자와 상관없이 한 사유로 센다


def render_labels(
    files: list[tuple[str, list[LabelCell]]],
    eligible: int,
    with_block: int,
    blocks: dict[str, bool],
) -> str:
    """files: (정답 파일 경로, 칸 목록). blocks: 정답 파일에 든 공고별 일반공급 ①지역 묶음 유무."""
    cells = [c for _, cs in files for c in cs]
    flagged = [c for c in cells if c.problems]
    filled = [c for c in cells if c.value is not None]
    md = "# 수동 정답 요약 (PDF에만 있는 필드 3개)\n\n"
    md += "정답 파일은 " + ", ".join(f"`{name}`" for name, _ in files) + "이다. "
    md += "청약홈과 OpenAI에 요청하지 않았다.\n\n"
    md += _table(
        ("정답 파일", "공고", "칸", "값 있는 칸", "null 칸", "검사에 걸린 칸"),
        [
            (
                name,
                len({c.pbno for c in cs}),
                len(cs),
                sum(c.value is not None for c in cs),
                sum(c.value is None for c in cs),
                sum(bool(c.problems) for c in cs),
            )
            for name, cs in files
        ],
    )
    md += f"\n- 값이 있는 칸 {len(filled)}개, null 칸 {len(cells) - len(filled)}개\n"
    md += f"- 정답 검사에 걸린 칸 {len(flagged)}개\n"
    multi = sum(c.field == RESALE and "," in (c.value or "") for c in cells)
    md += f"- 주택형마다 전매제한이 달라 `,`로 이은 칸 {multi}개\n"
    md += f"- PDF 텍스트가 있는 공고 {eligible}건 중 일반공급 ①지역 묶음을 찾은 공고 "
    md += f"{with_block}건\n"
    md += (
        f"- 정답 파일의 공고 {len(blocks)}건 중 묶음이 있는 공고 {sum(blocks.values())}건"
        f", 없는 공고 {len(blocks) - sum(blocks.values())}건\n\n"
    )
    rows = []
    for f in PDF_FIELDS:
        mine = [c for c in cells if c.field == f]
        if not mine:
            continue
        got = sum(c.value is not None for c in mine)
        rows.append((f, got, len(mine) - got, sum(bool(c.problems) for c in mine)))
    md += _table(("필드", "값 있는 칸", "null 칸", "검사에 걸린 칸"), rows)
    reasons = Counter(_reason_kind(r) for c in flagged for r in c.problems)
    md += "\n검사에 걸린 칸의 사유별 수(한 칸이 여러 사유에 걸릴 수 있다):\n\n"
    md += _table(("사유", "칸 수"), sorted(reasons.items())) if reasons else "없음\n"
    resident = [c for c in cells if c.field == RESIDENT]
    by_rule = Counter(c.rule for c in resident if c.value is not None)
    md += f"\n거주지 정답 {len(resident)}칸이 고르는 규칙 1·2·3 중 어디서 왔나:\n\n"
    md += _table(
        ("고르는 규칙", "칸 수"),
        [
            ("1 일반공급 ①지역 묶음", by_rule[1]),
            ("2 공통 표", by_rule[2]),
            ("3 해당지역 우선 문장", by_rule[3]),
            ("표시 없음", by_rule[None]),
            ("null (읽은 곳이 없다)", sum(c.value is None for c in resident)),
        ],
    )
    md += f"\n검사에 걸린 칸 {len(flagged)}개:\n\n"
    md += _problem_table(flagged) if flagged else "없음\n"
    nulls = [c for c in cells if c.value is None]
    md += f"\nnull 칸 {len(nulls)}개의 note (찾아본 쪽):\n\n"
    md += _table(("공고", "필드", "note"), [(c.pbno, c.field, c.note) for c in nulls])
    return md


def check_pdf_labels(
    raw_dir: Path,
    tune_path: Path,
    test_path: Path,
    out: Path,
    tune_split: Split | None = None,
    test_split: Split | None = None,
    tune_expected: int | None = None,
    test_expected: int | None = None,
) -> list[LabelCell]:
    """정답 파일 둘을 검사하고 요약을 out에 쓴다. 구조가 틀리면 ValueError. LLM을 부르지 않는다."""
    eligible = eligible_pbnos(raw_dir)
    _, _, tune_texts, tune_cells = _load(
        raw_dir, tune_path, "tune", tune_split, tune_expected, eligible
    )
    _, _, test_texts, test_cells = _load(
        raw_dir, test_path, "test", test_split, test_expected, eligible
    )
    with_block = sum(
        resident_block(pdf_pages(raw_dir / p / "notice.pdf")) is not None for p in eligible
    )
    blocks = {p: resident_block(t) is not None for p, t in {**tune_texts, **test_texts}.items()}
    files = [(tune_path.as_posix(), tune_cells), (test_path.as_posix(), test_cells)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_labels(files, len(eligible), with_block, blocks), encoding="utf-8")
    return [*tune_cells, *test_cells]


class Scored(NamedTuple):
    pbno: str
    field: str
    truth: str | None
    value: str | None  # LLM이 남긴 값
    evidence: str | None
    page: int | None  # LLM 근거 쪽
    state: str
    why: str | None  # 비운 이유(LLM이 비운 칸도 들어 있다)
    truth_page: int | None = None  # 정답 근거 쪽
    source: str | None = None  # 거주지만: 묶음 / 전체
    sum_off: bool = False  # 거주지 LLM 값의 %합이 100이 아니다


class PdfResult(NamedTuple):
    cells: list[Scored]
    skipped: list[tuple[str, str]]  # (공고, 이유). 잰 칸에서 빠진 공고
    label_problems: list[LabelCell]  # 정답 검사에 걸린 칸(잰 집합의 공고만)
    input_tokens: int


def _count_table(states: tuple[str, ...], cells: list[Scored]) -> str:
    return _table(
        ("상태", "칸 수 (비율)"),
        [(s, _pct(sum(c.state == s for c in cells), len(cells))) for s in states],
    )


def _n(cells: list[Scored], *states: str) -> int:
    return sum(c.state in states for c in cells)


def _source_table(cells: list[Scored]) -> str:
    """거주지 칸을 출처별로 센다. 정답에 값 있는 칸 중 비율은 앞 셋, null인 칸 중 비율은 뒤 둘."""
    rows = []
    for src in SOURCES:
        mine = [c for c in cells if c.source == src]
        filled = [c for c in mine if c.truth is not None]
        nulls = [c for c in mine if c.truth is None]
        rows.append(
            (
                src,
                len(mine),
                *(_pct(_n(filled, s), len(filled)) for s in (RIGHT, BLANK, OTHER)),
                *(_pct(_n(nulls, s), len(nulls)) for s in (NULL_BLANK, NULL_FILLED)),
            )
        )
    return _table(("출처", "칸", RIGHT, BLANK, OTHER, NULL_BLANK, NULL_FILLED), rows)


def render_eval(set_name: str, model: str | None, result: PdfResult) -> str:
    cells = result.cells
    filled = [c for c in cells if c.truth is not None]
    nulls = [c for c in cells if c.truth is None]
    notices = list(dict.fromkeys(c.pbno for c in cells))
    names = [f for f in PDF_FIELDS if any(c.field == f for c in cells)]
    kind = "다듬는" if set_name == "tune" else "재는"
    md = f"# 세 필드 LLM 추출 — {kind} 공고 ({set_name})\n\n"
    md += f"공고 {len(notices)}건 · 칸 {len(cells)}개"
    md += f" · 모델 {model}\n\n" if model else "\n\n"
    md += f"정답에 값이 있는 칸 {len(filled)}개 중:\n\n"
    md += _count_table((RIGHT, BLANK, OTHER), filled)
    md += f"\n정답이 null인 칸 {len(nulls)}개 중:\n\n"
    md += _count_table((NULL_BLANK, NULL_FILLED), nulls)
    resident = [c for c in cells if c.field == RESIDENT]
    if resident:
        md += f"\n거주지 칸 {len(resident)}개를 읽은 곳(출처)별로 센다:\n\n"
        md += _source_table(resident)
        md += f"\nLLM 값의 %를 더하면 100이 아닌 거주지 칸 {sum(c.sum_off for c in resident)}개\n"
    rows = []
    for f in names:
        mine = [c for c in cells if c.field == f]
        rows.append(
            (
                f,
                _n(mine, RIGHT, BLANK, OTHER),
                _n(mine, RIGHT),
                _n(mine, BLANK),
                _n(mine, OTHER),
                _n(mine, NULL_BLANK, NULL_FILLED),
                _n(mine, NULL_BLANK),
                _n(mine, NULL_FILLED),
            )
        )
    md += "\n필드별:\n\n" + _table(
        (
            "필드",
            "값 있는 칸",
            "맞음",
            "비움",
            "다른 값",
            "null 칸",
            "null에 비움",
            "null에 값을 채움",
        ),
        rows,
    )
    wrong = [c for c in cells if c.state not in (RIGHT, NULL_BLANK)]
    md += f"\n맞지 않은 칸 {len(wrong)}개:\n\n"
    md += (
        _table(
            (
                "공고",
                "필드",
                "정답 값",
                "LLM 값",
                "LLM 근거",
                "정답 쪽",
                "LLM 쪽",
                "출처",
                "합 100 아님",
                "상태",
                "비운 이유",
            ),
            [
                (
                    c.pbno,
                    c.field,
                    c.truth,
                    c.value,
                    c.evidence,
                    c.truth_page,
                    c.page,
                    c.source,
                    "예" if c.sum_off else None,
                    c.state,
                    c.why,
                )
                for c in wrong
            ],
        )
        if wrong
        else "없음\n"
    )
    md += f"\n입력 토큰 합계: {result.input_tokens:,}\n"
    if result.label_problems:
        md += f"\n정답 검사에 걸린 칸 {len(result.label_problems)}개:\n\n"
        md += _problem_table(result.label_problems)
    if result.skipped:
        md += "\n건너뛴 공고:\n\n" + "".join(f"- {p}: {why}\n" for p, why in result.skipped)
    return md


def _used(ask: Ask) -> int:
    usage = getattr(ask, "last_usage", None)
    return usage.input_tokens if usage else 0


def _extract_notice(
    pages: list[str], ask: Ask, resident_ask: Ask, others: bool
) -> tuple[dict[str, Extraction], dict[str, str], str, int]:
    """거주지는 따로 묻는다: 묶음이 있으면 그 묶음만, 없으면 전체 텍스트를 준다.

    others가 참이면 전매제한·신혼부부 소득 기준을 전체 텍스트로 한 번에 묻는다.
    돌려주는 값: (필드별 결과, 비운 이유, 출처, 입력 토큰).
    """
    if block := resident_block(pages):
        shown = [""] * (block.page - 1) + [block.text]  # 근거는 이 쪽, 이 묶음 안에서만 인정한다
        got = extract(shown, resident_ask, fields=RESIDENT_BLOCK_SET, only=block.page)
        source = FROM_BLOCK
    else:
        got = extract(pages, resident_ask, fields=RESIDENT_FULL_SET)
        source = FROM_WHOLE
    fields, blanked, tokens = dict(got.fields), dict(got.blanked), _used(resident_ask)
    if others:
        more = extract(pages, ask, fields=TWO_FIELD_SET)
        fields.update(more.fields)
        blanked.update(more.blanked)
        tokens += _used(ask)
    return fields, blanked, source, tokens


def evaluate_pdf(
    set_name: str,
    raw_dir: Path,
    labels_path: Path,
    ask: Ask,
    out: Path,
    split: Split | None = None,
    expected: int | None = None,
    resident_ask: Ask | None = None,
) -> PdfResult:
    """정답 파일과 data/raw/만 읽고 set_name의 공고를 추출해 점수를 쓴다.

    tune은 기존 50건의 세 필드(labels/pdf-only-50.json), test는 새 30건의 거주지만
    (labels/pdf-resident-30.json)이다. resident_ask를 안 주면 ask로 거주지도 묻는다.
    청약홈에 요청하지 않는다. 정답 파일 구조가 틀리면 LLM을 부르기 전에 ValueError다.
    """
    if set_name not in ("tune", "test"):
        raise ValueError(f"집합은 tune 또는 test다: {set_name!r}")
    _, split, texts, labels = _load(raw_dir, labels_path, set_name, split, expected)
    label = {(c.pbno, c.field): c for c in labels}
    fields = PDF_FIELDS if set_name == "tune" else (RESIDENT,)
    notices = [*split.tune, *split.test]
    scored: list[Scored] = []
    skipped: list[tuple[str, str]] = []
    tokens = 0
    for pbno in notices:
        try:
            got, blanked, source, used = _extract_notice(
                texts[pbno], ask, resident_ask or ask, set_name == "tune"
            )
        except ContextExceeded as e:
            skipped.append((pbno, f"컨텍스트 한도 초과: {e}"))
            continue
        except BadResponse as e:  # 인증·한도 오류는 잡지 않고 멈춘다
            skipped.append((pbno, f"LLM 응답을 쓸 수 없음: {e}"))
            continue
        tokens += used
        # 응답을 못 읽은 칸이 정답 null 칸에서 「null에 비움」(맞음)으로 세어지지 않게 공고째 뺀다
        unreadable = {why for why in blanked.values() if why in (BAD_JSON, NO_KEY, BAD_CELL)}
        if unreadable:
            skipped.append((pbno, f"LLM 응답을 읽을 수 없음: {', '.join(sorted(unreadable))}"))
            continue
        for f in fields:
            x, truth = got[f], label[pbno, f]
            scored.append(
                Scored(
                    pbno,
                    f,
                    truth.value,
                    x.value,
                    x.evidence,
                    x.page,
                    cell_state(f, truth.value, x.value),
                    blanked.get(f),
                    truth.page,
                    source if f == RESIDENT else None,
                    f == RESIDENT and sum_is_not_100(x.value),
                )
            )
    mine = set(notices)  # 다른 집합의 정답 문제로 이 집합의 종료 코드를 바꾸지 않는다
    flagged = [c for c in labels if c.problems and c.pbno in mine]
    result = PdfResult(scored, skipped, flagged, tokens)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_eval(set_name, getattr(ask, "model", None), result), encoding="utf-8")
    return result
