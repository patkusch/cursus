"""The Excel table that Visio's own "create diagram from data" feature reads.

Visio (desktop, Plan 2) turns this table into a flowchart with real swimlanes
and lays it out itself. The column names are the ones Visio's template uses.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo

from cursus.model import Process, with_stubs

COLUMNS = [
    "Process Step ID",
    "Process Step Description",
    "Next Step ID",
    "Connector Label",
    "Shape Type",
    "Function",
    "Phase",
    "Alt Description",
]
SHAPE_TYPE = {
    "start": "Start",
    "end": "End",
    "task": "Process",
    "decision": "Decision",
    "subprocess": "Subprocess",
    "document": "Document",
    "parallel": "Custom 1",
}


def _one(text: str) -> str:
    """Visio splits these cells on commas, so a comma inside a value would add a phantom arrow."""
    return text.replace(",", ";").strip()


def rows(p: Process) -> list[list[str]]:
    p = with_stubs(p)
    lane_name = {l.id: l.name for l in p.lanes}
    out = []
    for s in p.steps:
        exits = p.out_of(s.id)
        labels = [_one(f.label) for f in exits]
        out.append([
            s.id,
            s.text,
            ",".join(f.to_id for f in exits),
            ",".join(labels) if any(labels) else "",
            SHAPE_TYPE[s.kind],
            lane_name.get(s.lane or "", ""),
            "",
            s.quote or ("Not stated in the text" if s.assumed else ""),
        ])
    return out


def write_xlsx(p: Process, path: Path | str) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Process Map"
    ws.append(COLUMNS)
    data = rows(p)
    for row in data:
        ws.append(row)
    table = Table(displayName="ProcessData", ref=f"A1:H{len(data) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)
    for letter, width in zip("ABCDEFGH", (16, 42, 18, 18, 14, 22, 12, 60)):
        ws.column_dimensions[letter].width = width
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
