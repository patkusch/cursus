# cursus

Turns a written description of a process into a Visio flow chart, and shows
which sentence each box came from.

![An expense-claim process drawn as a flow chart with one row per role](docs/expense-claim.svg)

That picture was made from [sixteen lines of plain text](examples/expense-claim/process.txt).
The dashed box is deliberate. The text says a large claim needs the finance
director's sign-off, but never says what happens when the director says no.
cursus draws that gap and asks about it, instead of making up an answer.

## Why

Drawing a process in Visio by hand is slow. The tools that draw one for you
either need Visio installed, or hand back a picture whose arrows fall off when
you move a box. And none of them tell you where a box came from, so you cannot
tell a step the author wrote from a step the tool invented.

## What you get

For one description, four files:

| File | What it is for |
| --- | --- |
| `name.vsdx` | The flow chart, to open and edit in Visio. Each box carries its source sentence. |
| `name.xlsx` | The same flow as a table that Visio's own "create diagram from data" feature reads. |
| `name.svg` | A picture of what the Visio file holds, for anyone without Visio. |
| `name.md` | The questions to ask the author, and the sentence behind every step. |

## Where it stands

| Part | State |
| --- | --- |
| Checking a reading against the text | Built and tested. |
| Excel table for Visio | Built. Not yet tried in Visio. |
| Visio file | Built. **Not yet opened in Visio.** See [testpack](testpack/README.md). |
| Rows per role | Drawn as plain rectangles. Visio's own swimlanes come next. |
| Reading the text with a model | Built for models running on your own machine through Ollama. Any other model works by copy and paste. |
| Asking the author about gaps | Built. Answers are added to the text and the flow is redrawn. |
| Scoreboard | Built. See [how well models read](#how-well-models-read). |

## Try it

```bash
pip install -e ".[dev]"
```

```bash
cursus build examples/expense-claim/reading.json --source examples/expense-claim/process.txt
```

To start from your own text, with a model running on your machine
([Ollama](https://ollama.com)); nothing leaves the computer:

```bash
cursus read my-process.txt --model gemma3:12b -o reading.json
```

```bash
cursus build reading.json --source my-process.txt
```

The reading is checked as soon as it comes back. If it fails, the faults go
back to the model for another try, twice at most.

To use any other model, by copy and paste:

```bash
cursus prompt my-process.txt -o prompt.md
```

Give `prompt.md` to the model and save its answer as `reading.json`.

## Closing the gaps

When the text does not say what happens, cursus asks instead of guessing.

```bash
cursus questions reading.json -o answers.md
```

Write the answers into `answers.md`, then read and build again with
`--answers answers.md`. The answers become part of the text, so a step that
comes from an answer quotes the answer.

| Before | After the author answered one question |
| --- | --- |
| ![Flow with a dashed "Not stated" box](docs/expense-claim.svg) | ![Flow where the dashed box is replaced by a real step](docs/expense-claim-answered.svg) |

The answer given was: *"If the finance director refuses, finance rejects the
claim and tells the employee why."*

## How well models read

A drawing is only as good as the reading behind it. [bench/cases](bench/cases)
holds eleven process descriptions, each with a reference reading written by
hand. A model reads each one several times and every reading is scored against
the reference: steps found, arrows that agree, the right role on each step,
and whether a gap in the text was asked about or papered over.

Results are in [bench/SCOREBOARD.md](bench/SCOREBOARD.md), and
[bench/README.md](bench/README.md) says what they show. In short, for two
models that run on a laptop:

- The larger one (Gemma 3, 12B) produced a drawable reading 23 times out of 33, and asked about a gap instead of guessing 9 times out of 12. It usually left out who does each step.
- The smaller one (Gemma 3, 4B) managed 7 out of 33. It is not usable for this.

```bash
cursus score --model gemma3:12b --runs 3
```

The references were written for this project by the same hands as the tool.
Public sets of process descriptions are not in yet.

## What gets checked before anything is drawn

A reading with any of these faults is refused, not drawn:

- A step whose quote is not in the text, word for word.
- A step with no quote that is not marked as a guess.
- An arrow pointing at a step that does not exist.
- A decision with one way out, unless a question owns up to the gap.
- Two exits from a decision with the same label, or no label.
- Two arrows leaving a step that is not a decision.
- A step nothing leads to, or a path that never reaches an end.

## How the Visio file is made

For engineers. The plain version ends above.

- cursus never builds a Visio file from nothing. It starts from a file Visio
  itself saved ([cursus/seed](cursus/seed/NOTICE)) and replaces only the
  drawing on the page.
- Steps are Visio's stock Process, Decision and Start/End shapes, so they look
  and behave like shapes dropped from the stencil.
- Arrows are Visio's stock dynamic connector, glued to the shape at both ends
  with the same formulas and `Connect` records Visio writes. Move a box and the
  arrow should follow.
- The source sentence is stored as shape data ("Source text") on each box.
- Positions are worked out by cursus: one column per step along the flow, one
  row per role, right-angle arrows that keep clear of the boxes.
- `verify` re-opens the written file and tests what can be tested without
  Visio: every part is valid XML, every link inside the file resolves, every
  arrow is attached at both ends to a shape that exists. It cannot tell whether
  Visio will ask to repair the file. Only Visio can.

## Not built yet

- Visio's own swimlanes (rows that boxes belong to, not rectangles behind them).
- Sub-process and document shapes (drawn as a Process box for now).
- Calling a hosted model directly (local models work today; hosted ones by copy and paste).
- Public reference sets on the scoreboard, next to our own eleven cases.

## Credits

The starting file comes from [vsdxkit](https://github.com/firmfooting/vsdxkit)'s
reference files (BSD 3-Clause). See [cursus/seed/NOTICE](cursus/seed/NOTICE).
