"""수집 -> PDF 텍스트 -> 추출 -> 정답 파싱 -> 리포트를 한 번에 잇는다."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import httpx

from cheongyak_extract.extract import FIELDS, extract
from cheongyak_extract.fetch import LIST_URL, PAUSE_SECONDS, Skipped, download, parse_list
from cheongyak_extract.pdf_text import pages
from cheongyak_extract.report import Doc, FieldMetrics, metrics, render_markdown
from cheongyak_extract.truth import parse_truth


class Result(NamedTuple):
    metrics: list[FieldMetrics]
    processed: int
    skipped: list[tuple[str, str]]  # (pblancNo, 이유)


def run(
    n: int,
    client: httpx.Client,
    raw_dir: Path,
    report_path: Path,
    pause: Callable[[float], None] = time.sleep,
) -> Result:
    pause(PAUSE_SECONDS)
    listing = client.get(LIST_URL)
    listing.raise_for_status()

    docs: list[Doc] = []
    skipped: list[tuple[str, str]] = []
    for hmno, pbno, honm in parse_list(listing.text):
        if len(docs) == n:
            break
        try:
            out = download(client, hmno, pbno, honm, raw_dir, pause)
        except Skipped as e:
            skipped.append((pbno, str(e)))
            continue
        except httpx.HTTPError as e:
            skipped.append((pbno, f"다운로드 실패: {e}"))
            continue
        text = pages(out / "notice.pdf")
        truth = parse_truth((out / "detail.html").read_text(encoding="utf-8"))
        docs.append(Doc(pbno, truth, extract(text), text))

    rows = metrics(docs, FIELDS)
    md = f"# skeleton 리포트\n\n공고 {len(docs)}건: {', '.join(d.pbno for d in docs)}\n\n"
    md += render_markdown(rows)
    if skipped:
        md += "\n건너뛴 공고:\n\n" + "".join(f"- {pbno}: {why}\n" for pbno, why in skipped)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    print(md)
    return Result(rows, len(docs), skipped)
