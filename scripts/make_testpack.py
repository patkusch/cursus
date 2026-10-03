"""Writes the files in testpack/: the ones a person opens in Visio to answer what only Visio can."""
from pathlib import Path

from cursus.cli import load_reading
from cursus.datavis import write_xlsx
from cursus.visio import verify, write_vsdx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "testpack"

hello = load_reading(ROOT / "examples/hello/reading.json")
bare = hello.model_copy(deep=True)  # stock shapes and arrows only: no title, no source text
bare.title = ""
for step in bare.steps:
    step.quote = ""
expense = load_reading(ROOT / "examples/expense-claim/reading.json")

for name, process, recalc in (
    ("1-three-boxes.vsdx", bare, False),
    ("2-expense-claim.vsdx", expense, False),
    ("3-expense-claim-recalculated.vsdx", expense, True),
):
    problems = verify(write_vsdx(process, OUT / name, recalc=recalc))
    assert not problems, problems
    print("wrote", OUT / name)
print("wrote", write_xlsx(expense, OUT / "4-expense-claim-table.xlsx"))
