import argparse
import sys
from pathlib import Path

from cheongyak_extract.compare import parse_pbnos
from cheongyak_extract.fetch import fetch_notices, make_client
from cheongyak_extract.llm import make_ask, model_from_env
from cheongyak_extract.measure import measure_normalize
from cheongyak_extract.pdf_text import TEXT_MODES
from cheongyak_extract.pipeline import evaluate, run
from cheongyak_extract.raw_check import check_raw
from cheongyak_extract.truth_check import run_check

RAW_DIR = Path("data/raw")
LLM_CACHE = Path("data/llm")
EXTRACT_NEW = Path("reports/extract-new.md")  # 재는 공고 20건의 맨 위 목록과 LLM 결과
EXTRACTORS = ("llm", "regex")


def _new_pbnos() -> list[str]:
    return parse_pbnos(EXTRACT_NEW.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cheongyak_extract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser(
        "run", help="수집부터 LLM 추출·필드별 리포트까지 한 번에(OPENAI_API_KEY 필요)"
    )
    p.add_argument("--n", type=int, default=3, help="처리할 공고 수")
    p.add_argument("--out", type=Path, default=Path("reports/run.md"), help="리포트 경로")
    e = sub.add_parser(
        "eval", help="받아 둔 data/raw/<pbno>/만 읽어 리포트를 쓴다(청약홈 요청 없음)"
    )
    e.add_argument("--pbno", nargs="+", required=True, help="공고 번호")
    e.add_argument("--out", type=Path, required=True, help="리포트 경로")
    e.add_argument(
        "--no-sort", action="store_true", help="PDF 텍스트를 pymupdf 기본 순서로 뽑는다(비교용)"
    )
    e.add_argument(
        "--text",
        nargs="+",
        choices=TEXT_MODES,
        default=["T0"],
        help="PDF 텍스트 방식. T0=sort=True 텍스트, T1=T0 + 쪽의 표 markdown. 둘이면 나란히 쓴다",
    )
    e.add_argument(
        "--extractor",
        choices=EXTRACTORS,
        default="llm",
        help="llm=OpenAI로 추출(OPENAI_API_KEY 필요). regex=정규식 baseline, LLM을 부르지 않는다",
    )
    f = sub.add_parser("fetch", help="목록 N쪽부터 PDF 있는 공고를 n건 받는다(LLM 안 부름)")
    f.add_argument("--start-page", type=int, default=1, help="목록 시작 쪽")
    f.add_argument("--n", type=int, required=True, help="받을 공고 수")
    c = sub.add_parser(
        "check-raw", help="data/raw/만 읽어 수집된 공고 수와 열리지 않는 PDF를 센다(요청 없음)"
    )
    c.add_argument("--out", type=Path, default=Path("reports/raw.md"), help="리포트 경로")
    t = sub.add_parser(
        "check-truth",
        help="청약홈 정답(HTML)과 공고문 PDF 값을 20건 대조한다(청약홈·OpenAI 요청 없음)",
    )
    t.add_argument("--labels", type=Path, default=Path("labels/pdf-values-20.json"))
    t.add_argument("--out", type=Path, default=Path("reports/truth-check.md"), help="리포트 경로")
    sub.add_parser("measure-normalize", help="모의 추출값 24쌍의 일치 수를 정규화 전·후로 잰다")
    args = parser.parse_args(argv)

    if args.cmd == "measure-normalize":
        measure_normalize(
            RAW_DIR, Path("tests/fixtures/pdf_forms.json"), Path("reports/normalize.md")
        )
        return 0

    if args.cmd == "check-truth":
        try:
            checked = run_check(_new_pbnos(), RAW_DIR, args.labels, EXTRACT_NEW, args.out)
        except (ValueError, OSError, RuntimeError) as e:  # RuntimeError는 pymupdf가 PDF를 못 열 때
            print(f"대조할 수 없다: {e}", file=sys.stderr)
            return 1
        same = sum(c.same for c in checked.cells)
        bad = sum(c.ungrounded for c in checked.cells)
        print(f"정규화 뒤 같은 칸 {same}/{len(checked.cells)}, 근거를 못 찾은 칸 {bad}")
        return 0 if not bad else 1

    if args.cmd == "check-raw":
        found = check_raw(RAW_DIR, args.out)
        print(
            f"공고 디렉터리 {found.dirs}개, 수집된 공고 {len(found.collected)}건, "
            f"열리지 않는 PDF {len(found.unreadable)}건, PDF가 없는 공고 {len(found.no_pdf)}건"
        )
        return 0 if not found.unreadable else 1

    if args.cmd == "fetch":
        with make_client() as client:
            got = fetch_notices(client, RAW_DIR, args.start_page, args.n)
        print(f"받은 공고 {len(got.fetched)}건: {' '.join(got.fetched)}")
        by_kind = ", ".join(
            f"{label} {got.retries.get(kind, 0)}"
            for kind, label in (("list", "목록"), ("detail", "상세"), ("pdf", "PDF"))
        )
        print(f"다시 시도 {sum(got.retries.values())}회({by_kind})")
        for pbno, why in got.skipped:
            print(f"건너뜀 {pbno}: {why}")
        if got.stopped:
            print(f"멈춤: {got.stopped}")
        return 0 if got.stopped is None else 1

    if args.cmd == "eval":
        # regex면 OpenAI 클라이언트를 만들지 않는다. 키가 없어도 돈다
        ask = make_ask(model_from_env(), LLM_CACHE) if args.extractor == "llm" else None
        modes = tuple(dict.fromkeys(args.text))
        result = evaluate(args.pbno, RAW_DIR, ask, args.out, sort=not args.no_sort, modes=modes)
        return 0 if result.processed == len(args.pbno) * len(modes) else 1

    ask = make_ask(model_from_env(), LLM_CACHE)
    with make_client() as client:
        result = run(args.n, client, RAW_DIR, args.out, ask)
    # 정답 있음이 0이면 정확도·빈 칸이 `—`로 나와 추출 결과를 읽을 수 없다. 통과로 치지 않는다.
    no_truth = [m.field for m in result.metrics if m.with_truth == 0]
    if no_truth:
        print(f"정답 있음이 0인 필드: {', '.join(no_truth)}", file=sys.stderr)
    return 0 if result.processed == args.n and not no_truth else 1


if __name__ == "__main__":
    raise SystemExit(main())
