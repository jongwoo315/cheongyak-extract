"""청약홈 정답(HTML)과 공고문 PDF 값을 칸마다 대조한다. 라벨 파일은 labels/pdf-values-20.json."""

import json
import re
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract import compare
from cheongyak_extract.extract import FIELDS, grounded
from cheongyak_extract.normalize import normalize
from cheongyak_extract.pdf_text import pages
from cheongyak_extract.report import _cell
from cheongyak_extract.truth import parse_truth

CAUSES = ("표기 차이", "정정", "다른 값", "PDF에 없음")  # 같지 않은 칸의 원인. note 첫머리에 적는다
NO_CAUSE = "원인 미기재"
CELLS = 160  # 공고 20건 × 필드 8개. 빈 파일이 「0/0」으로 깨끗해 보이지 않게 센다
_KEYS = {"value", "quote", "page", "note"}


class Cell(NamedTuple):
    pbno: str
    field: str
    html: str | None
    pdf: str | None
    page: int | None
    quote: str | None
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
                Cell(
                    pbno,
                    f,
                    truths[pbno][f],
                    lab["value"],
                    page,
                    lab["quote"],
                    lab["note"],
                    same,
                    not found,
                )
            )
    if extra := set(labels) - set(truths):
        raise ValueError(f"라벨에 대조 대상이 아닌 공고가 있다: {sorted(extra)}")
    if len(out) != expected:
        raise ValueError(f"칸이 {len(out)}개다. {expected}개여야 한다")
    return out


def cause(note: str | None) -> str:
    head = (note or "").split(":", 1)[0].strip()
    return head if head in CAUSES else NO_CAUSE


class Reread(NamedTuple):
    pbno: str
    field: str
    value: str | None  # LLM·정규식이 낸 추출값
    pdf: str | None
    same: bool  # 정규화 뒤 PDF 값과 같다


class Checked(NamedTuple):
    cells: list[Cell]
    llm: list[Reread]
    regex: list[Reread]


def llm_values(md: str) -> dict[tuple[str, str], str | None]:
    """extract-new.md 「틀리게 채운 칸」 표의 추출값 열. 칸마다 (공고, 필드) -> 추출값."""
    part = re.search(r"틀리게 채운 칸:\n(.*?)\n토큰:", md, re.S)
    if part is None:
        raise ValueError("리포트에서 틀리게 채운 칸 표를 못 찾았다")
    out: dict[tuple[str, str], str | None] = {}
    for line in part[1].splitlines():
        if not re.match(r"\| \d{10} \| ", line):
            continue
        cols = re.split(r"(?<!\\) \| ", line.removeprefix("| ").removesuffix(" |"))
        value = cols[3].replace("\\|", "|").replace(" ⏎ ", "\n")
        out[(cols[0], cols[1])] = None if value == "—" else value
    return out


def reread(cells: list[Cell], extracted: dict[tuple[str, str], str | None]) -> list[Reread]:
    """추출값이 PDF 값과 정규화 뒤 같은지 칸마다 적는다."""
    pdf = {(c.pbno, c.field): c.pdf for c in cells}
    out = []
    for (pbno, f), value in extracted.items():
        if (pbno, f) not in pdf:
            raise ValueError(f"{pbno} {f}: 대조한 160칸에 없는 칸이다")
        out.append(
            Reread(pbno, f, value, pdf[pbno, f], normalize(f, value) == normalize(f, pdf[pbno, f]))
        )
    return out


def _pct(n: int, total: int) -> str:
    return f"{n}/{total} ({n / total:.1%})" if total else f"{n}/{total} (—)"


def _table(head: tuple[str, ...], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _reread_table(rows: list[Reread]) -> str:
    if not rows:
        return "없음\n"
    return _table(
        ("공고", "필드", "추출값", "PDF 값", "PDF 값과"),
        [(r.pbno, r.field, r.value, r.pdf, "같음" if r.same else "다름") for r in rows],
    )


def render(checked: Checked, fields: tuple[str, ...] = FIELDS) -> str:
    cells = checked.cells
    diff = [c for c in cells if not c.same]
    bad = [c for c in cells if c.ungrounded]
    by_cause = {k: sum(cause(c.note) == k for c in diff) for k in CAUSES}
    if missing := sum(cause(c.note) == NO_CAUSE for c in diff):
        by_cause[NO_CAUSE] = missing
    same = len(cells) - len(diff)
    md = "# 청약홈 정답과 공고문 PDF 값 대조\n\n"
    md += f"공고 {len({c.pbno for c in cells})}건 · 칸 {len(cells)}개. "
    md += "청약홈 정답은 상세 HTML(`truth.parse_truth`), PDF 값은 `labels/pdf-values-20.json`이다. "
    md += "청약홈과 OpenAI에 요청하지 않았다.\n\n"
    md += f"- 정규화 뒤 같은 칸: {_pct(same, len(cells))}\n"
    md += f"- 근거를 그 쪽에서 못 찾은 칸: {len(bad)}\n\n"
    md += "같지 않은 칸의 원인:\n\n" + _table(("원인", "칸 수"), list(by_cause.items()))
    lenient = _pct(same + by_cause["표기 차이"], len(cells))
    md += f"\n참고: 표기 차이를 같은 칸으로 쳤을 때: {lenient}. 본 수치를 대신하지 않는다.\n\n"
    rows = [
        (f, sum(c.field == f for c in cells), sum(c.field == f and c.same for c in cells))
        for f in fields
    ]
    md += "필드별 같은 칸:\n\n" + _table(("필드", "칸", "같은 칸"), rows)
    md += f"\n같지 않은 칸 {len(diff)}개:\n\n"
    md += (
        _table(
            ("공고", "필드", "HTML 값", "PDF 값", "쪽", "note"),
            [(c.pbno, c.field, c.html, c.pdf, c.page, c.note) for c in diff],
        )
        if diff
        else "없음\n"
    )
    if bad:
        md += "\n근거를 그 쪽에서 못 찾은 칸:\n\n"
        md += _table(
            ("공고", "필드", "쪽", "quote"),
            [(c.pbno, c.field, c.page, c.quote) for c in bad],
        )
    md += "\n## LLM·정규식 점수를 PDF 값으로 다시 읽기\n\n"
    md += "정답과 다른 값으로 채운 칸의 추출값이 PDF 값과 정규화 뒤 같은지 본다. "
    md += "eval의 정답은 바꾸지 않았다.\n\n"
    md += f"#147 LLM이 정답과 다른 값으로 채운 {len(checked.llm)}칸:\n\n" + _reread_table(
        checked.llm
    )
    md += f"\n#150 정규식이 정답과 다른 값으로 채운 {len(checked.regex)}칸:\n\n"
    md += _reread_table(checked.regex)
    llm_ok, regex_ok = sum(r.same for r in checked.llm), sum(r.same for r in checked.regex)
    md += f"\n- LLM {len(checked.llm)}칸 중 PDF 값과 같은 칸 {llm_ok}\n"
    md += f"- 정규식 {len(checked.regex)}칸 중 PDF 값과 같은 칸 {regex_ok}\n"
    return md


def run_check(
    pbnos: list[str],
    raw_dir: Path,
    labels_path: Path,
    extract_new: Path,
    out: Path,
    expected: int = CELLS,
) -> Checked:
    """data/raw/<pbno>/의 detail.html·notice.pdf와 라벨 파일만 읽어 리포트를 쓴다. 요청 없음."""
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    truths = {
        p: parse_truth((raw_dir / p / "detail.html").read_text(encoding="utf-8")) for p in pbnos
    }
    texts = {p: pages(raw_dir / p / "notice.pdf") for p in pbnos}
    cells = check_cells(labels, truths, texts, expected=expected)
    md = extract_new.read_text(encoding="utf-8")
    wrong = compare.parse_llm_new(md).wrong_cells
    values = llm_values(md)
    if set(values) != wrong:
        raise ValueError("틀리게 채운 칸 표의 칸이 C안 합계가 센 칸과 다르다")
    regex, _ = compare.regex_cells(pbnos, raw_dir)
    regex_wrong = {(c.pbno, c.field): c.value for c in regex if c.state == "wrong"}
    checked = Checked(cells, reread(cells, values), reread(cells, regex_wrong))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(checked), encoding="utf-8")
    return checked
