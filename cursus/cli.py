"""Command line: `cursus prompt`, `cursus check`, `cursus build`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from cursus import __version__
from cursus.check import check, has_errors
from cursus.datavis import write_xlsx
from cursus.model import Process
from cursus.preview import to_svg
from cursus.prompts import reading_prompt
from cursus.report import to_markdown
from cursus.visio import verify, write_vsdx


class ReadingError(ValueError):
    pass


def load_reading(path: Path) -> Process:
    """Read a model's answer. Models often wrap JSON in a code fence or a sentence, so take the outermost braces."""
    raw = path.read_text(encoding="utf-8")
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise ReadingError(f"{path} holds no JSON object")
    try:
        return Process.model_validate_json(raw[a : b + 1])
    except ValidationError as e:
        raise ReadingError(f"{path} does not match the expected layout:\n{e}") from e


def _findings(p: Process, source: str | None) -> tuple[list, bool]:
    findings = check(p, source)
    for f in findings:
        print(f.line())
    errors = sum(f.level == "error" for f in findings)
    print(f"{len(p.steps)} steps, {len(p.flows)} arrows, {len(p.questions)} questions: {errors} errors, {len(findings) - errors} warnings")
    return findings, has_errors(findings)


def cmd_prompt(args: argparse.Namespace) -> int:
    text = reading_prompt(Path(args.source).read_text(encoding="utf-8"))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    p = load_reading(Path(args.reading))
    source = Path(args.source).read_text(encoding="utf-8") if args.source else None
    _, bad = _findings(p, source)
    return 1 if bad else 0


def cmd_build(args: argparse.Namespace) -> int:
    p = load_reading(Path(args.reading))
    source = Path(args.source).read_text(encoding="utf-8") if args.source else None
    if source is None:
        print("no --source given: quotes are not checked against the text")
    findings, bad = _findings(p, source)
    if bad:
        print("not drawn: fix the errors above first")
        return 1
    out = Path(args.out)
    name = args.name or Path(args.reading).stem
    vsdx = write_vsdx(p, out / f"{name}.vsdx", recalc=not args.no_recalc)
    problems = verify(vsdx)
    for problem in problems:
        print(f"ERROR   file check: {problem}")
    xlsx = write_xlsx(p, out / f"{name}.xlsx")
    md = out / f"{name}.md"
    md.write_text(to_markdown(p, findings), encoding="utf-8")
    svg = out / f"{name}.svg"
    svg.write_text(to_svg(vsdx), encoding="utf-8")
    for path, what in ((vsdx, "Visio file"), (xlsx, "Excel table for Visio's create-from-data"), (svg, "picture of what the Visio file holds"), (md, "questions and sources")):
        print(f"wrote {path}  ({what})")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cursus", description="Turn a written description of a process into a Visio flow.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("prompt", help="write the instructions to give a model, with the source text inside")
    a.add_argument("source", help="text file describing the process")
    a.add_argument("-o", "--out", help="file to write (default: print)")
    a.set_defaults(run=cmd_prompt)

    a = sub.add_parser("check", help="test a reading without drawing it")
    a.add_argument("reading", help="the model's answer (JSON)")
    a.add_argument("--source", help="the text the reading was made from")
    a.set_defaults(run=cmd_check)

    a = sub.add_parser("build", help="test a reading, then write the Visio file, the Excel table, a picture and the sources page")
    a.add_argument("reading", help="the model's answer (JSON)")
    a.add_argument("--source", help="the text the reading was made from")
    a.add_argument("--out", default="out", help="folder to write into (default: out)")
    a.add_argument("--name", help="file name without extension (default: the reading's name)")
    a.add_argument("--no-recalc", action="store_true", help="do not ask Visio to recalculate the file when it opens")
    a.set_defaults(run=cmd_build)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (ReadingError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
