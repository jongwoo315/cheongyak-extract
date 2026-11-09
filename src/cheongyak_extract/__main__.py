import argparse
import sys
from pathlib import Path

from cheongyak_extract.compare import parse_pbnos
from cheongyak_extract.fetch import fetch_notices, make_client
from cheongyak_extract.llm import make_ask, model_from_env
from cheongyak_extract.measure import measure_normalize
from cheongyak_extract.pdf_fields import (
    RESIDENT_BLOCK_SET,
    TWO_FIELD_SET,
    check_pdf_labels,
    evaluate_pdf,
)
from cheongyak_extract.pdf_text import TEXT_MODES
from cheongyak_extract.pipeline import evaluate, run
from cheongyak_extract.raw_check import check_raw
from cheongyak_extract.resident_bound import report as resident_bound_report
from cheongyak_extract.resident_bound import snapshot
from cheongyak_extract.truth_check import missing_material, run_check, run_judge

RAW_DIR = Path("data/raw")
LLM_CACHE = Path("data/llm")
EXTRACT_NEW = Path("reports/extract-new.md")  # 재는 공고 20건의 맨 위 목록과 LLM 결과
EXTRACTORS = ("llm", "regex")
PDF_LABELS = Path("labels/pdf-only-50.json")  # --set tune: 기존 50건 세 필드
RESIDENT_LABELS = Path("labels/pdf-resident-30.json")  # --set test: 새 30건 거주지
JUDGE_FILE = Path("labels/source-judge.json")  # judge-source: jw가 어느 쪽이 맞는지 채우는 파일


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
    j = sub.add_parser(
        "judge-source",
        help="HTML 값·PDF 값·LLM 값이 정규화 뒤 하나라도 다른 칸을 jw가 판정할 파일로 "
        "만들고(있으면 읽고) 집계한다"
        "(청약홈·OpenAI 요청 없음)",
    )
    j.add_argument("--labels", type=Path, default=Path("labels/pdf-values-20.json"))
    j.add_argument("--judge", type=Path, default=JUDGE_FILE, help="jw가 채우는 판정 파일")
    j.add_argument("--out", type=Path, default=Path("reports/source-judge.md"), help="리포트 경로")
    ep = sub.add_parser(
        "eval-pdf",
        help="PDF에만 있는 필드를 수동 정답으로 잰다(청약홈 요청 없음, OpenAI 호출). "
        "tune=기존 50건 세 필드, test=새 30건 거주지만",
    )
    ep.add_argument("--set", dest="which", choices=("tune", "test"), required=True)
    ep.add_argument("--out", type=Path, required=True, help="리포트 경로")
    cl = sub.add_parser(
        "check-pdf-labels", help="수동 정답 파일 둘(180칸)을 검사하고 요약을 쓴다(요청 없음)"
    )
    cl.add_argument("--out", type=Path, default=Path("reports/pdf-labels.md"), help="리포트 경로")
    rb = sub.add_parser(
        "snapshot-resident-bound",
        help="149건의 거주지 묶음(규칙·쪽·글자 수·줄 수)을 재서 JSON으로 쓴다(요청 없음)",
    )
    rb.add_argument("--out", type=Path, required=True, help="JSON 경로")
    rb.add_argument(
        "--compare-to", type=Path, help="main 쪽 값 JSON. 주면 JSON 대신 비교 리포트를 --out에 쓴다"
    )
    sub.add_parser("measure-normalize", help="모의 추출값 24쌍의 일치 수를 정규화 전·후로 잰다")
    args = parser.parse_args(argv)

    if args.cmd == "measure-normalize":
        measure_normalize(
            RAW_DIR, Path("tests/fixtures/pdf_forms.json"), Path("reports/normalize.md")
        )
        return 0

    if args.cmd == "snapshot-resident-bound":
        if args.compare_to:
            cmd = (
                "uv run python -m cheongyak_extract snapshot-resident-bound "
                f"--compare-to {args.compare_to} --out {args.out}"
            )
            resident_bound_report(RAW_DIR, args.compare_to, args.out, cmd, "a51fe89")
            print(f"비교 리포트를 {args.out}에 썼다")
            return 0
        got = snapshot(RAW_DIR, args.out)
        print(f"공고 {len(got)}건, 묶음 있음 {sum(v['rule'] is not None for v in got.values())}건")
        return 0

    if args.cmd == "check-pdf-labels":
        try:
            cells = check_pdf_labels(RAW_DIR, PDF_LABELS, RESIDENT_LABELS, args.out)
        except (ValueError, OSError, RuntimeError) as e:
            print(f"정답을 검사할 수 없다: {e}", file=sys.stderr)
            return 1
        bad = sum(bool(c.problems) for c in cells)
        print(f"칸 {len(cells)}개, 정답 검사에 걸린 칸 {bad}개")
        return 0 if not bad else 1

    if args.cmd == "eval-pdf":
        model = model_from_env()
        ask = make_ask(model, LLM_CACHE, schema=TWO_FIELD_SET.schema)  # 전매제한·신혼부부
        resident_ask = make_ask(model, LLM_CACHE, schema=RESIDENT_BLOCK_SET.schema)  # 거주지
        labels = PDF_LABELS if args.which == "tune" else RESIDENT_LABELS
        try:
            result = evaluate_pdf(
                args.which, RAW_DIR, labels, ask, args.out, resident_ask=resident_ask
            )
        except (ValueError, OSError, RuntimeError) as e:  # 정답 파일이 깨졌거나 PDF를 못 연다
            print(f"잴 수 없다: {e}", file=sys.stderr)
            return 1
        print(
            f"칸 {len(result.cells)}개, 건너뛴 공고 {len(result.skipped)}건, "
            f"정답 검사에 걸린 칸 {len(result.label_problems)}개, 입력 토큰 {result.input_tokens:,}"
        )
        return 0 if not result.skipped and not result.label_problems else 1

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

    if args.cmd == "judge-source":
        try:
            judged = run_judge(
                _new_pbnos(), RAW_DIR, args.labels, EXTRACT_NEW, args.judge, args.out
            )
        except (ValueError, OSError, RuntimeError) as e:  # jw 값이 틀렸거나 파일·PDF를 못 읽는다
            print(f"판정 파일을 만들 수 없다: {e}", file=sys.stderr)
            return 1
        pending = sum(r["jw"] is None for r in judged.rows)
        print(
            f"판정할 칸 {len(judged.rows)}/{judged.total}, 정규화로 빠진 칸 {len(judged.dropped)}, "
            f"판정 전 {pending}, "
            f"재료가 빠진 칸 {sum(map(missing_material, judged.rows))}, "
            f"근거를 못 찾은 칸 {len(judged.bad)}"
        )
        return 0 if not judged.bad else 1

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
