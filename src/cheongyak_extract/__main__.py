import argparse
from pathlib import Path

from cheongyak_extract.fetch import make_client
from cheongyak_extract.pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cheongyak_extract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="수집부터 필드별 리포트까지 한 번에")
    p.add_argument("--n", type=int, default=3, help="처리할 공고 수")
    args = parser.parse_args(argv)

    with make_client() as client:
        result = run(args.n, client, Path("data/raw"), Path("reports/skeleton.md"))
    return 0 if result.processed == args.n else 1


if __name__ == "__main__":
    raise SystemExit(main())
