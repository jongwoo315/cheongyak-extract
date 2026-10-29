"""정규식과 LLM을 같은 칸에서 나란히 놓은 reports/regex-vs-llm.md를 만든다.

LLM 숫자는 커밋된 리포트(extract-new.md, extract-tune.md)를 읽어 온다. 손으로 옮기지 않고
OpenAI도 부르지 않는다. 정규식 숫자는 같은 규칙으로 다시 세고 reports/regex-*.md의 합계와 맞춰 본다.
"""

import re
from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.extract import FIELDS
from cheongyak_extract.pipeline import SkipDoc, _analyze
from cheongyak_extract.report import _state

RAW_DIR = Path("data/raw")
REPORTS = Path("reports")


class Counts(NamedTuple):
    total: int  # 정답 있는 칸
    right: int
    blank: int
    wrong: int  # 다른 값으로 채움


class Cell(NamedTuple):
    pbno: str
    field: str
    state: str  # right / blank / wrong
    value: str | None
    truth: str | None


class LlmNew(NamedTuple):
    counts: Counts
    right_by_field: dict[str, tuple[int, int]]  # 필드 -> (정답 있는 칸, 맞은 칸)
    wrong_cells: set[tuple[str, str]]  # (공고, 필드). 이 밖의 칸은 맞음이다


def _need(m: re.Match[str] | None, what: str) -> re.Match[str]:
    if m is None:
        raise ValueError(f"리포트에서 {what}을(를) 못 찾았다. 리포트 형식이 바뀌었는지 본다")
    return m


def _counts(total: str, right: str, blank: str, wrong: str) -> Counts:
    return Counts(int(total), int(right), int(blank), int(wrong))


def parse_llm_new(md: str) -> LlmNew:
    """extract-new.md의 C안 합계 줄, 필드별 C안 맞음, 틀리게 채운 칸 표."""
    row = _need(
        re.search(
            r"^\| C \| (\d+) \| (\d+) \(\d+%\) \| (\d+) \(\d+%\) \| (\d+) \(\d+%\) \|", md, re.M
        ),
        "C안 합계 줄",
    )
    by_field = {
        m[1]: (int(m[2]), int(m[3]))
        for m in re.finditer(
            r"^\| ([^|]+) \| (\d+) \| \d+ \(\d+%\) \| \d+ \(\d+%\) \| (\d+) \(\d+%\) \|$", md, re.M
        )
    }
    if not by_field:
        raise ValueError("리포트에서 필드별 맞은 칸 표를 못 찾았다")
    wrong_part = _need(re.search(r"틀리게 채운 칸:\n(.*?)\n토큰:", md, re.S), "틀리게 채운 칸 표")[
        1
    ]
    wrong = {(m[1], m[2]) for m in re.finditer(r"^\| (\d{10}) \| ([^|]+) \|", wrong_part, re.M)}
    counts = _counts(*row.groups())
    # 표에 없는 칸을 맞음으로 읽으므로 비움이 있거나 틀린 칸 수가 어긋나면 읽을 수 없다
    if counts.blank or len(wrong) != counts.wrong:
        raise ValueError(
            f"틀리게 채운 칸 표({len(wrong)}칸)가 "
            f"C안 합계(비움 {counts.blank}, 틀림 {counts.wrong})와 안 맞는다"
        )
    return LlmNew(counts, by_field, wrong)


def parse_llm_tune(md: str) -> Counts:
    """extract-tune.md `## 수정마다 한 줄` 표의 마지막 C안 줄."""
    section = _need(
        re.search(r"## 수정마다 한 줄\n(.*?)(?:\n## |\Z)", md, re.S), "수정마다 한 줄 표"
    )[1]
    rows = re.findall(
        r"^\| \d+ \|[^|]*\| C \| (\d+) \([\d.]+%\) \| (\d+) \([\d.]+%\) \| (\d+) \([\d.]+%\) \|$",
        section,
        re.M,
    )
    if not rows:
        raise ValueError("리포트에서 C안 줄을 못 찾았다")
    right, blank, wrong = map(int, rows[-1])
    return Counts(right + blank + wrong, right, blank, wrong)


def parse_regex_summary(md: str) -> Counts:
    """eval 리포트의 `정답 있는 칸 N · 맞음 N · 비움 N · 틀리게 채움 N` 줄."""
    m = _need(
        re.search(r"정답 있는 칸 (\d+) · 맞음 (\d+) · 비움 (\d+) · 틀리게 채움 (\d+)", md),
        "합계 줄",
    )
    return _counts(*m.groups())


def parse_regex_tune_last(md: str) -> Counts:
    """regex-tune.md 수정 표의 마지막 줄."""
    rows = re.findall(
        r"^\| \d+ \|[^|]*\| (\d+) \([\d.]+%\) \| (\d+) \([\d.]+%\) \| (\d+) \([\d.]+%\) \|$",
        md,
        re.M,
    )
    if not rows:
        raise ValueError("리포트에서 수정 표를 못 찾았다")
    right, blank, wrong = map(int, rows[-1])
    return Counts(right + blank + wrong, right, blank, wrong)


def parse_pbnos(md: str) -> list[str]:
    """eval 리포트에서 처리한 공고와 건너뛴 공고를 모두 읽는다."""
    head = _need(re.search(r"^공고 \d+건: (.+)$", md, re.M), "공고 목록")[1]
    skipped = re.findall(r"^- (\d{10}): ", md, re.M)
    return [*head.split(", "), *skipped]


def regex_cells(
    pbnos: list[str], raw_dir: Path = RAW_DIR
) -> tuple[list[Cell], list[tuple[str, str]]]:
    """정규식으로 뽑아 정답이 있는 칸의 상태를 센다. (칸들, 건너뛴 공고와 이유)."""
    cells: list[Cell] = []
    skipped: list[tuple[str, str]] = []
    for pbno in pbnos:
        try:
            doc = _analyze(pbno, raw_dir / pbno, None)
        except SkipDoc as e:
            skipped.append((pbno, str(e)))
            continue
        for f in FIELDS:
            if state := _state(f, doc):
                cells.append(Cell(pbno, f, state, doc.extracted[f].value, doc.truth[f]))
    return cells, skipped


def count(cells: list[Cell]) -> Counts:
    states = [c.state for c in cells]
    return Counts(len(cells), states.count("right"), states.count("blank"), states.count("wrong"))


def cross(cells: list[Cell], llm_wrong: set[tuple[str, str]]) -> dict[str, list[Cell]]:
    """같은 칸에서 정규식과 LLM의 맞음·틀림을 가른다. LLM은 llm_wrong 밖이 맞음이다."""
    out: dict[str, list[Cell]] = {
        "정규식 맞음, LLM 틀림": [],
        "정규식 틀림, LLM 맞음": [],
        "둘 다 틀림": [],
        "둘 다 맞음": [],
    }
    for c in cells:
        regex_ok = c.state == "right"
        llm_ok = (c.pbno, c.field) not in llm_wrong
        key = {
            (True, False): "정규식 맞음, LLM 틀림",
            (False, True): "정규식 틀림, LLM 맞음",
            (False, False): "둘 다 틀림",
            (True, True): "둘 다 맞음",
        }[(regex_ok, llm_ok)]
        out[key].append(c)
    return out


def _pct(n: int, total: int) -> str:
    return f"{n} ({n / total:.1%})" if total else f"{n} (—)"


def _row(label: str, c: Counts) -> str:
    cols = (c.total, _pct(c.right, c.total), _pct(c.blank, c.total), _pct(c.wrong, c.total))
    return f"| {label} | " + " | ".join(map(str, cols)) + " |"


_HEAD = (
    "| 추출 | 정답 있는 칸 | 맞음 | 비움 | 다른 값으로 채움 |\n| --- | --- | --- | --- | --- |\n"
)
_STATE = {"right": "맞음", "blank": "비움", "wrong": "다른 값으로 채움"}


def _rate(c: Counts) -> float:
    return c.right / c.total if c.total else 0.0


def _gap(label_a: str, a: Counts, label_b: str, b: Counts) -> str:
    diff = (_rate(a) - _rate(b)) * 100
    return f"| {label_a} {_rate(a):.2%} − {label_b} {_rate(b):.2%} | {diff:+.2f}%p |\n"


def _by_field(cells: list[Cell], fields: tuple[str, ...]) -> dict[str, tuple[int, int]]:
    return {
        f: (
            sum(c.field == f for c in cells),
            sum(c.field == f and c.state == "right" for c in cells),
        )
        for f in fields
    }


def _cell_md(v: str | None) -> str:
    return (v or "—").replace("|", "\\|").replace("\n", " ")


def _share(right: int, n: int) -> str:
    return f"{right} ({right / n:.0%})" if n else f"{right} (—)"


def _field_table(
    cells: list[Cell], fields: tuple[str, ...], llm: dict[str, tuple[int, int]] | None = None
) -> str:
    head = "| 필드 | 정답 있는 칸 | 정규식 맞음 |" + (" LLM 맞음 |" if llm else "")
    md = head + "\n" + "| --- " * (head.count("|") - 1) + "|\n"
    for f, (n, right) in _by_field(cells, fields).items():
        row = f"| {f} | {n} | {_share(right, n)} |"
        if llm:
            ln, lright = llm[f]
            row += f" {_share(lright, ln)} |"
        md += row + "\n"
    return md


def render(
    new: list[Cell],
    llm_new: LlmNew,
    tune: list[Cell],
    llm_tune: Counts,
    more: list[Cell],
    more_skipped: list[tuple[str, str]],
    fields: tuple[str, ...] = FIELDS,
) -> str:
    r_new, r_tune, r_more = count(new), count(tune), count(more)
    n_more = len({c.pbno for c in more})
    md = "# 정규식 baseline과 LLM 비교\n\n"
    md += (
        "LLM 숫자는 커밋된 리포트 `reports/extract-new.md`·`reports/extract-tune.md`에서 읽었다. "
        "LLM을 다시 부르지 않았고 OpenAI API를 쓰지 않았다. 정규식 숫자는 규칙을 고정한 뒤 "
        "`reports/regex-new.md`·`regex-tune.md`·`regex-more.md`와 같은 규칙으로 센 값이다. "
        "칸은 공고 하나 × 필드 하나이고 청약홈 정답이 있는 칸만 센다.\n\n"
    )
    md += "## 1. 재는 공고 20건\n\n" + _HEAD
    md += _row("정규식", r_new) + "\n" + _row("LLM(T0, C안)", llm_new.counts) + "\n\n"
    md += "## 2. 필드별 맞은 칸 (재는 공고 20건)\n\n"
    md += _field_table(new, fields, llm_new.right_by_field)
    md += "\n## 3. 다듬는 공고 29건\n\n"
    md += "정규식은 규칙을 고정한 뒤(수정 3) 값이다. "
    md += "LLM은 `reports/extract-tune.md` 마지막 C안 줄이다.\n\n"
    md += _HEAD + _row("정규식", r_tune) + "\n" + _row("LLM(T0, C안)", llm_tune) + "\n\n"
    got = cross(new, llm_new.wrong_cells)
    md += "## 4. 칸마다 갈린 곳 (재는 공고 20건)\n\n"
    md += (
        "LLM 칸 상태는 `extract-new.md`의 「틀리게 채운 칸」 표에 있는 칸이 다른 값으로 채움이고 "
        "나머지는 맞음이다. 틀림은 맞음이 아닌 칸(비움 또는 다른 값으로 채움)이다.\n\n"
    )
    md += "| 구분 | 칸 수 |\n| --- | --- |\n"
    md += "".join(f"| {k} | {len(v)} |\n" for k, v in got.items())
    for key in ("정규식 맞음, LLM 틀림", "정규식 틀림, LLM 맞음", "둘 다 틀림"):
        md += f"\n{key} ({len(got[key])}칸):\n\n"
        if not got[key]:
            md += "없음\n"
            continue
        md += "| 공고 | 필드 | 정규식 | 정규식 추출값 | 정답 |\n| --- | --- | --- | --- | --- |\n"
        for c in got[key]:
            md += f"| {c.pbno} | {c.field} | {_STATE[c.state]} | "
            md += f"{_cell_md(c.value)} | {_cell_md(c.truth)} |\n"
    md += "\n## 5. 규칙을 다듬은 공고와 안 본 공고의 차이 (맞은 칸 비율)\n\n"
    md += "| 비교 | 값 |\n| --- | --- |\n"
    md += _gap("정규식 다듬는 29건", r_tune, "재는 20건", r_new)
    md += _gap(f"정규식 남은 {n_more}건", r_more, "재는 20건", r_new)
    md += _gap("LLM 다듬는 29건", llm_tune, "재는 20건", llm_new.counts)
    md += f"\n## 6. 남은 공고 {n_more + len(more_skipped)}건 중 {n_more}건 (정규식만, LLM 없음)\n\n"
    md += "남은 공고에는 LLM 결과가 없어 비교하지 않는다. "
    md += "규칙이 다듬는 공고에만 맞춰졌는지 보는 참고 숫자다.\n\n"
    md += _HEAD + _row("정규식", r_more) + "\n\n" + _field_table(more, fields)
    if more_skipped:
        md += "\n건너뛴 공고:\n\n" + "".join(f"- {p}: {why}\n" for p, why in more_skipped)
    return md


def _read(name: str) -> str:
    return (REPORTS / name).read_text(encoding="utf-8")


def _same(label: str, cells: list[Cell], report: Counts) -> None:
    if count(cells) != report:
        raise SystemExit(f"{label}: 다시 센 값 {count(cells)}이 리포트 합계 {report}와 다르다")


def main() -> int:
    llm_new = parse_llm_new(_read("extract-new.md"))
    llm_tune = parse_llm_tune(_read("extract-tune.md"))
    new, _ = regex_cells(parse_pbnos(_read("extract-new.md")))
    tune, _ = regex_cells(parse_pbnos(_read("extract-tune-0.md")))
    more, more_skipped = regex_cells(parse_pbnos(_read("regex-more.md")))
    if llm_new.counts.total != count(new).total:
        raise SystemExit(
            f"LLM 칸 {llm_new.counts.total}개와 정규식 칸 {count(new).total}개가 다르다"
        )
    _same("재는 20건", new, parse_regex_summary(_read("regex-new.md")))
    _same("다듬는 29건", tune, parse_regex_tune_last(_read("regex-tune.md")))
    _same("남은 건", more, parse_regex_summary(_read("regex-more.md")))
    md = render(new, llm_new, tune, llm_tune, more, more_skipped)
    (REPORTS / "regex-vs-llm.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
