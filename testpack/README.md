# Test pack: open these in Visio

Nothing here has been opened in Visio yet. These four files answer the
questions only Visio can. Go in order: each file adds one thing, so the first
one that misbehaves tells us what to fix.

| File | What it adds |
| --- | --- |
| `1-three-boxes.vsdx` | The least possible: start, two steps, end, three arrows. Nothing else. |
| `2-expense-claim.vsdx` | A title, rows per role, labelled arrows, a loop back, a dashed "Not stated" box, and the source sentence on each box. |
| `3-expense-claim-recalculated.vsdx` | The same, but asks Visio to recalculate everything on opening. |
| `4-expense-claim-table.xlsx` | The table for Visio's own "create diagram from data". |

## For each .vsdx, in the desktop app

1. Does it open with no "repair" or "problem with contents" message?
2. Does it look like `docs/expense-claim.svg` (files 2 and 3)?
3. Drag a box. Do its arrows stay attached and re-route?
4. Click a box, then open Data > Shape Data Window. Is there a "Source text" line with a sentence in it?
5. Do the arrow labels (Yes / No / ?) sit on their arrows?
6. Files 2 and 3 side by side: does file 3 look different? (Text fitting its box better is the hope.)

Then upload the same files to Visio for the web and answer 1 to 3 again.

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

If you can, also save one blank file from your own Visio: File > New >
Cross-Functional Flowchart, drop one Subprocess and one Document shape on it,
save as `seed.vsdx`. That lets us stop borrowing someone else's starting file
and adds the two shapes we are missing.
