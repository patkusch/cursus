# What the scoreboard shows

The numbers are in [SCOREBOARD.md](SCOREBOARD.md). This page says what they mean.

## What we learned (3 October 2026)

Two models that run on a laptop were tested: Gemma 3 in its 12B size
(`gemma3:12b`) and its 4B size (`gemma3:latest`). Each read all eleven cases
three times, 33 readings per model.

**The larger model is usable, with two blind spots.**

- 23 of its 33 readings passed every check and would be drawn.
- When a reading is drawn it finds most of the steps: 0.75 to 1.00 of them on seven of the eight cases it could draw.
- It asked about a gap in the text 9 times out of 12, and guessed twice.
- It left out who does each step in 31 of 33 readings, although the text names them. That is why "Right role" is 0.18.
- It failed all three readings of three cases. Two of them have work that happens at the same time, which it drew as two arrows leaving a plain step. In the third it left a path with no end.

**The smaller model is not usable for this.** 7 of its 33 readings were drawn, and 3 of those were the simplest case.

**It is slow.** About two and a half minutes per reading for the larger model on a laptop (Apple M5, 16 GB), one minute for the smaller.

## What changed since the first run

The first run is kept as a record in [first-run/SCOREBOARD.md](first-run/SCOREBOARD.md).
It showed the tool, not the models, getting two things wrong:

1. A reading that asked the right question about a gap was refused when the question did not name the decision it was about, even though it quoted the same sentence. The tool now accepts that.
2. A reading was refused when its Start or End box had no role. The tool now gives them the role of the step next to them.

| | Drawn, first run | Drawn, after the two fixes |
| --- | --- | --- |
| gemma3:12b | 19 of 33 | 23 of 33 |
| gemma3:latest (4B) | 5 of 33 | 7 of 33 |

The current table re-scores the same saved readings. The models were not run
again. A fresh run could come out differently: a reading that now passes first
time would not have been sent back for another try.

The wording of two fault messages was also made clearer. That only affects
future runs.

## Limits

- Eleven cases is a small set, and the references were written by the same hands as the tool.
- The instructions given to the model were written before ten of the eleven cases existed, and have not been changed to suit them. The expense-claim case was the worked example while building.
- The reference decides how finely the work is cut. A reading that splits one step in two loses a little even when a person would call it right.
- No hosted model has been scored yet.

## Run it yourself

```bash
cursus score --model gemma3:12b --runs 3
```

Every reading is saved in [results](results), so the table can be rebuilt
without running a model:

```bash
cursus score --table
```
