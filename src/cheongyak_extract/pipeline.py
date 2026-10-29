"""수집 -> PDF 텍스트 -> 추출 -> 정답 파싱 -> 리포트를 한 번에 잇는다."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import httpx

from cheongyak_extract.extract import DEFAULT_RULE, FIELDS, Ask, extract_rules
from cheongyak_extract.fetch import LIST_URL, PAUSE_SECONDS, Skipped, download, parse_list
from cheongyak_extract.llm import BadResponse, ContextExceeded
from cheongyak_extract.pdf_text import pages
from cheongyak_extract.report import (
    Doc,
    FieldMetrics,
    metrics,
    render_field_rates,
    render_markdown,
    render_mode_table,
    render_rule_table,
    render_shape_errors,
    render_summary,
    render_token_ratio,
    render_usage,
    render_wrong,
)
from cheongyak_extract.truth import parse_truth


class Result(NamedTuple):
    metrics: list[FieldMetrics]
    processed: int
    skipped: list[tuple[str, str]]  # (pblancNo, 이유)


class SkipDoc(Exception):
    """이 공고만 건너뛴다. 메시지가 리포트에 적힌다."""


def _analyze(pbno: str, out: Path, ask: Ask, sort: bool = True, mode: str = "T0") -> Doc:
    """out(data/raw/<pbno>/)의 detail.html·notice.pdf로 추출하고 Doc을 만든다. mode는 T0·T1."""
    for name in ("detail.html", "notice.pdf"):
        if not (out / name).exists():
            raise SkipDoc(f"{name} 없음")
    try:
        text = pages(out / "notice.pdf", sort=sort, tables=mode == "T1")
    except Exception as e:  # 열기·텍스트 뽑기 실패가 한 가지 예외가 아니다(#146 리뷰 13)
        raise SkipDoc(f"PDF를 열 수 없음: {e}") from e
    if not any(t.strip() for t in text):
        raise SkipDoc("텍스트 없음(스캔 PDF로 보임)")
    truth = parse_truth((out / "detail.html").read_text(encoding="utf-8"))
    try:
        by_rule = extract_rules(text, ask)
    except ContextExceeded as e:
        raise SkipDoc(f"컨텍스트 한도 초과: {e}") from e
    except BadResponse as e:  # 이 공고의 응답만 못 쓴다. 인증·한도 오류는 잡지 않고 멈춘다
        raise SkipDoc(f"LLM 응답을 쓸 수 없음: {e}") from e
    got = by_rule[DEFAULT_RULE]
    usage = getattr(ask, "last_usage", None)
    return Doc(pbno, truth, got.fields, text, got.blanked, usage, by_rule)


def _body(docs: list[Doc], ask: Ask) -> str:
    md = render_markdown(metrics(docs, FIELDS)) + "\n"
    if DEFAULT_RULE == "C":
        md += (
            "표의 「지어낸 값」·「근거 위치 맞음」은 근거 문장이 PDF에 없어도 값이 그 쪽에 있어 "
            "남긴 칸(C안)까지 센다. 값이 틀렸다는 뜻이 아니다.\n\n"
        )
    md += render_summary(docs, FIELDS)
    if rule_table := render_rule_table(docs, FIELDS):
        md += f"\n값을 남기는 조건 A·B·C안 (같은 LLM 응답에 건 결과):\n\n{rule_table}"
        md += f"\n필드별 맞은 칸:\n\n{render_field_rates(docs, FIELDS)}"
    md += "\n틀리게 채운 칸:\n\n" + render_wrong(docs, FIELDS)
    md += render_shape_errors(docs)
    md += "\n토큰:\n\n" + render_usage(docs)
    return md


def _report(
    title: str,
    by_mode: dict[str, list[Doc]],
    skipped: list[tuple[str, str]],
    report_path: Path,
    ask: Ask,
) -> Result:
    """by_mode: 텍스트 방식 -> Doc들. 방식이 둘 이상이면 방식마다 절을 나눈다."""
    docs = [d for ds in by_mode.values() for d in ds]
    pbnos = list(dict.fromkeys(d.pbno for d in docs))
    md = f"# {title}\n\n공고 {len(pbnos)}건: {', '.join(pbnos)}\n\n"
    if model := getattr(ask, "model", None):
        md += f"모델: {model}\n\n"
    md += "텍스트 방식별 결과:\n\n" + render_mode_table(by_mode, FIELDS)
    md += render_token_ratio(by_mode) + "\n"
    for mode, mode_docs in by_mode.items():
        if len(by_mode) > 1:
            md += f"## {mode}\n\n"
        md += _body(mode_docs, ask)
        md += "\n"
    if skipped:
        md += "건너뛴 공고:\n\n" + "".join(f"- {pbno}: {why}\n" for pbno, why in skipped)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    print(md)
    return Result(metrics(docs, FIELDS), len(docs), skipped)


def run(
    n: int,
    client: httpx.Client,
    raw_dir: Path,
    report_path: Path,
    ask: Ask,
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
            skipped.append((pbno, f"다운로드 실패: {type(e).__name__}: {e}"))
            continue
        try:
            docs.append(_analyze(pbno, out, ask))
        except SkipDoc as e:
            skipped.append((pbno, str(e)))
    return _report("run 리포트", {"T0": docs}, skipped, report_path, ask)


def evaluate(
    pbnos: list[str],
    raw_dir: Path,
    ask: Ask,
    report_path: Path,
    sort: bool = True,
    modes: tuple[str, ...] = ("T0",),
) -> Result:
    """이미 받아 둔 data/raw/<pbno>/만 읽는다. 청약홈에 요청하지 않는다.

    modes의 텍스트 방식마다 같은 공고를 따로 추출해 한 리포트에 나란히 쓴다.
    """
    by_mode: dict[str, list[Doc]] = {m: [] for m in modes}
    skipped: list[tuple[str, str]] = []
    for pbno in pbnos:
        for mode in modes:
            try:
                by_mode[mode].append(_analyze(pbno, raw_dir / pbno, ask, sort, mode))
            except SkipDoc as e:
                why = f"{raw_dir / pbno}: {e}"
                skipped.append((pbno, f"{mode}: {why}" if len(modes) > 1 else why))
    return _report("eval 리포트", by_mode, skipped, report_path, ask)
