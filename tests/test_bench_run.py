import json
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from cursus import bench
from cursus.read import ReadError

EX = Path(__file__).resolve().parent.parent / "examples" / "expense-claim"


@pytest.fixture
def folder(tmp_path):
    """A small bench of one case, built from the bundled example."""
    case = tmp_path / "cases" / "expense"
    case.mkdir(parents=True)
    shutil.copy(EX / "process.txt", case / "process.txt")
    shutil.copy(EX / "reading.json", case / "reference.json")
    return tmp_path


@pytest.fixture
def stand_in(monkeypatch):
    """Replace the model with one that returns the reference reading, and remember how it was asked for."""
    asked = []

    def fake_ollama(model, host, temperature, seed):
        asked.append({"model": model, "host": host, "temperature": temperature, "seed": seed})
        return lambda messages: (EX / "reading.json").read_text(encoding="utf-8")

    monkeypatch.setattr(bench, "ollama", fake_ollama)
    return asked


def test_the_slug_makes_a_model_name_safe_for_a_folder():
    assert bench.slug("gemma3:12b") == "gemma3-12b"
    assert bench.slug("Library/Model_V2.5") == "library-model-v2-5"


def test_only_folders_with_a_reference_reading_count_as_cases_and_only_filters_by_name(folder):
    (folder / "cases" / "unfinished").mkdir()
    (folder / "cases" / "unfinished" / "process.txt").write_text("text", encoding="utf-8")
    assert [name for name, _, _ in bench.cases(folder)] == ["expense"]
    assert bench.cases(folder, only=["other"]) == []
    assert [name for name, _, _ in bench.cases(folder, only=["expense"])] == ["expense"]


def test_each_run_is_saved_with_how_it_went_and_the_first_run_is_the_steady_one(folder, stand_in):
    lines = []
    bench.run_model(folder, "gemma3:12b", "http://h:1", runs=2, repairs=1, only=None, log=lines.append)
    saved = sorted(p.name for p in (folder / "results" / "gemma3-12b").iterdir())
    assert saved == ["expense.run1.json", "expense.run2.json"]
    record = json.loads((folder / "results" / "gemma3-12b" / "expense.run1.json").read_text())
    assert record["model"] == "gemma3:12b" and record["case"] == "expense" and record["run"] == 1
    assert record["attempts"] == 1 and record["fault"] == "" and record["reading"]
    assert [a["temperature"] for a in stand_in] == [0.0, bench.SAMPLED]
    assert [a["seed"] for a in stand_in] == [1, 2], "each repeat has its own seed, so repeats differ"
    assert all(a["host"] == "http://h:1" for a in stand_in)
    assert len(lines) == 2 and "expense run 1: " in lines[0] and "after 1 tries" in lines[0]


def test_runs_that_are_already_saved_are_not_asked_for_again(folder, stand_in):
    bench.run_model(folder, "m", "h", runs=1, repairs=0, only=None, log=lambda _: None)
    first = len(stand_in)
    bench.run_model(folder, "m", "h", runs=1, repairs=0, only=None, log=lambda _: None)
    assert len(stand_in) == first
    bench.run_model(folder, "m", "h", runs=2, repairs=0, only=None, log=lambda _: None)
    assert len(stand_in) == first + 1, "only the new second run is asked for"


def test_a_model_that_cannot_be_reached_stops_the_run_and_says_which_one(folder, monkeypatch):
    def down(model, host, temperature, seed):
        def ask(messages):
            raise ReadError("could not reach Ollama")
        return ask

    monkeypatch.setattr(bench, "ollama", down)
    lines = []
    with pytest.raises(ReadError):
        bench.run_model(folder, "ghost", "h", runs=1, repairs=0, only=None, log=lines.append)
    assert lines == ["ghost expense run 1: stopped (could not reach Ollama)"]
    assert not (folder / "results" / "ghost" / "expense.run1.json").exists()


def test_a_reading_the_checks_refuse_scores_nothing_so_the_table_shows_what_a_user_would_get(folder):
    _, source, ref = bench.cases(folder)[0]
    assert bench.score_record({"reading": None}, source, ref) == (False, bench.ZERO)
    assert bench.score_record({}, source, ref) == (False, bench.ZERO)
    good = json.loads((EX / "reading.json").read_text(encoding="utf-8"))
    drawn, score = bench.score_record({"reading": good}, source, ref)
    assert drawn is True and score != bench.ZERO
    assert bench.score_record({"reading": good}, "a completely different text", ref) == (False, bench.ZERO), "quotes not in the text are refused"


def test_scoring_needs_a_model_or_the_table_flag_and_says_so(folder, capsys):
    code = bench.run_board(Namespace(bench=str(folder), table=False, model=None, host="h", runs=1, repairs=0, only=None))
    assert code == 2
    assert "name at least one --model, or use --table" in capsys.readouterr().out
    assert not (folder / "SCOREBOARD.md").exists()


def test_table_rebuilds_the_scoreboard_from_saved_runs_without_asking_any_model(folder, stand_in, capsys):
    bench.run_model(folder, "gemma3:12b", "h", runs=1, repairs=0, only=None, log=lambda _: None)
    asked = len(stand_in)
    code = bench.run_board(Namespace(bench=str(folder), table=True, model=None, host="h", runs=1, repairs=0, only=None))
    assert code == 0 and len(stand_in) == asked
    board = (folder / "SCOREBOARD.md").read_text(encoding="utf-8")
    assert f"wrote {folder / 'SCOREBOARD.md'}" in capsys.readouterr().out
    assert "expense" in board and "1 of 1 drawn" in board


def test_running_a_named_model_through_the_board_saves_its_runs_and_then_the_table(folder, stand_in, capsys):
    code = bench.run_board(Namespace(bench=str(folder), table=False, model=["gemma3:4b"], host="h", runs=1, repairs=0, only=None))
    assert code == 0
    assert (folder / "results" / "gemma3-4b" / "expense.run1.json").exists()
    assert (folder / "SCOREBOARD.md").exists()
