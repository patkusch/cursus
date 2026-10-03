"""Runs the scoreboard: a model reads every case in bench/cases several times, and each reading is scored against the reference.

Every reading is saved in bench/results/, so a run can be stopped and picked
up again, and the table can be rebuilt without running a model.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from cursus.check import check, has_errors
from cursus.model import Process, settle
from cursus.read import ReadError, ollama, parse_reading, read
from cursus.score import ZERO, Score, score

SAMPLED = 0.7  # run 1 reads the way `cursus read` does (same answer every time); later runs let the model vary


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def cases(bench: Path, only: list[str] | None = None) -> list[tuple[str, str, Process]]:
    out = []
    for folder in sorted((bench / "cases").iterdir()):
        if not (folder / "reference.json").exists() or (only and folder.name not in only):
            continue
        source = (folder / "process.txt").read_text(encoding="utf-8")
        out.append((folder.name, source, parse_reading((folder / "reference.json").read_text(encoding="utf-8"))))
    return out


def _say(line: str) -> None:
    print(line, flush=True)


def run_model(bench: Path, model: str, host: str, runs: int, repairs: int, only: list[str] | None, log=_say) -> None:
    folder = bench / "results" / slug(model)
    folder.mkdir(parents=True, exist_ok=True)
    for name, source, _ in cases(bench, only):
        for run in range(1, runs + 1):
            path = folder / f"{name}.run{run}.json"
            if path.exists():
                continue
            ask = ollama(model, host, temperature=0.0 if run == 1 else SAMPLED, seed=run)
            try:
                result = read(source, ask, repairs=repairs)
            except ReadError as e:
                log(f"{model} {name} run {run}: stopped ({e})")
                raise
            record = {
                "model": model,
                "case": name,
                "run": run,
                "attempts": result.attempts,
                "seconds": round(result.seconds, 1),
                "fault": result.fault,
                "errors": [f.line() for f in result.findings if f.level == "error"],
                "reading": json.loads(result.process.model_dump_json(by_alias=True)) if result.process else None,
            }
            path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
            log(f"{model} {name} run {run}: {'passed' if result.ok else 'refused'} after {result.attempts} tries, {result.seconds:.0f} s")


def score_record(record: dict, source: str, ref: Process) -> tuple[bool, Score]:
    """A reading the checks refuse is never drawn, so it scores nothing: the table shows what a user would get."""
    if not record.get("reading"):
        return False, ZERO
    cand = settle(Process.model_validate(record["reading"]))
    if has_errors(check(cand, source)):
        return False, ZERO
    return True, score(ref, cand, source)


def board(bench: Path) -> dict:
    """model -> per-run averages across the cases, ready for the table."""
    all_cases = {name: (source, ref) for name, source, ref in cases(bench)}
    out: dict[str, dict] = {}
    results = bench / "results"
    for folder in sorted(p for p in results.iterdir() if p.is_dir()) if results.exists() else []:
        by_run: dict[int, list[tuple[bool, Score, dict]]] = {}
        model = folder.name
        for path in sorted(folder.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["case"] not in all_cases:
                continue
            model = record["model"]
            source, ref = all_cases[record["case"]]
            passed, s = score_record(record, source, ref)
            by_run.setdefault(record["run"], []).append((passed, s, record))
        if by_run:
            out[model] = by_run
    return out


COLUMNS = [
    ("Drawn", "passed", "readings that passed every check and would be drawn"),
    ("Steps found", "steps_found", "of the steps in the reference, the share the reading has"),
    ("Steps right", "steps_right", "of the steps in the reading, the share that are in the reference"),
    ("Arrows found", "arrows_found", "of the arrows in the reference, the share the reading has"),
    ("Arrows right", "arrows_right", "of the arrows in the reading, the share that are in the reference"),
    ("Decisions found", "decisions_found", "of the decisions in the reference, the share the reading has"),
    ("Right role", "roles_right", "of the matched steps, the share given to the right person or team"),
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def table(bench: Path) -> str:
    data = board(bench)
    n_cases = len(cases(bench))
    lines = [
        "# Scoreboard",
        "",
        f"Each model read {n_cases} process descriptions. Every reading was scored against a reference written by hand.",
        "A reading the checks refuse is never drawn, so it scores zero on everything: the numbers are what a user would get.",
        "What the numbers show, and what changed since the first run, is in [README.md](README.md).",
        "",
        "Scores run from 0 to 1, and 1 means the same as the reference. The range in brackets is the lowest and highest of the runs.",
        "",
        "| Model | Runs | " + " | ".join(c[0] for c in COLUMNS) + " | Gaps asked | Gaps guessed | Seconds per reading |",
        "| --- | --- | " + " | ".join("---" for _ in COLUMNS) + " | --- | --- | --- |",
    ]
    for model, by_run in data.items():
        cells = []
        for _, key, _ in COLUMNS:
            per_run = [_mean([float(passed) if key == "passed" else getattr(s, key) for passed, s, _ in rows]) for rows in by_run.values()]
            cell = f"{_mean(per_run):.2f}"
            if len(per_run) > 1:
                cell += f" ({min(per_run):.2f}–{max(per_run):.2f})"
            cells.append(cell)
        rows = [r for run in by_run.values() for r in run]
        gaps = sum(len_gaps for len_gaps in (_gaps(bench, r[2]["case"]) for r in rows))
        asked = sum(s.gaps_asked for _, s, _ in rows)
        guessed = sum(s.gaps_guessed for _, s, _ in rows)
        seconds = _mean([r[2]["seconds"] for r in rows])
        lines.append(f"| {model} | {len(by_run)} | " + " | ".join(cells) + f" | {asked} of {gaps} | {guessed} of {gaps} | {seconds:.0f} |")
    if not data:
        lines.append("| *no results yet* | | " + " | ".join("" for _ in COLUMNS) + " | | | |")
    lines += ["", "What the columns mean:", ""]
    lines[-3:-3] = _by_case(bench, data)
    lines += [f"- **{name}**: {meaning}." for name, _, meaning in COLUMNS]
    lines += [
        "- **Gaps asked**: places where the text does not say what happens, and the reading asked instead of making something up.",
        "- **Gaps guessed**: the same places, where the reading drew a second way out without asking.",
        "",
        "Run 1 reads the way `cursus read` does. Later runs let the model vary, to show how much the result moves.",
        "The reference decides how finely the work is cut, so a reading that splits or merges steps loses a little even when a person would call it right.",
        "",
    ]
    return "\n".join(lines)


def _by_case(bench: Path, data: dict) -> list[str]:
    """One row per case: how many of a model's readings were drawn, and how many of the reference's steps they found."""
    if not data:
        return []
    models = list(data)
    lines = ["", "## Case by case", "", "Readings drawn out of the runs made, then the share of the reference's steps found.", ""]
    lines.append("| Case | Steps | " + " | ".join(models) + " |")
    lines.append("| --- | --- | " + " | ".join("---" for _ in models) + " |")
    for name, _, ref in cases(bench):
        work = sum(s.kind not in ("start", "end") for s in ref.steps)
        cells = []
        for model in models:
            rows = [r for run in data[model].values() for r in run if r[2]["case"] == name]
            if not rows:
                cells.append("")
                continue
            drawn = sum(passed for passed, _, _ in rows)
            cells.append(f"{drawn} of {len(rows)} drawn, {_mean([s.steps_found for _, s, _ in rows]):.2f}")
        lines.append(f"| {name} | {work} | " + " | ".join(cells) + " |")
    return lines


_GAPS: dict[tuple[str, str], int] = {}


def _gaps(bench: Path, case: str) -> int:
    key = (str(bench), case)
    if key not in _GAPS:
        from cursus.model import open_decisions

        for name, _, ref in cases(bench):
            _GAPS[(str(bench), name)] = len(open_decisions(ref))
    return _GAPS.get(key, 0)


def run_board(args) -> int:
    bench = Path(args.bench)
    if not args.table:
        if not args.model:
            print("error: name at least one --model, or use --table to rebuild from saved results")
            return 2
        for model in args.model:
            run_model(bench, model, args.host, args.runs, args.repairs, args.only)
    out = bench / "SCOREBOARD.md"
    out.write_text(table(bench), encoding="utf-8")
    print(f"wrote {out}")
    return 0
