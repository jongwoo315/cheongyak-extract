"""data/raw/를 읽기만 해서 수집된 공고와 문제가 있는 공고를 센다. 청약홈에 요청하지 않는다."""

from pathlib import Path
from typing import NamedTuple

from cheongyak_extract.fetch import pdf_links
from cheongyak_extract.pdf_text import pdf_problem


class RawScan(NamedTuple):
    dirs: int  # 공고 디렉터리 수
    collected: list[str]  # detail.html이 있고 notice.pdf가 열린다(설계 §「수집됐다」)
    unreadable: list[tuple[str, str]]  # notice.pdf가 있는데 열리지 않는다: (공고 번호, 이유)
    no_pdf: list[tuple[str, str]]  # notice.pdf가 없다: (공고 번호, 상세에 공고문 링크가 있는지)
    no_detail: list[str]  # notice.pdf는 열리는데 detail.html이 없다


def scan(raw_dir: Path) -> RawScan:
    dirs = sorted(d for d in raw_dir.iterdir() if d.is_dir()) if raw_dir.is_dir() else []
    collected: list[str] = []
    unreadable: list[tuple[str, str]] = []
    no_pdf: list[tuple[str, str]] = []
    no_detail: list[str] = []
    for d in dirs:
        detail, pdf = d / "detail.html", d / "notice.pdf"
        if pdf.exists():
            if problem := pdf_problem(pdf):
                unreadable.append((d.name, problem))
            elif detail.exists():
                collected.append(d.name)
            else:
                no_detail.append(d.name)
        elif not detail.exists():
            no_pdf.append((d.name, "detail.html 없음"))
        else:
            has_link = bool(pdf_links(detail.read_text(encoding="utf-8")))
            no_pdf.append((d.name, f"상세에 공고문 링크 {'있음' if has_link else '없음'}"))
    return RawScan(len(dirs), collected, unreadable, no_pdf, no_detail)


def _table(header: str, rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "없음\n"
    lines = [f"| 공고 | {header} |", "| --- | --- |"]
    return "\n".join(lines + [f"| {pbno} | {why} |" for pbno, why in rows]) + "\n"


def render(result: RawScan) -> str:
    md = "# data/raw 확인\n\n"
    md += f"- 공고 디렉터리 {result.dirs}개\n"
    md += f"- 수집된 공고 {len(result.collected)}건 (detail.html이 있고 notice.pdf가 열린다)\n"
    md += f"- 열리지 않는 PDF {len(result.unreadable)}건\n"
    md += f"- PDF가 없는 공고 {len(result.no_pdf)}건\n"
    if result.no_detail:
        md += f"- PDF는 열리는데 detail.html이 없는 공고 {len(result.no_detail)}건\n"
    md += "\n## 열리지 않는 PDF\n\n" + _table("이유", result.unreadable)
    md += "\n## PDF가 없는 공고\n\n" + _table("이유", result.no_pdf)
    if result.no_detail:
        md += "\n## detail.html이 없는 공고\n\n" + " ".join(result.no_detail) + "\n"
    return md


def check_raw(raw_dir: Path, out: Path) -> RawScan:
    result = scan(raw_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(result), encoding="utf-8")
    return result
