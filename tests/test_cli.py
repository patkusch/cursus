from pathlib import Path

import pytest

from cursus import __version__
from cursus.cli import main

EX = Path(__file__).resolve().parent.parent / "examples" / "expense-claim"
READING = EX / "reading.json"
SOURCE = EX / "process.txt"
ANSWERS = EX / "answers.md"
ANSWERED_READING = EX / "reading-answered.json"


def fake_model(monkeypatch, reply):
    """Stand in for the local model: every question gets `reply` (a string, or a function of the call number)."""
    calls = []

    def ollama(model, host):
        def ask(messages):
            calls.append(model)
            return reply(len(calls)) if callable(reply) else reply

        return ask

    monkeypatch.setattr("cursus.cli.ollama", ollama)
    return calls


def test_version_prints_the_number(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_is_refused_with_usage(capsys):
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_prompt_prints_the_instructions_with_the_text_inside(capsys):
    assert main(["prompt", str(SOURCE)]) == 0
    out = capsys.readouterr().out
    assert SOURCE.read_text(encoding="utf-8").strip()[:60] in out


def test_prompt_can_write_to_a_file_and_say_how_many_answers_it_added(tmp_path, capsys):
    target = tmp_path / "prompt.txt"
    assert main(["prompt", str(SOURCE), "--answers", str(ANSWERS), "-o", str(target)]) == 0
    out = capsys.readouterr().out
    assert "1 answered question added to the text" in out
    assert f"wrote {target}" in out
    assert "If the finance director refuses" in target.read_text(encoding="utf-8")


def test_questions_prints_a_page_or_writes_it_and_counts_the_questions(tmp_path, capsys):
    assert main(["questions", str(READING)]) == 0
    assert "What happens when the finance director does not sign off a claim?" in capsys.readouterr().out
    target = tmp_path / "q.md"
    assert main(["questions", str(READING), "-o", str(target)]) == 0
    assert "(2 questions)" in capsys.readouterr().out
    assert target.read_text(encoding="utf-8").count("Answer:") == 3


def test_check_passes_a_good_reading_and_counts_what_it_found(capsys):
    assert main(["check", str(READING), "--source", str(SOURCE)]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_check_reports_when_the_authors_answers_were_added(capsys):
    assert main(["check", str(ANSWERED_READING), "--source", str(SOURCE), "--answers", str(ANSWERS)]) in (0, 1)
    assert "1 answered question added to the text" in capsys.readouterr().out


def test_check_fails_with_exit_1_when_a_quote_is_not_in_the_text(tmp_path, capsys):
    other = tmp_path / "other.txt"
    other.write_text("Completely different text.", encoding="utf-8")
    assert main(["check", str(READING), "--source", str(other)]) == 1
    assert "error" in capsys.readouterr().out.lower()


def test_a_missing_or_unreadable_reading_is_a_clean_exit_2_not_a_traceback(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.json")]) == 2
    assert capsys.readouterr().err.startswith("error:")
    junk = tmp_path / "junk.json"
    junk.write_text("not json at all", encoding="utf-8")
    assert main(["check", str(junk)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error:") and "junk.json" in err


def test_build_without_a_source_says_quotes_were_not_checked_and_still_builds(tmp_path, capsys):
    assert main(["build", str(READING), "--out", str(tmp_path), "--name", "x"]) == 0
    out = capsys.readouterr().out
    assert "no --source given: quotes are not checked against the text" in out
    assert {p.suffix for p in tmp_path.iterdir()} == {".vsdx", ".xlsx", ".svg", ".md"}


def test_read_writes_the_reading_when_the_model_gets_it_right_first_time(tmp_path, capsys, monkeypatch):
    calls = fake_model(monkeypatch, READING.read_text(encoding="utf-8"))
    target = tmp_path / "sub" / "reading.json"
    assert main(["read", str(SOURCE), "-o", str(target), "--model", "tiny"]) == 0
    out = capsys.readouterr().out
    assert "reading with tiny (up to 2 repair rounds)" in out
    assert "after 1 try" in out
    assert calls == ["tiny"]
    assert target.exists(), "the folder is created when it does not exist"
    assert main(["check", str(target), "--source", str(SOURCE)]) == 0


def test_read_gives_up_with_exit_2_when_the_model_never_gives_json(tmp_path, capsys, monkeypatch):
    calls = fake_model(monkeypatch, "I cannot help with that.")
    target = tmp_path / "r.json"
    assert main(["read", str(SOURCE), "-o", str(target), "--repairs", "1"]) == 2
    assert "no usable answer after 2 tries" in capsys.readouterr().err
    assert len(calls) == 2, "one try plus one repair"
    assert not target.exists()


def test_read_keeps_the_best_reading_but_says_it_still_has_errors(tmp_path, capsys, monkeypatch):
    fake_model(monkeypatch, ANSWERED_READING.read_text(encoding="utf-8"))  # its added step is not in the original text
    target = tmp_path / "r.json"
    assert main(["read", str(SOURCE), "-o", str(target), "--repairs", "0"]) == 1
    out = capsys.readouterr().out
    assert "the reading still has errors" in out
    assert target.exists()
