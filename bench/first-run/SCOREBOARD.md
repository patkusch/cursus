# Scoreboard: first run, 3 October 2026

Kept as a record. These are the numbers from the first time the models were run, scored by the tool as it was that day.
The run showed the tool refusing some readings that were right; see [the current scoreboard](../SCOREBOARD.md) for what changed.

Each model read 11 process descriptions. Every reading was scored against a reference written by hand.
A reading the checks refuse is never drawn, so it scores zero on everything: the numbers are what a user would get.

Scores run from 0 to 1, and 1 means the same as the reference. The range in brackets is the lowest and highest of the runs.

| Model | Runs | Drawn | Steps found | Steps right | Arrows found | Arrows right | Decisions found | Right role | Gaps asked | Gaps guessed | Seconds per reading |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:12b | 3 | 0.58 (0.55–0.64) | 0.51 (0.47–0.55) | 0.48 (0.44–0.52) | 0.42 (0.38–0.45) | 0.41 (0.36–0.44) | 0.53 (0.48–0.58) | 0.18 (0.18–0.18) | 2 of 12 | 2 of 12 | 154 |
| gemma3:latest | 3 | 0.15 (0.09–0.18) | 0.12 (0.09–0.14) | 0.14 (0.07–0.18) | 0.09 (0.07–0.10) | 0.10 (0.06–0.12) | 0.15 (0.09–0.18) | 0.15 (0.09–0.18) | 0 of 12 | 0 of 12 | 67 |

## Case by case

Readings drawn out of the runs made, then the share of the reference's steps found.

| Case | Steps | gemma3:12b | gemma3:latest |
| --- | --- | --- | --- |
| customer-refund | 8 | 2 of 3 drawn, 0.58 | 0 of 3 drawn, 0.00 |
| document-review | 5 | 3 of 3 drawn, 1.00 | 1 of 3 drawn, 0.20 |
| expense-claim | 13 | 3 of 3 drawn, 0.90 | 0 of 3 drawn, 0.00 |
| incident-triage | 9 | 0 of 3 drawn, 0.00 | 0 of 3 drawn, 0.00 |
| invoice-payment | 9 | 0 of 3 drawn, 0.00 | 0 of 3 drawn, 0.00 |
| leave-request | 6 | 3 of 3 drawn, 0.89 | 2 of 3 drawn, 0.56 |
| loan-application | 8 | 0 of 3 drawn, 0.00 | 0 of 3 drawn, 0.00 |
| new-starter | 7 | 0 of 3 drawn, 0.00 | 1 of 3 drawn, 0.24 |
| order-packing | 4 | 3 of 3 drawn, 1.00 | 1 of 3 drawn, 0.33 |
| purchase-order | 6 | 2 of 3 drawn, 0.44 | 0 of 3 drawn, 0.00 |
| support-ticket-interview | 8 | 3 of 3 drawn, 0.75 | 0 of 3 drawn, 0.00 |

What the columns mean:

- **Drawn**: readings that passed every check and would be drawn.
- **Steps found**: of the steps in the reference, the share the reading has.
- **Steps right**: of the steps in the reading, the share that are in the reference.
- **Arrows found**: of the arrows in the reference, the share the reading has.
- **Arrows right**: of the arrows in the reading, the share that are in the reference.
- **Decisions found**: of the decisions in the reference, the share the reading has.
- **Right role**: of the matched steps, the share given to the right person or team.
- **Gaps asked**: places where the text does not say what happens, and the reading asked instead of making something up.
- **Gaps guessed**: the same places, where the reading drew a second way out without asking.

Run 1 reads the way `cursus read` does. Later runs let the model vary, to show how much the result moves.
The reference decides how finely the work is cut, so a reading that splits or merges steps loses a little even when a person would call it right.
