import json
import shutil
from pathlib import Path

import cursus.bench as bench_module
from cursus.bench import board, run_model, table

REAL = Path(__file__).resolve().parent.parent / "bench"


def small_bench(tmp_path):
    shutil.copytree(REAL / "cases" / "order-packing", tmp_path / "cases" / "order-packing")
    bench_module._GAPS.clear()
    return tmp_path


def test_a_model_run_saves_each_reading_and_picks_up_where_it_stopped(tmp_path, monkeypatch):
    bench = small_bench(tmp_path)
    good = (bench / "cases" / "order-packing" / "reference.json").read_text()
    calls = []

    def fake_ollama(model, host, *, temperature, seed):
        calls.append((temperature, seed))
        return lambda messages: good

    monkeypatch.setattr(bench_module, "ollama", fake_ollama)
    run_model(bench, "toy:1b", "http://nowhere", runs=2, repairs=0, only=None, log=lambda line: None)
    saved = sorted(p.name for p in (bench / "results" / "toy-1b").iterdir())
    assert saved == ["order-packing.run1.json", "order-packing.run2.json"]
    assert calls == [(0.0, 1), (0.7, 2)]  # run 1 as shipped, run 2 allowed to vary

    run_model(bench, "toy:1b", "http://nowhere", runs=3, repairs=0, only=None, log=lambda line: None)
    assert len(calls) == 3  # only the missing third run was made


def test_a_refused_reading_scores_zero_and_shows_in_the_table(tmp_path):
    bench = small_bench(tmp_path)
    good = json.loads((bench / "cases" / "order-packing" / "reference.json").read_text())
    folder = bench / "results" / "toy-1b"
    folder.mkdir(parents=True)
    for run, reading in ((1, good), (2, None)):
        record = {"model": "toy:1b", "case": "order-packing", "run": run, "attempts": 1, "seconds": 10.0, "fault": "", "errors": [], "reading": reading}
        (folder / f"order-packing.run{run}.json").write_text(json.dumps(record))

    by_run = board(bench)["toy:1b"]
    assert by_run[1][0][0] is True and by_run[2][0][0] is False
    text = table(bench)
    row = next(line for line in text.splitlines() if line.startswith("| toy:1b"))
    assert "| 2 |" in row and "0.50 (0.00–1.00)" in row
    assert "0 of 0" in row  # this case has no gaps to ask about
    assert "| order-packing | 4 | 1 of 2 drawn, 0.50 |" in text


def test_table_without_results_says_so(tmp_path):
    assert "no results yet" in table(small_bench(tmp_path))
