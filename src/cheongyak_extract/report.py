"""필드별 eval 리포트. 지표 정의는 docs/plans/146-1025-design-skeleton.md §리포트 지표."""

from dataclasses import dataclass, field, replace

from cheongyak_extract.extract import (
    BAD_CELL,
    BAD_JSON,
    BAD_PAGE,
    EMPTY,
    NO_EVIDENCE,
    NO_KEY,
    RULE_BLANKS,
    RULES,
    Extracted,
    Extraction,
    Usage,
    grounded,
)
from cheongyak_extract.normalize import normalize

COLUMNS = (
    "필드",
    "정답 있음",
    "정확도",
    "빈 칸",
    "지어낸 값",
    "비어야 하는데 채움",
    "근거 위치 맞음",
    "틀리게 채움",
    "근거 확인 못해 비움",
)

# 근거 규칙(2·3)과 값을 남기는 조건(4)으로 비운 칸은 LLM이 값을 줬다가 코드가 비운 칸이다
_GAVE_THEN_BLANKED = (NO_EVIDENCE, BAD_PAGE, *RULE_BLANKS)
# 응답 모양이 깨져 비운 칸. LLM이 일부러 비운 것도, 근거 규칙으로 비운 것도 아니다
_SHAPE_ERRORS = (BAD_JSON, BAD_CELL, NO_KEY)


@dataclass(frozen=True)
class Doc:
    pbno: str
    truth: dict[str, str | None]
    extracted: dict[str, Extraction]
    pages: list[str]
    blanked: dict[str, str] = field(default_factory=dict)  # 필드 -> 비운 이유
    usage: Usage | None = None
    rules: dict[str, Extracted] = field(default_factory=dict)  # 같은 응답에 건 A·B·C안 결과


def with_rule(d: Doc, rule: str) -> Doc:
    """d의 extracted·blanked를 rule안 결과로 바꾼 Doc. d.rules에 없는 안이면 KeyError."""
    r = d.rules[rule]
    return replace(d, extracted=r.fields, blanked=r.blanked)


@dataclass(frozen=True)
class FieldMetrics:
    field: str
    with_truth: int
    accuracy: float | None
    blank: float | None
    fabricated: int
    filled_empty: int
    page_ok: float | None
    wrong: int = 0  # 틀리게 채운 칸 수
    ungrounded: int = 0  # 근거를 확인 못해 코드가 비운 칸 수


def _empty(v: str | None) -> bool:
    return not (v or "").strip()


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def _state(f: str, d: Doc) -> str | None:
    """정답이 있는 칸의 상태: right / blank / wrong. 정답이 없으면 None."""
    truth, ex = d.truth.get(f), d.extracted.get(f, EMPTY)
    if _empty(truth):
        return None
    if _empty(ex.value):
        return "blank"
    return "right" if normalize(f, ex.value) == normalize(f, truth) else "wrong"


def metrics(docs: list[Doc], fields: tuple[str, ...]) -> list[FieldMetrics]:
    out = []
    for f in fields:
        with_truth = correct = blank = wrong = ungrounded = 0
        fabricated = filled_empty = paged = page_ok = 0
        for d in docs:
            ex = d.extracted.get(f, EMPTY)
            state = _state(f, d)
            if state is None:
                filled_empty += not _empty(ex.value)
            else:
                with_truth += 1
                correct += state == "right"
                blank += state == "blank"
                wrong += state == "wrong"
                ungrounded += d.blanked.get(f) in RULE_BLANKS
            if not _empty(ex.value) and not grounded(ex.evidence, "\n".join(d.pages)):
                fabricated += 1
            if ex.page is not None:
                paged += 1
                in_range = 1 <= ex.page <= len(d.pages)
                page_ok += in_range and grounded(ex.evidence, d.pages[ex.page - 1])
        out.append(
            FieldMetrics(
                f,
                with_truth,
                _rate(correct, with_truth),
                _rate(blank, with_truth),
                fabricated,
                filled_empty,
                _rate(page_ok, paged),
                wrong,
                ungrounded,
            )
        )
    return out


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def _cell(v: object) -> str:
    s = "—" if v is None else str(v)
    return s.replace("\n", " ⏎ ").replace("|", "\\|")


def _table(head: tuple[str, ...], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def render_markdown(rows: list[FieldMetrics]) -> str:
    return _table(
        COLUMNS,
        [
            (
                m.field,
                m.with_truth,
                _pct(m.accuracy),
                _pct(m.blank),
                m.fabricated,
                m.filled_empty,
                _pct(m.page_ok),
                m.wrong,
                m.ungrounded,
            )
            for m in rows
        ],
    )


def render_wrong(docs: list[Doc], fields: tuple[str, ...]) -> str:
    """틀리게 채운 칸을 한 줄씩. 원인(LLM 오답·정규화·정답 쪽)은 사람이 PDF를 보고 적는다."""
    rows = []
    for d in docs:
        for f in fields:
            if _state(f, d) == "wrong":
                ex = d.extracted[f]
                rows.append((d.pbno, f, d.truth[f], ex.value, ex.evidence, ex.page))
    if not rows:
        return "틀리게 채운 칸 없음\n"
    return _table(("공고", "필드", "정답", "추출값", "근거", "쪽"), rows)


def render_shape_errors(docs: list[Doc]) -> str:
    """응답 모양이 깨져 비운 칸. LLM이 비운 칸과 섞여 보이지 않게 한다. 없으면 빈 문자열."""
    rows = [(d.pbno, f, why) for d in docs for f, why in d.blanked.items() if why in _SHAPE_ERRORS]
    if not rows:
        return ""
    return "\n응답 모양이 깨져 비운 칸:\n\n" + _table(("공고", "필드", "이유"), rows)


def render_usage(docs: list[Doc]) -> str:
    def n(v: int | None) -> str:
        return "—" if v is None else f"{v:,}"

    rows = [(d.pbno, *(n(x) for x in (d.usage or (None, None)))) for d in docs]
    used = [d.usage for d in docs if d.usage]
    rows.append(
        ("합계", n(sum(u.input_tokens for u in used)), n(sum(u.output_tokens for u in used)))
    )
    return _table(("공고", "입력 토큰", "출력 토큰"), rows)


class _Counts:
    """정답이 있는 칸의 상태 수와, LLM이 값을 준 칸 중 값을 남기는 조건으로 비운 칸 수."""

    def __init__(self, docs: list[Doc], fields: tuple[str, ...]) -> None:
        self.n = self.right = self.blank = self.wrong = self.gave = self.rule_blanked = 0
        for d in docs:
            for f in fields:
                state = _state(f, d)
                if state is None:
                    continue
                self.n += 1
                self.right += state == "right"
                self.blank += state == "blank"
                self.wrong += state == "wrong"
                why = d.blanked.get(f)
                self.gave += (
                    not _empty(d.extracted.get(f, EMPTY).value) or why in _GAVE_THEN_BLANKED
                )
                self.rule_blanked += why in RULE_BLANKS


def _count_pct(num: int, den: int) -> str:
    return f"{num} ({_pct(_rate(num, den))})"


def render_summary(docs: list[Doc], fields: tuple[str, ...]) -> str:
    c = _Counts(docs, fields)
    md = f"정답 있는 칸 {c.n} · 맞음 {c.right} · 비움 {c.blank} · 틀리게 채움 {c.wrong}\n\n"
    if c.gave:
        md += (
            f"LLM이 값을 준 {c.gave}칸 중 근거를 확인 못해 비운 칸 {c.rule_blanked}"
            f" ({_pct(c.rule_blanked / c.gave)})\n"
        )
    else:
        md += "LLM이 값을 준 칸 없음\n"
    return md


def render_rule_table(docs: list[Doc], fields: tuple[str, ...]) -> str:
    """A·B·C안을 같은 응답에 걸었을 때의 칸 수. 안 결과가 없는 Doc뿐이면 빈 문자열."""
    if not any(d.rules for d in docs):
        return ""
    rows = []
    for rule in RULES:
        c = _Counts([with_rule(d, rule) for d in docs if d.rules], fields)
        rows.append(
            (
                rule,
                c.n,
                _count_pct(c.right, c.n),
                _count_pct(c.blank, c.n),
                _count_pct(c.wrong, c.n),
                c.gave,
                _count_pct(c.rule_blanked, c.gave),
            )
        )
    head = (
        "안",
        "정답 있는 칸",
        "맞음",
        "비움",
        "틀리게 채움",
        "LLM이 값을 준 칸",
        "그 조건으로 비운 칸",
    )
    return _table(head, rows)


def render_field_rates(docs: list[Doc], fields: tuple[str, ...]) -> str:
    """필드별로 안마다 맞은 칸 수와 비율(정답 있는 칸 기준). 안 결과가 없으면 빈 문자열."""
    ruled = [d for d in docs if d.rules]
    if not ruled:
        return ""
    rows = []
    for f in fields:
        per_rule = [_Counts([with_rule(d, r) for d in ruled], (f,)) for r in RULES]
        rows.append((f, per_rule[0].n, *(_count_pct(c.right, c.n) for c in per_rule)))
    return _table(("필드", "정답 있는 칸", *(f"{r}안 맞음" for r in RULES)), rows)


COMPANY_FIELDS = ("시행사", "시공사")


def _input_tokens(docs: list[Doc]) -> int:
    return sum(d.usage.input_tokens for d in docs if d.usage)


def render_mode_table(by_mode: dict[str, list[Doc]], fields: tuple[str, ...]) -> str:
    """텍스트 방식(T0·T1)마다 A·B·C안 칸 수, 회사 필드의 틀리게 채운 칸, 입력 토큰 합계."""
    rows = []
    for mode, docs in by_mode.items():
        for rule in RULES:
            ruled = [with_rule(d, rule) for d in docs if d.rules]
            c = _Counts(ruled, fields)
            company = _Counts(ruled, tuple(f for f in COMPANY_FIELDS if f in fields))
            rows.append(
                (
                    mode,
                    rule,
                    c.n,
                    _count_pct(c.right, c.n),
                    _count_pct(c.blank, c.n),
                    _count_pct(c.wrong, c.n),
                    company.wrong,
                    f"{_input_tokens(docs):,}",
                )
            )
    head = (
        "방식",
        "안",
        "정답 있는 칸",
        "맞음",
        "비움",
        "틀리게 채움",
        "시행사·시공사 틀리게 채움",
        "입력 토큰 합계",
    )
    return _table(head, rows)


def render_token_ratio(by_mode: dict[str, list[Doc]]) -> str:
    """T1 입력 토큰 ÷ T0 입력 토큰. 두 방식이 모두 없거나 T0 토큰을 모르면 빈 문자열."""
    if "T0" not in by_mode or "T1" not in by_mode:
        return ""
    t0 = _input_tokens(by_mode["T0"])
    if not t0:
        return ""
    return f"입력 토큰 T1 ÷ T0 = {_input_tokens(by_mode['T1']) / t0:.2f}배\n"
