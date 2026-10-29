import pytest

from cheongyak_extract import __main__ as cli
from cheongyak_extract.fetch import FetchResult
from cheongyak_extract.pipeline import Result
from cheongyak_extract.report import FieldMetrics

ASK = object()


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    made = []

    def make(model, cache_dir):
        made.append((model, str(cache_dir)))
        return ASK

    monkeypatch.setattr(cli, "make_ask", make)
    monkeypatch.setattr(cli, "model_from_env", lambda: "m-env")
    return made


def fake_run(with_truth: int, processed: int = 3):
    row = FieldMetrics("f", with_truth, 0.0, 1.0, 0, 0, None)
    return lambda *a, **k: Result([row], processed, [])


def test_exit_0_when_all_processed_and_every_field_has_truth(monkeypatch):
    monkeypatch.setattr(cli, "run", fake_run(3))
    assert cli.main(["run", "--n", "3"]) == 0


def test_exit_1_when_fewer_announcements_processed(monkeypatch):
    monkeypatch.setattr(cli, "run", fake_run(3, processed=2))
    assert cli.main(["run", "--n", "3"]) == 1


def test_exit_1_when_a_field_has_no_truth(monkeypatch):
    monkeypatch.setattr(cli, "run", fake_run(0))
    assert cli.main(["run", "--n", "3"]) == 1


def test_run_passes_n_default_paths_and_llm_ask(monkeypatch, fake_llm):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        return Result([FieldMetrics("f", 3, 0.0, 1.0, 0, 0, None)], 5, [])

    monkeypatch.setattr(cli, "run", spy)
    assert cli.main(["run", "--n", "5"]) == 0
    n, _client, raw_dir, report_path, ask = calls[0]
    assert (n, str(raw_dir), str(report_path), ask) == (5, "data/raw", "reports/run.md", ASK)
    assert fake_llm == [("m-env", "data/llm")]


def test_eval_reads_only_the_given_notices_offline(monkeypatch):
    calls = []

    def spy(pbnos, raw_dir, ask, report_path, sort=True, modes=("T0",)):
        calls.append((pbnos, str(raw_dir), ask, str(report_path), sort, modes))
        return Result([], len(pbnos), [])

    def no_network():
        raise AssertionError("eval은 청약홈에 요청하지 않는다")

    monkeypatch.setattr(cli, "evaluate", spy)
    monkeypatch.setattr(cli, "make_client", no_network)
    args = ["eval", "--pbno", "2026000518", "2026000530", "--out", "reports/x.md"]
    assert cli.main(args) == 0
    assert calls == [(["2026000518", "2026000530"], "data/raw", ASK, "reports/x.md", True, ("T0",))]
    assert cli.main([*args, "--no-sort"]) == 0
    assert calls[-1][4] is False


def test_eval_text_option_picks_the_text_modes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli, "evaluate", lambda *a, **k: calls.append(k.get("modes")) or Result([], 1, [])
    )
    args = ["eval", "--pbno", "A", "--out", "x.md"]
    cli.main([*args, "--text", "T0", "T1"])
    cli.main([*args, "--text", "T1"])
    assert calls == [("T0", "T1"), ("T1",)]
    with pytest.raises(SystemExit):
        cli.main([*args, "--text", "T2"])


def test_eval_exit_code_counts_one_result_per_notice_and_text_mode(monkeypatch):
    args = ["eval", "--pbno", "A", "--out", "x.md", "--text", "T0", "T1"]
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: Result([], 2, []))
    assert cli.main(args) == 0
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: Result([], 1, [("A", "T1: 건너뜀")]))
    assert cli.main(args) == 1
    # 같은 방식을 두 번 주면 한 번으로 센다
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: Result([], 1, []))
    assert cli.main(["eval", "--pbno", "A", "--out", "x.md", "--text", "T0", "T0"]) == 0


def test_eval_exits_1_when_some_notice_was_skipped(monkeypatch):
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: Result([], 1, [("B", "notice.pdf 없음")]))
    assert cli.main(["eval", "--pbno", "A", "B", "--out", "x.md"]) == 1


def test_eval_requires_pbno_and_out():
    for args in (["eval", "--out", "x.md"], ["eval", "--pbno", "A"]):
        with pytest.raises(SystemExit):
            cli.main(args)


def test_fetch_passes_page_n_and_raw_dir_and_prints_the_fetched_numbers(monkeypatch, capsys):
    calls = []

    def spy(client, raw_dir, start_page, n):
        calls.append((str(raw_dir), start_page, n))
        return FetchResult(["2026000508", "2026000507"], [], None)

    def no_llm(*a):
        raise AssertionError("fetch는 LLM을 만들지 않는다")

    monkeypatch.setattr(cli, "fetch_notices", spy)
    monkeypatch.setattr(cli, "make_ask", no_llm)
    assert cli.main(["fetch", "--start-page", "2", "--n", "20"]) == 0
    assert calls == [("data/raw", 2, 20)]
    assert "2026000508 2026000507" in capsys.readouterr().out


def test_fetch_prints_what_it_got_and_exits_1_when_it_stopped_early(monkeypatch, capsys):
    result = FetchResult(["2026000508"], [], "429 3번 연속")
    monkeypatch.setattr(cli, "fetch_notices", lambda *a: result)
    assert cli.main(["fetch", "--start-page", "2", "--n", "20"]) == 1
    out = capsys.readouterr().out
    assert "2026000508" in out and "429 3번 연속" in out


def test_fetch_prints_how_many_requests_were_retried(monkeypatch, capsys):
    result = FetchResult(["2026000508"], [], None, {"list": 1, "pdf": 2})
    monkeypatch.setattr(cli, "fetch_notices", lambda *a: result)
    assert cli.main(["fetch", "--n", "1"]) == 0
    assert "다시 시도 3회(목록 1, 상세 0, PDF 2)" in capsys.readouterr().out
