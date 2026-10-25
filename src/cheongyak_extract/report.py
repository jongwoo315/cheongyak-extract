"""필드별 eval 리포트. 지표 정의는 docs/plans/146-1025-design-skeleton.md §리포트 지표."""

from dataclasses import dataclass

from cheongyak_extract.extract import Extraction

COLUMNS = (
    "필드",
    "정답 있음",
    "정확도",
    "빈 칸",
    "지어낸 값",
    "비어야 하는데 채움",
    "근거 위치 맞음",
)


@dataclass(frozen=True)
class Doc:
    pbno: str
    truth: dict[str, str | None]
    extracted: dict[str, Extraction]
    pages: list[str]


@dataclass(frozen=True)
class FieldMetrics:
    field: str
    with_truth: int
    accuracy: float | None
    blank: float | None
    fabricated: int
    filled_empty: int
    page_ok: float | None


def _empty(v: str | None) -> bool:
    return not (v or "").strip()


def _norm(s: str) -> str:
    return " ".join(s.split())


def _grounded(evidence: str | None, text: str) -> bool:
    return evidence is not None and _norm(evidence) in _norm(text)


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def metrics(docs: list[Doc], fields: tuple[str, ...]) -> list[FieldMetrics]:
    out = []
    for f in fields:
        with_truth = correct = blank = fabricated = filled_empty = paged = page_ok = 0
        for d in docs:
            truth, ex = d.truth[f], d.extracted[f]
            if _empty(truth):
                filled_empty += not _empty(ex.value)
            else:
                with_truth += 1
                correct += not _empty(ex.value) and ex.value.strip() == truth.strip()
                blank += _empty(ex.value)
            if not _empty(ex.value) and not _grounded(ex.evidence, "\n".join(d.pages)):
                fabricated += 1
            if ex.page is not None:
                paged += 1
                in_range = 1 <= ex.page <= len(d.pages)
                page_ok += in_range and _grounded(ex.evidence, d.pages[ex.page - 1])
        out.append(
            FieldMetrics(
                f,
                with_truth,
                _rate(correct, with_truth),
                _rate(blank, with_truth),
                fabricated,
                filled_empty,
                _rate(page_ok, paged),
            )
        )
    return out


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def render_markdown(rows: list[FieldMetrics]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + " --- |" * len(COLUMNS)]
    for m in rows:
        cells = (
            m.field,
            m.with_truth,
            _pct(m.accuracy),
            _pct(m.blank),
            m.fabricated,
            m.filled_empty,
            _pct(m.page_ok),
        )
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"
