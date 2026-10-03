"""Score a model that is reached by copy and paste instead of through Ollama.

    python scripts/paste_bench.py prompts DIR
        writes one prompt per case into DIR/prompts/

    python scripts/paste_bench.py collect "model name" DIR/answers
        reads DIR/answers/<case>.json, checks each reading, saves it under
        bench/results/, and writes <case>.faults.md next to any reading that
        failed, ready to paste back to the model for another try

Run `collect` again after each round of fixes. `cursus score --table` then
rebuilds the scoreboard.
"""
import json
import sys
from pathlib import Path

from cursus.bench import cases, slug
from cursus.check import check
from cursus.prompts import reading_prompt
from cursus.read import ReadError, _fix_request, parse_reading

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"


def prompts(folder: Path) -> None:
    out = folder / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    for name, source, _ in cases(BENCH):
        (out / f"{name}.md").write_text(reading_prompt(source), encoding="utf-8")
    print(f"wrote {len(list(out.iterdir()))} prompts to {out}")


def collect(model: str, answers: Path) -> None:
    results = BENCH / "results" / slug(model)
    results.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, source, _ in cases(BENCH):
        path = answers / f"{name}.json"
        record_path = results / f"{name}.run1.json"
        tries = json.loads(record_path.read_text())["attempts"] if record_path.exists() else 0
        faults_path = answers / f"{name}.faults.md"
        if not path.exists():
            print(f"{name}: no answer yet")
            continue
        raw = path.read_text(encoding="utf-8")
        seen = answers / f".{name}.seen"
        if not seen.exists() or seen.read_text() != raw:  # a new or changed answer counts as one more try
            tries += 1
            seen.write_text(raw)
        try:
            process, fault = parse_reading(raw), ""
            findings = check(process, source)
        except ReadError as e:
            process, fault, findings = None, str(e), []
        errors = [f for f in findings if f.level == "error"]
        record = {
            "model": model,
            "case": name,
            "run": 1,
            "attempts": tries,
            "seconds": 0,
            "fault": fault,
            "errors": [f.line() for f in errors],
            "reading": json.loads(process.model_dump_json(by_alias=True)) if process else None,
        }
        record_path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        if fault or errors:
            failed += 1
            faults_path.write_text(_fix_request([fault] if fault else [f"{f.where}: {f.message}" for f in errors]) + "\n", encoding="utf-8")
            print(f"{name}: refused on try {tries} -> {faults_path.name}")
        else:
            faults_path.unlink(missing_ok=True)
            print(f"{name}: passed on try {tries}")
    print(f"{failed} to fix")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "prompts":
        prompts(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "collect":
        collect(sys.argv[2], Path(sys.argv[3]))
    else:
        sys.exit(__doc__)
