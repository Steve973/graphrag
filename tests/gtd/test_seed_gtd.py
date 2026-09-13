from pathlib import Path

import pytest

from gtd.seed_gtd import build_parser, main


def test_csv_command_line_option_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GTD_CSV_PATH", "/environment/gtd.csv")

    args = build_parser().parse_args(["--csv", "/command/gtd.csv"])

    assert args.csv == Path("/command/gtd.csv")


def test_csv_defaults_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GTD_CSV_PATH", "/environment/gtd.csv")

    args = build_parser().parse_args([])

    assert args.csv == Path("/environment/gtd.csv")


def test_csv_is_required_from_option_or_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GTD_CSV_PATH", raising=False)

    with pytest.raises(SystemExit, match="2"):
        main([])
