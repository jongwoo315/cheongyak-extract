"""거주지 묶음 고르기(`resident_block`)가 149건에서 무엇을 고르는지 재고, 두 코드의 값을 비교한다.

청약홈·OpenAI를 부르지 않는다. `data/raw`의 PDF만 읽는다.
"""

import json
from pathlib import Path

from cheongyak_extract import pdf_fields as pf
from cheongyak_extract.pdf_text import pages as pdf_pages
from cheongyak_extract.report import _table


def _text_lines(text: str) -> int:
    return sum(bool(line.strip()) for line in text.split("\n"))


def snap(texts: dict[str, list[str]]) -> dict[str, dict]:
    """공고마다 고른 묶음의 규칙·쪽·글자 수·글이 든 줄 수·본문. 묶음이 없으면 rule은 None."""
    out: dict[str, dict] = {}
    for pbno, pages in sorted(texts.items()):
        block = pf.resident_block(pages)
        out[pbno] = (
            {"rule": None, "page": None, "chars": 0, "lines": 0, "text": ""}
            if block is None
            else {
                "rule": block.rule,
                "page": block.page,
                "chars": len(block.text),
                "lines": _text_lines(block.text),
                "text": block.text,
            }
        )
    return out


def snapshot(raw_dir: Path, out: Path) -> dict[str, dict]:
    """149건(`eligible_pbnos`)을 지금 코드로 재서 JSON으로 쓴다."""
    texts = {p: pdf_pages(raw_dir / p / "notice.pdf") for p in pf.eligible_pbnos(raw_dir)}
    got = snap(texts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return got


CAP = 5  # 규칙 1 묶음의 글이 든 줄 상한(통과 기준 1)
MUST_KEEP = {  # 상한에 걸려도 묶음에 남아야 하는 줄(실패 징후 1)
    "2026000310": "①지역 : 해당지역 거주자(남양주시",
    "2026000293": "해당지역 거주자 (강릉시 6개월 이상",
}
RULE_NAME = {1: "규칙 1", 2: "규칙 2", 3: "규칙 3", None: "전체"}


def _squash(text: str) -> str:
    return " ".join(text.split())  # PDF 줄의 공백 수가 달라도 같은 줄로 본다


def _same(a: dict, b: dict) -> bool:
    return all(a[k] == b[k] for k in ("rule", "page", "text"))


def _shape(v: dict) -> str:
    where = f"{RULE_NAME[v['rule']]} {v['page']}쪽" if v["rule"] else "전체"
    return f"{where} · {v['chars']}자 · {v['lines']}줄" if v["rule"] else where


def _sentence_place(pages: list[str], block: pf.Block) -> tuple[int, int] | None:
    """규칙 3 묶음의 첫 줄이 있는 (쪽, 줄). 제목 줄과 같은 쪽이면 제목 줄 아래만 본다."""
    first = block.text.split("\n")[0].strip()
    title = pf.general_title(pages)
    lines = pages[block.page - 1].split("\n")
    for i, line in enumerate(lines, start=1):
        if line.strip() == first and (title is None or (block.page, i) > title):
            return block.page, i
    return None


def compare(before: dict[str, dict], texts: dict[str, list[str]], commands: str, base: str) -> str:
    """main 쪽 값(before)과 지금 코드의 값을 공고마다 비교한 리포트(통과 기준 6, 실패 징후 1·2)."""
    after = snap(texts)
    changed = [p for p in after if not _same(before[p], after[p])]
    out = ["# 거주지 묶음 규칙 1 상한·규칙 3 일반공급 절 한정 — 149건 비교 (#184)", ""]
    out += ["재현:", "", "```", commands, "```", ""]
    out += [
        f"비교 기준: main(`{base}`)의 `reports/resident-bound-before.json`. "
        "청약홈·OpenAI 요청 없음.",
        "",
    ]
    out += [f"공고 {len(after)}건 중 묶음(규칙·쪽·본문)이 바뀐 공고 {len(changed)}건.", ""]
    rows = [
        (
            name,
            sum(v["rule"] == r for v in before.values()),
            sum(v["rule"] == r for v in after.values()),
        )
        for r, name in RULE_NAME.items()
    ]
    out += [_table(("고른 규칙", "main 공고 수", "이 브랜치 공고 수"), rows)]
    out += ["## 바뀐 공고", ""]
    out += [
        _table(
            ("공고", "main", "이 브랜치"),
            [(p, _shape(before[p]), _shape(after[p])) for p in changed],
        )
    ]

    over = [p for p, v in after.items() if v["rule"] == 1 and v["lines"] > CAP]
    cut = [p for p in changed if before[p]["rule"] == 1 == after[p]["rule"]]
    out += ["## 실패 징후 1 — 규칙 1 길이 상한", ""]
    out += [f"- 규칙 1 묶음 중 글이 든 줄이 {CAP}개를 넘는 묶음: {len(over)}건 {' '.join(over)}"]
    out += [f"- 상한에 걸려 잘린 공고: {len(cut)}건 {' '.join(cut)}".rstrip()]
    for p, need in MUST_KEEP.items():
        if p not in after:
            continue
        kept = _squash(need) in _squash(after[p]["text"])
        out += [
            f"- {p} 묶음에 「{need}」 줄이 남았나(공백 수는 무시): {'예' if kept else '아니오'}"
        ]
    out += [""]
    for p in cut:
        out += [f"잘린 묶음 전문 — {p} ({_shape(before[p])} → {_shape(after[p])})", "", "```"]
        out += [after[p]["text"], "```", ""]

    out += ["## 실패 징후 2 — 규칙 3 문장의 위치", ""]
    rows3 = []
    for p in sorted(p for p in after if after[p]["rule"] == 3 or before[p]["rule"] == 3):
        t = pf.general_title(texts[p])
        title = "없음"
        if t:
            title = f"{t[0]}쪽 {t[1]}줄 「{texts[p][t[0] - 1].split(chr(10))[t[1] - 1].strip()}」"
        block = pf.resident_block(texts[p])
        place = _sentence_place(texts[p], block) if block and block.rule == 3 else None
        below = "예" if place and t and place > t else "아니오"
        sent = f"{place[0]}쪽 {place[1]}줄" if place else "—"
        text = block.text.split("\n")[0].strip() if block and block.rule == 3 else "—"
        rows3.append(
            (p, RULE_NAME[before[p]["rule"]], RULE_NAME[after[p]["rule"]], title, sent, below, text)
        )
    out += [
        _table(
            (
                "공고",
                "main 규칙",
                "지금 규칙",
                "첫 일반공급 절 제목 줄",
                "고른 문장",
                "제목 줄 아래",
                "문장 첫 줄",
            ),
            rows3,
        )
    ]
    whole = [p for p, v in after.items() if v["rule"] is None]
    out += [f"PDF 전체를 넘기는 공고: {len(whole)}/{len(after)} {' '.join(whole)}".rstrip(), ""]
    return "\n".join(line.rstrip() for line in "\n".join(out).split("\n"))


def report(raw_dir: Path, before: Path, out: Path, commands: str, base: str) -> str:
    texts = {p: pdf_pages(raw_dir / p / "notice.pdf") for p in pf.eligible_pbnos(raw_dir)}
    md = compare(json.loads(before.read_text(encoding="utf-8")), texts, commands, base)
    out.write_text(md, encoding="utf-8")
    return md
