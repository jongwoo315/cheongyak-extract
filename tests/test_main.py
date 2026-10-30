import pytest

from cheongyak_extract import __main__ as cli
from cheongyak_extract.fetch import FetchResult
from cheongyak_extract.pipeline import Result
from cheongyak_extract.report import FieldMetrics
from cheongyak_extract.truth_check import Checked

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


def test_eval_extractor_defaults_to_llm(monkeypatch, fake_llm):
    calls = []
    monkeypatch.setattr(
        cli, "evaluate", lambda pbnos, raw, ask, *a, **k: calls.append(ask) or Result([], 1, [])
    )
    assert cli.main(["eval", "--pbno", "A", "--out", "x.md"]) == 0
    assert cli.main(["eval", "--pbno", "A", "--out", "x.md", "--extractor", "llm"]) == 0
    assert calls == [ASK, ASK]
    assert len(fake_llm) == 2


def test_eval_regex_makes_no_llm_client_and_needs_no_api_key(monkeypatch, fake_llm):
    calls = []
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        cli, "evaluate", lambda pbnos, raw, ask, *a, **k: calls.append(ask) or Result([], 1, [])
    )
    monkeypatch.setattr(cli, "model_from_env", lambda: pytest.fail("모델을 읽지 않는다"))
    assert cli.main(["eval", "--pbno", "A", "--out", "x.md", "--extractor", "regex"]) == 0
    assert calls == [None]  # ask가 없으면 evaluate가 정규식으로 뽑는다
    assert fake_llm == []  # make_ask를 부르지 않는다


def test_eval_rejects_unknown_extractor():
    with pytest.raises(SystemExit):
        cli.main(["eval", "--pbno", "A", "--out", "x.md", "--extractor", "rule"])


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


def test_check_raw_reads_data_raw_writes_the_report_and_needs_no_llm(monkeypatch, fake_llm, capsys):
    from cheongyak_extract.raw_check import RawScan

    calls = []

    def fake(raw_dir, out):
        calls.append((str(raw_dir), str(out)))
        return RawScan(3, ["A", "B"], [], [("C", "상세에 공고문 링크 없음")], [])

    monkeypatch.setattr(cli, "check_raw", fake)
    assert cli.main(["check-raw"]) == 0
    assert calls == [("data/raw", "reports/raw.md")]
    assert fake_llm == []  # make_ask를 부르지 않는다
    assert "수집된 공고 2건" in capsys.readouterr().out


def test_check_raw_exits_1_when_a_pdf_does_not_open(monkeypatch):
    from cheongyak_extract.raw_check import RawScan

    monkeypatch.setattr(
        cli, "check_raw", lambda *a: RawScan(1, [], [("A", "FileDataError")], [], [])
    )
    assert cli.main(["check-raw", "--out", "x.md"]) == 1


def test_check_truth_command_makes_no_client_and_passes_paths(monkeypatch):
    calls = []

    def spy(pbnos, raw_dir, labels_path, md, out):
        calls.append((len(pbnos), str(raw_dir), str(labels_path), str(md), str(out)))
        return Checked([], [], [])

    def no_network(*a, **k):
        raise AssertionError("check-truth는 청약홈·OpenAI에 요청하지 않는다")

    monkeypatch.setattr(cli, "run_check", spy)
    monkeypatch.setattr(cli, "make_client", no_network)
    monkeypatch.setattr(cli, "make_ask", no_network)
    monkeypatch.setattr(
        cli, "_new_pbnos", lambda: ["2026000001", "2026000002"]
    )  # reports/extract-new.md 맨 위 목록
    assert cli.main(["check-truth"]) == 0
    assert calls == [
        (
            2,
            "data/raw",
            "labels/pdf-values-20.json",
            "reports/extract-new.md",
            "reports/truth-check.md",
        )
    ]


@pytest.mark.parametrize(
    "error", [ValueError("칸 수"), FileNotFoundError("data/raw"), RuntimeError("pdf")]
)
def test_check_truth_exits_1_with_a_message_when_it_cannot_compare(monkeypatch, capsys, error):
    def boom(*a, **k):
        raise error

    monkeypatch.setattr(cli, "_new_pbnos", lambda: ["2026000001"])
    monkeypatch.setattr(cli, "run_check", boom)
    assert cli.main(["check-truth"]) == 1
    assert "대조할 수 없다" in capsys.readouterr().err


def test_check_truth_exits_1_when_a_quote_is_not_found(monkeypatch, capsys):
    from cheongyak_extract.truth_check import Cell

    ungrounded = Cell("2026000001", "공급규모", "100", "100", 2, "없는 문장", None, True, True)
    monkeypatch.setattr(cli, "_new_pbnos", lambda: ["2026000001"])
    monkeypatch.setattr(cli, "run_check", lambda *a, **k: Checked([ungrounded], [], []))
    assert cli.main(["check-truth"]) == 1
    assert capsys.readouterr().out.strip() == "정규화 뒤 같은 칸 1/1, 근거를 못 찾은 칸 1"
