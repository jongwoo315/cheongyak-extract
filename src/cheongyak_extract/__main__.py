import argparse
import sys
from pathlib import Path

from cheongyak_extract.fetch import make_client
from cheongyak_extract.measure import measure_normalize
from cheongyak_extract.pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cheongyak_extract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="수집부터 필드별 리포트까지 한 번에")
    p.add_argument("--n", type=int, default=3, help="처리할 공고 수")
    sub.add_parser("measure-normalize", help="모의 추출값 24쌍의 일치 수를 정규화 전·후로 잰다")
    args = parser.parse_args(argv)

    if args.cmd == "measure-normalize":
        measure_normalize(
            Path("data/raw"), Path("tests/fixtures/pdf_forms.json"), Path("reports/normalize.md")
        )
        return 0

    with make_client() as client:
        result = run(args.n, client, Path("data/raw"), Path("reports/skeleton.md"))
    # 정답 있음이 0이면 정확도·빈 칸이 `—`로 나와 stub 동작을 확인할 수 없다. 통과로 치지 않는다.
    no_truth = [m.field for m in result.metrics if m.with_truth == 0]
    if no_truth:
        print(f"정답 있음이 0인 필드: {', '.join(no_truth)}", file=sys.stderr)
    return 0 if result.processed == args.n and not no_truth else 1


if __name__ == "__main__":
    raise SystemExit(main())
