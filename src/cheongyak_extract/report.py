"""필드별 eval 리포트. 지표 정의는 docs/plans/146-1025-design-skeleton.md §리포트 지표."""

from dataclasses import dataclass, field

from cheongyak_extract.extract import (
    BAD_CELL,
    BAD_JSON,
    BAD_PAGE,
    EMPTY,
    NO_EVIDENCE,
    NO_KEY,
    NOT_IN_PAGE,
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

# 근거 규칙(2·3·4)으로 비운 칸은 LLM이 값을 줬다가 코드가 비운 칸이다
_GAVE_THEN_BLANKED = (NO_EVIDENCE, BAD_PAGE, NOT_IN_PAGE)
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
                ungrounded += d.blanked.get(f) == NOT_IN_PAGE
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


def render_summary(docs: list[Doc], fields: tuple[str, ...]) -> str:
    states = [s for d in docs for f in fields if (s := _state(f, d))]
    gave = blanked_ungrounded = 0
    for d in docs:
        for f in fields:
            if _state(f, d) is None:
                continue
            why = d.blanked.get(f)
            gave += not _empty(d.extracted.get(f, EMPTY).value) or why in _GAVE_THEN_BLANKED
            blanked_ungrounded += why == NOT_IN_PAGE
    count = states.count
    md = (
        f"정답 있는 칸 {len(states)} · 맞음 {count('right')} · 비움 {count('blank')}"
        f" · 틀리게 채움 {count('wrong')}\n\n"
    )
    if gave:
        md += (
            f"LLM이 값을 준 {gave}칸 중 근거를 확인 못해 비운 칸 {blanked_ungrounded}"
            f" ({_pct(blanked_ungrounded / gave)})\n"
        )
    else:
        md += "LLM이 값을 준 칸 없음\n"
    return md
