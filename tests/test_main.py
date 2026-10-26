import pytest

from cheongyak_extract import __main__ as cli
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

    def spy(pbnos, raw_dir, ask, report_path):
        calls.append((pbnos, str(raw_dir), ask, str(report_path)))
        return Result([], len(pbnos), [])

    def no_network():
        raise AssertionError("eval은 청약홈에 요청하지 않는다")

    monkeypatch.setattr(cli, "evaluate", spy)
    monkeypatch.setattr(cli, "make_client", no_network)
    args = ["eval", "--pbno", "2026000518", "2026000530", "--out", "reports/x.md"]
    assert cli.main(args) == 0
    assert calls == [(["2026000518", "2026000530"], "data/raw", ASK, "reports/x.md")]


def test_eval_exits_1_when_some_notice_was_skipped(monkeypatch):
    monkeypatch.setattr(cli, "evaluate", lambda *a: Result([], 1, [("B", "notice.pdf 없음")]))
    assert cli.main(["eval", "--pbno", "A", "B", "--out", "x.md"]) == 1


def test_eval_requires_pbno_and_out():
    for args in (["eval", "--out", "x.md"], ["eval", "--pbno", "A"]):
        with pytest.raises(SystemExit):
            cli.main(args)
