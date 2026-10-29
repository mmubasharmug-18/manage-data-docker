import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

from add_reading import HEADER, main

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "add_reading.py"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def saved_rows(data_dir):
    with (data_dir / "readings.csv").open(newline="") as handle:
        return list(csv.reader(handle))


def test_first_reading_creates_the_file_with_a_header(data_dir):
    assert main(["P-001", "120", "80", "72"]) == 0
    rows = saved_rows(data_dir)
    assert rows[0] == HEADER
    assert rows[1][1:] == ["P-001", "120", "80", "72"]


def test_header_is_written_only_once(data_dir):
    main(["P-001", "120", "80", "72"])
    main(["P-002", "135", "88", "76"])
    rows = saved_rows(data_dir)
    assert len(rows) == 3
    assert rows.count(HEADER) == 1


def test_output_counts_the_readings_in_the_file(data_dir, capsys):
    main(["P-001", "120", "80", "72"])
    main(["P-002", "135", "88", "76"])
    out = capsys.readouterr().out
    assert "Readings in file: 1" in out
    assert "Readings in file: 2" in out


def test_patient_id_is_trimmed(data_dir):
    main(["  P-001  ", "120", "80", "72"])
    assert saved_rows(data_dir)[1][1] == "P-001"


def test_show_lists_every_reading(data_dir, capsys):
    main(["P-001", "120", "80", "72"])
    main(["P-002", "135", "88", "76"])
    capsys.readouterr()
    assert main(["--show"]) == 0
    out = capsys.readouterr().out
    assert "P-001" in out and "BP 120/80" in out
    assert "P-002" in out and "BP 135/88" in out
    assert "Readings in file: 2" in out


def test_show_with_no_file_says_zero(data_dir, capsys):
    assert main(["--show"]) == 0
    assert "Readings in file: 0" in capsys.readouterr().out


def test_a_row_added_by_hand_is_picked_up(data_dir, capsys):
    main(["P-001", "120", "80", "72"])
    with (data_dir / "readings.csv").open("a") as handle:
        handle.write("2026-01-01T00:00:00+00:00,P-011,118,76,66\n")
    capsys.readouterr()
    main(["--show"])
    out = capsys.readouterr().out
    assert "P-011" in out
    assert "Readings in file: 2" in out


@pytest.mark.parametrize(
    "args",
    [
        ["P-001", "49", "80", "72"],
        ["P-001", "301", "80", "72"],
        ["P-001", "120", "29", "72"],
        ["P-001", "120", "201", "72"],
        ["P-001", "120", "80", "19"],
        ["P-001", "120", "80", "251"],
        ["   ", "120", "80", "72"],
    ],
)
def test_bad_values_are_not_saved(data_dir, capsys, args):
    assert main(args) == 2
    assert "Not saved" in capsys.readouterr().err
    assert not (data_dir / "readings.csv").exists()


def test_missing_arguments_are_refused(data_dir):
    with pytest.raises(SystemExit) as error:
        main(["P-001", "120"])
    assert error.value.code == 2


def test_a_folder_that_cannot_be_used_gives_exit_code_1(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x")
    monkeypatch.setenv("DATA_DIR", str(blocker))
    assert main(["P-001", "120", "80", "72"]) == 1
    assert "Problem with" in capsys.readouterr().err


def test_script_runs_on_its_own_and_defaults_to_a_data_folder(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "DATA_DIR"}
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "P-001", "120", "80", "72"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert done.returncode == 0
    assert (tmp_path / "data" / "readings.csv").exists()
    assert "Readings in file: 1" in done.stdout
