"""Command line: `cursus prompt`, `read`, `questions`, `check`, `build`, `score`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cursus import __version__
from cursus.answers import parse_answers, questions_markdown, text_with_answers
from cursus.check import check, has_errors
from cursus.datavis import write_xlsx
from cursus.model import Process
from cursus.preview import to_svg
from cursus.prompts import reading_prompt
from cursus.read import OLLAMA, ReadError, ollama, parse_reading, read
from cursus.report import to_markdown
from cursus.visio import verify, write_vsdx

ReadingError = ReadError


def load_reading(path: Path | str) -> Process:
    path = Path(path)
    try:
        return parse_reading(path.read_text(encoding="utf-8"))
    except ReadError as e:
        raise ReadError(f"{path}: {e}") from e


def _text(args: argparse.Namespace) -> tuple[str | None, bool]:
    """The text a reading is checked against: the source, plus the author's answers when given."""
    if not getattr(args, "source", None):
        return None, False
    source = Path(args.source).read_text(encoding="utf-8")
    if getattr(args, "answers", None):
        answers = Path(args.answers).read_text(encoding="utf-8")
        n = len(parse_answers(answers))
        print(f"{n} answered question{'s' if n != 1 else ''} added to the text")
        return text_with_answers(source, answers), n > 0
    return source, False


def _report(p: Process, findings: list) -> bool:
    for f in findings:
        print(f.line())
    errors = sum(f.level == "error" for f in findings)
    print(f"{len(p.steps)} steps, {len(p.flows)} arrows, {len(p.questions)} questions: {errors} errors, {len(findings) - errors} warnings")
    return has_errors(findings)


def cmd_prompt(args: argparse.Namespace) -> int:
    text, answered = _text(args)
    prompt = reading_prompt(text or "", has_answers=answered)
    if args.out:
        Path(args.out).write_text(prompt, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(prompt)
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    text, answered = _text(args)
    print(f"reading with {args.model} (up to {args.repairs} repair rounds)...")
    result = read(text or "", ollama(args.model, args.host), repairs=args.repairs, has_answers=answered)
    if result.process is None:
        print(f"error: no usable answer after {result.attempts} tries: {result.fault}", file=sys.stderr)
        return 2
    bad = _report(result.process, result.findings)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.process.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} after {result.attempts} tr{'y' if result.attempts == 1 else 'ies'}, {result.seconds:.0f} s")
    if bad:
        print("the reading still has errors: fix the file by hand or read again before building")
    return 1 if bad else 0


def cmd_questions(args: argparse.Namespace) -> int:
    p = load_reading(args.reading)
    page = questions_markdown(p)
    if args.out:
        Path(args.out).write_text(page, encoding="utf-8")
        print(f"wrote {args.out}  ({len(p.questions)} questions)")
    else:
        sys.stdout.write(page)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    p = load_reading(args.reading)
    text, _ = _text(args)
    return 1 if _report(p, check(p, text)) else 0


def cmd_build(args: argparse.Namespace) -> int:
    p = load_reading(args.reading)
    text, _ = _text(args)
    if text is None:
        print("no --source given: quotes are not checked against the text")
    findings = check(p, text)
    if _report(p, findings):
        print("not drawn: fix the errors above first")
        return 1
    out = Path(args.out)
    name = args.name or Path(args.reading).stem
    try:
        vsdx = write_vsdx(p, out / f"{name}.vsdx", recalc=not args.no_recalc, seed=args.seed)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    problems = verify(vsdx)
    for problem in problems:
        print(f"ERROR   file check: {problem}")
    xlsx = write_xlsx(p, out / f"{name}.xlsx")
    svg = out / f"{name}.svg"
    svg.write_text(to_svg(vsdx), encoding="utf-8")
    md = out / f"{name}.md"
    md.write_text(to_markdown(p, findings), encoding="utf-8")
    for path, what in ((vsdx, "Visio file"), (xlsx, "Excel table for Visio's create-from-data"), (svg, "picture of what the Visio file holds"), (md, "questions and sources")):
        print(f"wrote {path}  ({what})")
    return 1 if problems else 0


def cmd_score(args: argparse.Namespace) -> int:
    from cursus.bench import run_board

    return run_board(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cursus", description="Turn a written description of a process into a Visio flow.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def text_args(a: argparse.ArgumentParser, required: bool) -> None:
        if required:
            a.add_argument("source", help="text file describing the process")
        else:
            a.add_argument("--source", help="the text the reading was made from")
        a.add_argument("--answers", help="a questions page the author has filled in (see `cursus questions`)")

    a = sub.add_parser("prompt", help="write the instructions to give a model by hand, with the text inside")
    text_args(a, True)
    a.add_argument("-o", "--out", help="file to write (default: print)")
    a.set_defaults(run=cmd_prompt)

    a = sub.add_parser("read", help="have a model on this machine read the text, check its reading and retry on faults")
    text_args(a, True)
    a.add_argument("-o", "--out", default="reading.json", help="where to write the reading (default: reading.json)")
    a.add_argument("--model", default="gemma3:12b", help="Ollama model name (default: gemma3:12b)")
    a.add_argument("--host", default=OLLAMA, help=f"Ollama address (default: {OLLAMA})")
    a.add_argument("--repairs", type=int, default=2, help="how many times to send faults back (default: 2)")
    a.set_defaults(run=cmd_read)

    a = sub.add_parser("questions", help="write the reading's open questions as a page for the author to answer")
    a.add_argument("reading", help="a reading (JSON)")
    a.add_argument("-o", "--out", help="file to write (default: print)")
    a.set_defaults(run=cmd_questions)

    a = sub.add_parser("check", help="test a reading without drawing it")
    a.add_argument("reading", help="a reading (JSON)")
    text_args(a, False)
    a.set_defaults(run=cmd_check)

    a = sub.add_parser("build", help="test a reading, then write the Visio file, the Excel table, a picture and the sources page")
    a.add_argument("reading", help="a reading (JSON)")
    text_args(a, False)
    a.add_argument("--out", default="out", help="folder to write into (default: out)")
    a.add_argument("--name", help="file name without extension (default: the reading's name)")
    a.add_argument("--no-recalc", action="store_true", help="do not ask Visio to recalculate the file when it opens")
    a.add_argument("--seed", help="a drawing saved from your own Visio to start from, instead of the bundled one")
    a.set_defaults(run=cmd_build)

    a = sub.add_parser("score", help="score a model's readings against the reference processes in bench/")
    a.add_argument("--model", action="append", help="Ollama model to score (repeatable)")
    a.add_argument("--runs", type=int, default=3, help="readings per case (default: 3)")
    a.add_argument("--repairs", type=int, default=2, help="repair rounds per reading (default: 2)")
    a.add_argument("--host", default=OLLAMA)
    a.add_argument("--bench", default="bench", help="folder holding cases/ and results/ (default: bench)")
    a.add_argument("--only", action="append", help="score only this case (repeatable)")
    a.add_argument("--table", action="store_true", help="do not run anything: rebuild the scoreboard from saved results")
    a.set_defaults(run=cmd_score)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (ReadError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
