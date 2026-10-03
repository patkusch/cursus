"""Writes the files in testpack/: the ones a person opens in Visio to answer what only Visio can.

Also writes expected.json: how many shapes and source sentences each file
holds, so a program that opens the file can be checked against it.
"""
import json
from pathlib import Path

from cursus.cli import load_reading
from cursus.datavis import write_xlsx
from cursus.model import with_stubs
from cursus.preview import read_page
from cursus.visio import verify, write_vsdx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "testpack"

hello = load_reading(ROOT / "examples/hello/reading.json")
bare = hello.model_copy(deep=True)  # stock shapes and arrows only: no title, no source text
bare.title = ""
for step in bare.steps:
    step.quote = ""
expense = load_reading(ROOT / "examples/expense-claim/reading.json")

expected = {}
for name, process, recalc in (
    ("1-three-boxes.vsdx", bare, False),
    ("2-expense-claim.vsdx", expense, False),
    ("3-expense-claim-recalculated.vsdx", expense, True),
):
    problems = verify(write_vsdx(process, OUT / name, recalc=recalc))
    assert not problems, problems
    drawn = with_stubs(process)
    expected[name] = {
        "shapes": len(read_page(OUT / name)[2]),
        "source_texts": sum(bool(s.quote.strip()) or s.assumed for s in drawn.steps),
        "stock": sorted({"Start/End", "Process", "Decision", "Dynamic connector"} if len(drawn.steps) > 4 else {"Start/End", "Process", "Dynamic connector"}),
    }
    print("wrote", OUT / name)
(OUT / "expected.json").write_text(json.dumps(expected, indent=1) + "\n")
print("wrote", write_xlsx(expense, OUT / "4-expense-claim-table.xlsx"))
