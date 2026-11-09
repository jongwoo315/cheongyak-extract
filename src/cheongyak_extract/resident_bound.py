"""거주지 묶음 고르기(`resident_block`)가 149건에서 무엇을 고르는지 재고, 두 코드의 값을 비교한다.

청약홈·OpenAI를 부르지 않는다. `data/raw`의 PDF만 읽는다.
"""

import json
from pathlib import Path

from cheongyak_extract import pdf_fields as pf
from cheongyak_extract.pdf_text import pages as pdf_pages


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
