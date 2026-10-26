"""모의 추출값 24쌍으로 정규화 효과를 잰다. 정규화 전은 `strip()` 비교다."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.normalize import normalize
from cheongyak_extract.truth import parse_truth

Norm = Callable[[str, str], str | None]  # (field, value) -> 정규형


class Pair(NamedTuple):
    pbno: str
    field: str
    truth: str | None
    mock: str | None
    note: str | None = None  # 사람이 적은 원인. fixture 칸의 `note`


def _strip(field: str, value: str) -> str:
    return value.strip()


def load_pairs(raw_dir: Path, fixture: Path, fields: tuple[str, ...] = FIELDS) -> list[Pair]:
    forms = json.loads(fixture.read_text(encoding="utf-8"))
    if not forms:  # 빈 fixture가 「0/0, 안 맞는 쌍 없음」으로 깨끗해 보이지 않게 한다
        raise ValueError(f"모의 추출값이 비어 있다: {fixture}")
    pairs = []
    for pbno, form in forms.items():
        truth = parse_truth((raw_dir / pbno / "detail.html").read_text(encoding="utf-8"))
        for f in fields:
            cell = form.get(f) or {}
            pairs.append(Pair(pbno, f, truth[f], cell.get("value"), cell.get("note")))
    return pairs


def _same(pair: Pair, norm: Norm) -> bool:
    if not (pair.truth or "").strip() or not (pair.mock or "").strip():
        return False
    return norm(pair.field, pair.truth) == norm(pair.field, pair.mock)


def tally(pairs: list[Pair], norm: Norm) -> int:
    return sum(_same(p, norm) for p in pairs)


def _cell(v: str | None) -> str:
    return "—" if v is None else v.replace("\n", " ⏎ ").replace("|", "\\|")


def render(pairs: list[Pair], after: Norm) -> str:
    n = len(pairs)
    md = "# 정규화 효과 측정\n\n"
    md += f"- 정규화 전 {tally(pairs, _strip)}/{n} (`strip()` 비교)\n"
    md += f"- 정규화 후 {tally(pairs, after)}/{n}\n"
    rows = [p for p in pairs if not _same(p, after)]
    if not rows:
        md += "\n안 맞는 쌍 없음\n"
    else:
        head = ("공고", "필드", "정답", "모의값", "정규형(정답)", "정규형(모의값)", "비고")
        md += "\n안 맞는 쌍:\n\n| " + " | ".join(head) + " |\n"
        md += "|" + " --- |" * len(head) + "\n"
        for p in rows:
            norm = [after(p.field, v) if v is not None else None for v in (p.truth, p.mock)]
            cells = (p.pbno, p.field, p.truth, p.mock, *norm, p.note)
            md += "| " + " | ".join(_cell(c) for c in cells) + " |\n"
    return md


def measure_normalize(raw_dir: Path, fixture: Path, report_path: Path) -> str:
    md = render(load_pairs(raw_dir, fixture), normalize)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    print(md)
    return md
