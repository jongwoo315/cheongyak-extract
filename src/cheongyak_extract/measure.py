"""모의 추출값 24쌍으로 정규화 효과를 잰다. 정규화 전은 `strip()` 비교다."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.truth import parse_truth

Norm = Callable[[str, str], str | None]  # (field, value) -> 정규형


class Pair(NamedTuple):
    pbno: str
    field: str
    truth: str | None
    mock: str | None


def _strip(field: str, value: str) -> str:
    return value.strip()


def load_pairs(raw_dir: Path, fixture: Path, fields: tuple[str, ...] = FIELDS) -> list[Pair]:
    forms = json.loads(fixture.read_text(encoding="utf-8"))
    pairs = []
    for pbno, form in forms.items():
        truth = parse_truth((raw_dir / pbno / "detail.html").read_text(encoding="utf-8"))
        pairs += [Pair(pbno, f, truth[f], (form[f] or {}).get("value")) for f in fields]
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
    if rows:
        md += "\n안 맞는 쌍:\n\n| 공고 | 필드 | 정답 | 모의값 | 정규형(정답) | 정규형(모의값) |\n"
        md += "| --- | --- | --- | --- | --- | --- |\n"
        for p in rows:
            norm = [after(p.field, v) if v is not None else None for v in (p.truth, p.mock)]
            cells = (p.pbno, p.field, p.truth, p.mock, *norm)
            md += "| " + " | ".join(_cell(c) for c in cells) + " |\n"
    return md


def measure_normalize(raw_dir: Path, fixture: Path, report_path: Path) -> str:
    md = render(load_pairs(raw_dir, fixture), _strip)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    print(md)
    return md
