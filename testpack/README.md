# Test pack: the part only full Visio can answer

These files are already opened on every push by Microsoft's free Visio Viewer
and by LibreOffice, and both draw them correctly (see the main README). What
is left needs the full Visio program, because only it can show a "repair"
message and only it lets you move things.

| File | What it holds |
| --- | --- |
| `1-three-boxes.vsdx` | The least possible: start, two steps, end, three arrows. Nothing else. |
| `2-expense-claim.vsdx` | A title, rows per role, labelled arrows, a loop back, a dashed "Not stated" box, and the source sentence on each box. |
| `3-expense-claim-recalculated.vsdx` | The same, but asks Visio to recalculate everything on opening. |
| `4-expense-claim-table.xlsx` | The table for Visio's own "create diagram from data". |

## Three questions per .vsdx

1. Does it open with no "repair" or "problem with contents" message?
2. Drag a box. Do its arrows stay attached and re-route?
3. Files 2 and 3 side by side: does file 3 look any different?

Then upload the same files to Visio for the web and answer 1 and 2 again.

## For the .xlsx, in the desktop app

File > New > search "Data Visualizer" > Cross-Functional Flowchart > "Create diagram from data",
pick the workbook and the table `ProcessData`, and accept the column mapping
(Function is the row; Phase is empty).

1. Does the wizard accept the table?
2. Does the diagram have five rows with the right names?
3. Are Yes / No on the right arrows?

## What to send back

The file number, the question number, and what you saw. A screenshot or the
exact wording of any message helps most.
