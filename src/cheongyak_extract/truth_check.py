"""청약홈 정답(HTML)과 공고문 PDF 값을 칸마다 대조한다. 라벨 파일은 labels/pdf-values-20.json."""

from typing import NamedTuple

from cheongyak_extract.extract import FIELDS, grounded
from cheongyak_extract.normalize import normalize

CELLS = 160  # 공고 20건 × 필드 8개. 빈 파일이 「0/0」으로 깨끗해 보이지 않게 센다
_KEYS = {"value", "quote", "page", "note"}


class Cell(NamedTuple):
    pbno: str
    field: str
    html: str | None
    pdf: str | None
    page: int | None
    note: str | None
    same: bool  # 정규화 뒤 HTML 값과 PDF 값이 같다
    ungrounded: bool  # quote가 있는데 그 쪽 텍스트에서 못 찾았다


def _check_label(pbno: str, field: str, raw: object) -> dict:
    where = f"{pbno} {field}"
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ValueError(f"{where}: 칸은 {sorted(_KEYS)} 키를 모두 가진 객체여야 한다")
    has_value = bool((raw["value"] or "").strip())
    has_quote = bool((raw["quote"] or "").strip())
    if has_value != has_quote or has_quote != (raw["page"] is not None):
        raise ValueError(f"{where}: value·quote·page는 모두 있거나 모두 null이어야 한다")
    return raw


def check_cells(
    labels: dict[str, dict[str, dict]],
    truths: dict[str, dict[str, str | None]],
    texts: dict[str, list[str]],
    fields: tuple[str, ...] = FIELDS,
    expected: int = CELLS,
) -> list[Cell]:
    """공고마다 정답(truths)·쪽 텍스트(texts)와 라벨을 맞춰 칸 목록을 만든다.

    라벨에 공고나 필드가 빠졌거나 남으면, 칸 수가 expected가 아니면 ValueError다.
    """
    out: list[Cell] = []
    for pbno in truths:
        got = labels.get(pbno)
        if got is None:
            raise ValueError(f"{pbno}: 라벨에 이 공고가 없다")
        if extra := set(got) - set(fields):
            raise ValueError(f"{pbno}: 라벨에 필드가 더 있다: {sorted(extra)}")
        for f in fields:
            if f not in got:
                raise ValueError(f"{pbno}: 라벨에 필드 {f}이(가) 없다")
            lab = _check_label(pbno, f, got[f])
            page = lab["page"]
            pages = texts[pbno]
            found = lab["quote"] is None or (
                1 <= page <= len(pages) and grounded(lab["quote"], pages[page - 1])
            )
            same = normalize(f, truths[pbno][f]) == normalize(f, lab["value"])
            out.append(
                Cell(pbno, f, truths[pbno][f], lab["value"], page, lab["note"], same, not found)
            )
    if extra := set(labels) - set(truths):
        raise ValueError(f"라벨에 대조 대상이 아닌 공고가 있다: {sorted(extra)}")
    if len(out) != expected:
        raise ValueError(f"칸이 {len(out)}개다. {expected}개여야 한다")
    return out
