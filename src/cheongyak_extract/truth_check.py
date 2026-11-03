"""청약홈 정답(HTML)과 공고문 PDF 값을 칸마다 대조한다. 라벨 파일은 labels/pdf-values-20.json."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract import compare
from cheongyak_extract.extract import FIELDS, grounded
from cheongyak_extract.normalize import normalize
from cheongyak_extract.pdf_fields import PDF_FIELDS
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
    if not all(raw[k] is None or isinstance(raw[k], str) for k in ("value", "quote", "note")):
        raise ValueError(f"{where}: value·quote·note는 문자열이거나 null이어야 한다")
    page = raw["page"]
    if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
        raise ValueError(f"{where}: page는 1 이상의 정수이거나 null이어야 한다")
    if any(raw[k] is not None and not raw[k].strip() for k in ("value", "quote")):
        raise ValueError(f"{where}: 값이 없으면 빈 문자열이 아니라 null로 적는다")
    has_value, has_quote = raw["value"] is not None, raw["quote"] is not None
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
    if not isinstance(labels, dict):
        raise ValueError("라벨 파일의 맨 위는 공고번호를 키로 하는 객체여야 한다")
    out: list[Cell] = []
    for pbno in truths:
        got = labels.get(pbno)
        if got is None:
            raise ValueError(f"{pbno}: 라벨에 이 공고가 없다")
        if not isinstance(got, dict):
            raise ValueError(f"{pbno}: 공고의 라벨은 필드를 키로 하는 객체여야 한다")
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
    for line in part[1].split("\n"):  # splitlines()는 \r·\x0c 같은 글자에서도 잘라 추출값이 끊긴다
        if not re.match(r"\| \d{10} \| ", line):
            continue
        cols = re.split(r"(?<!\\) \| ", line.removeprefix("| ").removesuffix(" |"))
        if len(cols) != 6:
            raise ValueError(f"틀리게 채운 칸 표의 열이 {len(cols)}개다. 6개여야 한다: {line[:60]}")
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


# ---- #153: 어느 쪽이 맞는지 jw가 판정할 칸 ----

JUDGES = ("HTML", "PDF", "둘 다", "둘 다 아님")  # jw 칸이 받는 값. 비어 있으면 null
PENDING = "판정 전"
_JUDGE_KEYS = {"pbno", "field", "html", "pdf", "quote", "page", "llm", "jw", "jw_note"}


def pick_cells(cells: list[Cell], llm: dict[tuple[str, str], str | None]) -> list[dict]:
    """HTML 값·PDF 값·LLM 값이 정규화 뒤 하나라도 다른 칸을 판정 파일 꼴로 낸다.

    llm은 틀리게 채운 칸 표의 추출값이다. 표에 없는 칸은 HTML 값과 같다고 본다.
    """
    out = []
    for c in cells:
        value = llm.get((c.pbno, c.field), c.html)
        if len({normalize(c.field, v) for v in (c.html, c.pdf, value)}) == 1:
            continue
        out.append(
            {
                "pbno": c.pbno,
                "field": c.field,
                "html": c.html,
                "pdf": c.pdf,
                "quote": c.quote,
                "page": c.page,
                "llm": value,
                "jw": None,
                "jw_note": None,
            }
        )
    return out


def _check_judge_row(i: int, row: object) -> dict:
    where = f"판정 파일 {i + 1}번째 칸"
    if not isinstance(row, dict) or set(row) != _JUDGE_KEYS:
        raise ValueError(f"{where}: {sorted(_JUDGE_KEYS)} 키를 모두 가진 객체여야 한다")
    where = f"{row['pbno']} {row['field']}"
    if not all(isinstance(row[k], str) for k in ("pbno", "field")):
        raise ValueError(f"{where}: pbno·field는 문자열이어야 한다")
    for k in ("html", "pdf", "quote", "llm", "jw_note"):
        if row[k] is not None and not isinstance(row[k], str):
            raise ValueError(f"{where}: {k}는 문자열이거나 null이어야 한다")
    page = row["page"]
    if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
        raise ValueError(f"{where}: page는 1 이상의 정수이거나 null이어야 한다")
    jw = row["jw"]
    if jw is not None and not (isinstance(jw, str) and jw in JUDGES):
        raise ValueError(
            f"{where}: jw는 {' / '.join(JUDGES)} 중 하나이거나 null이어야 한다: {jw!r}"
        )
    return row


def load_judge(path: Path) -> list[dict]:
    """판정 파일을 읽고 칸마다 형식과 jw 값을 검사한다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("판정 파일의 맨 위는 칸 목록이어야 한다")
    return [_check_judge_row(i, row) for i, row in enumerate(raw)]


def _key(r: dict) -> tuple[str, str]:
    return r["pbno"], r["field"]


def merge_judge(picked: list[dict], filed: list[dict] | None) -> list[dict]:
    """이번에 고른 칸에 파일에 적힌 jw·jw_note를 얹는다. 파일이 없으면 고른 칸 그대로다.

    jw가 채운 칸을 덮어쓰지 않는다. 고른 칸이 파일과 다르거나, 같은 칸의 HTML 값·PDF 값·근거 줄·쪽·
    LLM 값이 jw가 본 값과 다르면 말없이 붙이지 않고 에러를 낸다.
    """
    if filed is None:
        return picked
    seen = Counter(_key(r) for r in filed)
    if dup := sorted(f"{p} {f}" for (p, f), n in seen.items() if n > 1):
        raise ValueError(f"판정 파일에 같은 칸이 두 번 있다: {dup}")
    now, before = {_key(r) for r in picked}, {_key(r) for r in filed}
    if now != before:
        diff = sorted(f"{p} {f}" for p, f in now ^ before)
        raise ValueError(f"판정 파일의 칸이 이번에 고른 칸과 다르다: {diff}")
    saved = {_key(r): r for r in filed}
    for r in picked:
        for k in ("html", "pdf", "quote", "page", "llm"):
            if saved[_key(r)][k] != r[k]:
                raise ValueError(
                    f"{r['pbno']} {r['field']}: jw가 본 {k} 값이 이번에 읽은 값과 다르다. "
                    f"jw 판정을 새 값에 붙이지 않는다(파일 {saved[_key(r)][k]!r}, 이번 {r[k]!r})"
                )
    return [{**r, "jw": saved[_key(r)]["jw"], "jw_note": saved[_key(r)]["jw_note"]} for r in picked]


def missing_material(row: dict) -> bool:
    """jw가 판정할 재료(HTML 값·PDF 값·근거 줄·쪽·LLM 값) 중 비어 있는 것이 있다."""
    return any(row[k] is None for k in ("html", "pdf", "quote", "page", "llm"))


def ungrounded_judge(rows: list[dict], texts: dict[str, list[str]]) -> list[dict]:
    """근거 줄이 있는데 적힌 쪽 텍스트에서 못 찾은 칸. 근거 줄 자체가 없는 칸은 여기 안 센다."""
    out = []
    for r in rows:
        if r["quote"] is None:
            continue
        body = texts[r["pbno"]]
        if not (r["page"] is not None and 1 <= r["page"] <= len(body)):
            out.append(r)
        elif not grounded(r["quote"], body[r["page"] - 1]):
            out.append(r)
    return out


# #152 리포트에서 옮긴 숫자. (필드, 정답 있는 칸, LLM이 맞힌 칸, 출처, 대상).
# 정답은 구현 루프가 PDF를 읽고 적었다
_PDF_ONLY_SOURCES = (
    ("전매제한 기간", 47, 47, "reports/pdf-fields-tune-2.md", "기존 50건"),
    ("거주지 우선 비율", 49, 48, "reports/pdf-fields-tune-2.md", "기존 50건"),
    ("거주지 우선 비율", 30, 29, "reports/pdf-resident-test.md", "새 30건"),
    ("신혼부부 소득 기준", 46, 42, "reports/pdf-fields-tune-2.md", "기존 50건"),
)


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


def _load(
    pbnos: list[str], raw_dir: Path, labels_path: Path, extract_new: Path, expected: int
) -> tuple[list[Cell], dict[str, list[str]], dict[tuple[str, str], str | None]]:
    """칸 목록, 공고별 쪽 텍스트, extract_new의 LLM 추출값을 파일에서만 읽는다."""
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
        raise ValueError(
            "틀리게 채운 칸 표를 두 방식으로 읽은 결과가 다르다(행이 빠졌거나 표 서식이 바뀌었다)"
        )
    return cells, texts, values


def run_check(
    pbnos: list[str],
    raw_dir: Path,
    labels_path: Path,
    extract_new: Path,
    out: Path,
    expected: int = CELLS,
) -> Checked:
    """data/raw/<pbno>/의 detail.html·notice.pdf, 라벨 파일, extract_new(LLM 결과)만 읽는다.

    요청은 없다. 정규식 결과는 data/raw/의 PDF 텍스트로 다시 뽑는다.
    """
    cells, _, values = _load(pbnos, raw_dir, labels_path, extract_new, expected)
    regex, skipped = compare.regex_cells(pbnos, raw_dir)
    if skipped:  # 건너뛴 공고의 칸이 말없이 빠지면 합계 줄이 실제보다 작게 나온다
        raise ValueError(f"정규식이 건너뛴 공고가 있다: {skipped}")
    regex_wrong = {(c.pbno, c.field): c.value for c in regex if c.state == "wrong"}
    checked = Checked(cells, reread(cells, values), reread(cells, regex_wrong))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(checked), encoding="utf-8")
    return checked


def render_judge(
    rows: list[dict],
    total_cells: int,
    bad: list[dict],
    fields: tuple[str, ...] = FIELDS,
) -> str:
    """rows는 jw 칸까지 채운 판정할 칸, bad는 근거 줄을 못 찾은 칸이다."""
    same = total_cells - len(rows)
    done = {j: sum(r["jw"] == j for r in rows) for j in JUDGES}
    pending = sum(r["jw"] is None for r in rows)
    md = "# 청약홈 HTML과 공고문 PDF 중 어느 쪽 값이 맞는지\n\n"
    md += "HTML 값은 상세 HTML(`truth.parse_truth`), PDF 값은 `labels/pdf-values-20.json`, "
    md += "LLM 값은 `reports/extract-new.md`의 틀리게 채운 칸 표다. "
    md += "표에 없는 칸은 HTML 값과 같다고 본다. "
    md += "청약홈과 OpenAI에 요청하지 않았다.\n\n"
    md += "가정: 세 값이 모두 같은 칸은 두 방식 모두 맞다고 본다. "
    md += f"이 가정이 들어간 칸은 같은 칸 {same}/{total_cells}이다.\n\n"
    if pending:
        md += f"**jw 판정 전.** `판정 전` {pending}칸이 남아 있어 방식별 합계를 쓰지 않는다. "
        md += "`labels/source-judge.json`의 `jw` 칸을 채운 뒤 `judge-source`를 다시 돌린다.\n\n"
    md += f"- 같은 칸 {_pct(same, total_cells)}\n"
    md += f"- 판정할 칸 {_pct(len(rows), total_cells)}\n"
    md += (
        f"- 재료(HTML 값·PDF 값·근거 줄·쪽·LLM 값)가 빠진 칸: {sum(map(missing_material, rows))}\n"
    )
    md += f"- 근거 줄을 그 쪽에서 못 찾은 칸: {len(bad)}\n\n"
    md += "## 판정할 칸\n\n"
    md += (
        _table(
            ("공고", "필드", "HTML 값", "PDF 값", "쪽", "LLM 값", "jw 판정"),
            [
                (
                    r["pbno"],
                    r["field"],
                    r["html"],
                    r["pdf"],
                    r["page"],
                    r["llm"],
                    r["jw"] or PENDING,
                )
                for r in rows
            ],
        )
        if rows
        else "없음\n"
    )
    md += "\n필드별 판정할 칸:\n\n"
    md += _table(("필드", "판정할 칸"), [(f, sum(r["field"] == f for r in rows)) for f in fields])
    if bad:
        md += "\n근거 줄을 그 쪽에서 못 찾은 칸:\n\n"
        md += _table(
            ("공고", "필드", "쪽", "quote"),
            [(r["pbno"], r["field"], r["page"], r["quote"]) for r in bad],
        )
    md += "\n## jw 판정별 칸 수\n\n"
    md += _table(("jw 판정", "칸 수"), [*done.items(), (PENDING, pending)])
    if not pending:
        md += "\n방식별로 맞는 값을 가진 칸(같은 칸 + 그 방식이거나 `둘 다`로 판정한 칸):\n\n"
        for name in ("HTML", "PDF"):
            n = same + done[name] + done["둘 다"]
            md += f"- {name} 쪽이 맞는 값을 가진 칸: {_pct(n, total_cells)}\n"
        md += "- `둘 다 아님`은 어느 쪽에도 세지 않는다\n"
    only = [f for f in PDF_FIELDS if f not in FIELDS]
    md += "\n## HTML에 없는 필드\n\n"
    md += f"{len(only)}개 필드({', '.join(only)})는 HTML 쪽 값이 없다"
    md += f"(`truth.parse_truth`가 읽는 필드 {len(FIELDS)}개에 없다). "
    md += "그래서 위 판정할 칸에 들어갈 수 없고, PDF 쪽 숫자만 #152 리포트에서 옮긴다. "
    md += "정답은 jw가 아니라 구현 루프가 PDF를 읽고 적었다.\n\n"
    md += _table(
        ("필드", "정답 있는 칸", "LLM이 맞힌 칸", "대상", "출처"),
        [(f, n, ok, which, src) for f, n, ok, src, which in _PDF_ONLY_SOURCES],
    )
    return md


class Judged(NamedTuple):
    rows: list[dict]  # 판정할 칸(jw 칸까지)
    total: int  # 대조한 전체 칸
    bad: list[dict]  # 근거 줄을 그 쪽에서 못 찾은 칸


def run_judge(
    pbnos: list[str],
    raw_dir: Path,
    labels_path: Path,
    extract_new: Path,
    judge_path: Path,
    out: Path,
    expected: int = CELLS,
) -> Judged:
    """판정할 칸을 골라 judge_path에 없으면 만들고, 있으면 jw 칸을 그대로 읽어 리포트를 쓴다.

    data/raw/, 라벨 파일, extract_new만 읽는다. 청약홈과 OpenAI에 요청하지 않는다.
    """
    cells, texts, values = _load(pbnos, raw_dir, labels_path, extract_new, expected)
    picked = pick_cells(cells, values)
    exists = judge_path.exists()
    rows = merge_judge(picked, load_judge(judge_path) if exists else None)
    if not exists:
        judge_path.parent.mkdir(parents=True, exist_ok=True)
        judge_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    bad = ungrounded_judge(rows, texts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_judge(rows, len(cells), bad), encoding="utf-8")
    return Judged(rows, len(cells), bad)
