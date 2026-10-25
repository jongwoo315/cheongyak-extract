from cheongyak_extract import __main__ as cli
from cheongyak_extract.pipeline import Result
from cheongyak_extract.report import FieldMetrics


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
