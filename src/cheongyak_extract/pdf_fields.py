"""PDF에만 적힌 필드 3개: 필드 정의, 정규형, 수동 정답(labels/pdf-only-50.json) 검사, 점수.

필드의 뜻과 정규형은 docs/plans/152-1031-design-pdf-only-fields.md §필드 3개의 뜻.
"""

import json
import random
import re
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import Ask, FieldSet, _blank, _squash, extract, grounded
from cheongyak_extract.llm import BadResponse, ContextExceeded
from cheongyak_extract.pdf_text import has_text
from cheongyak_extract.pdf_text import pages as pdf_pages
from cheongyak_extract.raw_check import scan
from cheongyak_extract.report import _table

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
        "일반공급 당첨자의 전매제한 기간 하나. 1쪽 요약표에 '전매제한' 칸이 있으면 그 값이다. "
        "없으면 전매행위 제한 안내 문장의 기간이다. '6개월', '3년'처럼 단위까지 쓴다. "
        "제한이 없다고 적혀 있으면 '없음'. 주택형·공급 유형마다 기간이 다르면 "
        "서로 다른 기간을 짧은 것부터 ', '로 잇는다. "
        "기간(년·개월)이나 '없음'이 아닌 값(임대의무기간, 분양전환 시기 등)이면 null"
    ),
    RESIDENT: (
        "일반공급 1순위·2순위 당첨자 선정 순서의 '① 지역' 줄 하나. "
        "특별공급(다자녀·노부모부양·신혼부부 등)의 지역 비율이 아니다. "
        "지역마다 %가 적혀 있으면 우선순위가 높은 지역부터 "
        "'평택시 30% / 경기도 20% / 기타 50%'처럼 쓴다. "
        "% 없이 해당지역 거주자 우선만 적혀 있으면 value는 정확히 '해당지역 100%'로 쓰고, "
        "evidence는 해당지역 거주자 우선을 적은 문장을 복사한다"
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


def _load(
    raw_dir: Path, labels_path: Path, split: Split | None, expected: int
) -> tuple[dict, Split, dict[str, list[str]], list[LabelCell]]:
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    split = split or pick(eligible_pbnos(raw_dir))
    texts = {p: pdf_pages(raw_dir / p / "notice.pdf") for p in [*split.tune, *split.test]}
    return data, split, texts, check_labels(data, split, texts, expected)


def _pct(n: int, total: int) -> str:
    return f"{n} ({n / total:.1%})" if total else f"{n} (—)"


def _problem_table(flagged: list[LabelCell]) -> str:
    return _table(
        ("공고", "필드", "쪽", "이유", "quote"),
        [(c.pbno, c.field, c.page, "; ".join(c.problems), c.quote) for c in flagged],
    )


def render_labels(cells: list[LabelCell]) -> str:
    flagged = [c for c in cells if c.problems]
    filled = [c for c in cells if c.value is not None]
    md = "# 수동 정답 요약 (PDF에만 있는 필드 3개)\n\n"
    md += f"공고 {len({c.pbno for c in cells})}건 · 칸 {len(cells)}개. "
    md += "정답 파일은 `labels/pdf-only-50.json`이다. 청약홈과 OpenAI에 요청하지 않았다.\n\n"
    md += f"- 값이 있는 칸 {len(filled)}개, null 칸 {len(cells) - len(filled)}개\n"
    md += f"- 정답 검사 둘(quote가 그 쪽에 있다, 숫자가 quote에 있다)에 걸린 칸 {len(flagged)}개\n"
    multi = sum(c.field == RESALE and "," in (c.value or "") for c in cells)
    md += f"- 주택형마다 전매제한이 달라 `,`로 이은 칸 {multi}개\n\n"
    rows = []
    for f in PDF_FIELDS:
        mine = [c for c in cells if c.field == f]
        got = sum(c.value is not None for c in mine)
        rows.append((f, got, len(mine) - got, sum(bool(c.problems) for c in mine)))
    md += _table(("필드", "값 있는 칸", "null 칸", "검사에 걸린 칸"), rows)
    md += f"\n검사에 걸린 칸 {len(flagged)}개:\n\n"
    md += _problem_table(flagged) if flagged else "없음\n"
    nulls = [c for c in cells if c.value is None]
    md += f"\nnull 칸 {len(nulls)}개의 note (찾아본 쪽):\n\n"
    md += _table(("공고", "필드", "note"), [(c.pbno, c.field, c.note) for c in nulls])
    return md


def check_pdf_labels(
    raw_dir: Path,
    labels_path: Path,
    out: Path,
    split: Split | None = None,
    expected: int = CELLS,
) -> list[LabelCell]:
    """정답 파일을 검사하고 요약을 out에 쓴다. 구조가 틀리면 ValueError. LLM을 부르지 않는다."""
    *_, cells = _load(raw_dir, labels_path, split, expected)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_labels(cells), encoding="utf-8")
    return cells


class Scored(NamedTuple):
    pbno: str
    field: str
    truth: str | None
    value: str | None  # LLM이 남긴 값
    evidence: str | None
    page: int | None
    state: str
    why: str | None  # 비운 이유(LLM이 비운 칸도 들어 있다)


class PdfResult(NamedTuple):
    cells: list[Scored]
    skipped: list[tuple[str, str]]  # (공고, 이유). 잰 칸에서 빠진 공고
    label_problems: list[LabelCell]  # 정답 검사 둘에 걸린 칸(잰 집합의 공고만)
    input_tokens: int


def _count_table(states: tuple[str, ...], cells: list[Scored]) -> str:
    return _table(
        ("상태", "칸 수 (비율)"),
        [(s, _pct(sum(c.state == s for c in cells), len(cells))) for s in states],
    )


def _n(cells: list[Scored], *states: str) -> int:
    return sum(c.state in states for c in cells)


def render_eval(set_name: str, model: str | None, result: PdfResult) -> str:
    cells = result.cells
    filled = [c for c in cells if c.truth is not None]
    nulls = [c for c in cells if c.truth is None]
    notices = list(dict.fromkeys(c.pbno for c in cells))
    kind = "다듬는" if set_name == "tune" else "재는"
    md = f"# 세 필드 LLM 추출 — {kind} 공고 ({set_name})\n\n"
    md += f"공고 {len(notices)}건 · 칸 {len(cells)}개"
    md += f" · 모델 {model}\n\n" if model else "\n\n"
    md += f"정답에 값이 있는 칸 {len(filled)}개 중:\n\n"
    md += _count_table((RIGHT, BLANK, OTHER), filled)
    md += f"\n정답이 null인 칸 {len(nulls)}개 중:\n\n"
    md += _count_table((NULL_BLANK, NULL_FILLED), nulls)
    rows = []
    for f in PDF_FIELDS:
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
            ("공고", "필드", "정답 값", "LLM 값", "LLM 근거", "쪽", "상태", "비운 이유"),
            [
                (c.pbno, c.field, c.truth, c.value, c.evidence, c.page, c.state, c.why)
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


def evaluate_pdf(
    set_name: str,
    raw_dir: Path,
    labels_path: Path,
    ask: Ask,
    out: Path,
    split: Split | None = None,
    expected: int = CELLS,
) -> PdfResult:
    """정답 파일과 data/raw/만 읽고 set_name(tune·test)의 공고를 세 필드로 추출해 점수를 쓴다.

    청약홈에 요청하지 않는다. 정답 파일 구조가 틀리면 LLM을 부르기 전에 ValueError다.
    """
    if set_name not in ("tune", "test"):
        raise ValueError(f"집합은 tune 또는 test다: {set_name!r}")
    data, _, texts, labels = _load(raw_dir, labels_path, split, expected)
    truth = {(c.pbno, c.field): c.value for c in labels}
    scored: list[Scored] = []
    skipped: list[tuple[str, str]] = []
    tokens = 0
    for pbno in data[set_name]:
        try:
            got = extract(texts[pbno], ask, fields=PDF_FIELD_SET)
        except ContextExceeded as e:
            skipped.append((pbno, f"컨텍스트 한도 초과: {e}"))
            continue
        except BadResponse as e:  # 인증·한도 오류는 잡지 않고 멈춘다
            skipped.append((pbno, f"LLM 응답을 쓸 수 없음: {e}"))
            continue
        if usage := getattr(ask, "last_usage", None):
            tokens += usage.input_tokens
        for f in PDF_FIELDS:
            x = got.fields[f]
            state = cell_state(f, truth[pbno, f], x.value)
            scored.append(
                Scored(
                    pbno, f, truth[pbno, f], x.value, x.evidence, x.page, state, got.blanked.get(f)
                )
            )
    mine = set(data[set_name])  # 다른 집합의 정답 문제로 이 집합의 종료 코드를 바꾸지 않는다
    flagged = [c for c in labels if c.problems and c.pbno in mine]
    result = PdfResult(scored, skipped, flagged, tokens)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_eval(set_name, getattr(ask, "model", None), result), encoding="utf-8")
    return result
