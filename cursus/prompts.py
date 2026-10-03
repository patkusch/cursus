"""The instructions given to whichever model reads the source text.

The reading is the only step a model does. It can come from any model: paste
the prompt into a chat, or wire up an API. The answer is a JSON file that
check.py then tests against the same source text.
"""
from __future__ import annotations

import json

from cursus.model import Process

RULES = """\
You are turning a written description of a process into a flow. The result will
be drawn as a diagram and checked, line by line, against the text below.

Rules

1. Use only what the text says. Do not add steps, checks or outcomes that a
   sensible process would have but this text does not mention.
2. Every task, decision, sub-process and document carries a `quote`: the
   passage it came from, copied word for word from the text, as one unbroken
   run of words. A quote that is not in the text fails the check.
3. When the text says what happens one way but not the other (it says what
   happens when a request is approved, but never what happens when it is
   refused), do not invent the missing path. Give the decision the one exit the
   text states, and add a question about it to `questions` with `about` set to
   that decision's id.
4. Add a question for anything else a reader would need to ask the author:
   a step with no stated owner, two passages that disagree, a term that could
   mean two things.
5. A `decision` is one question with a labelled exit per answer ("Yes", "No",
   "Over 500"). Only decisions have more than one exit. If work splits into
   branches that all happen at the same time, use a `parallel` step to split
   and another to join.
6. `lanes` are the people, teams or systems the text names as doing the work.
   If the text names them, every step sits in one lane. If it never says who
   does anything, leave `lanes` empty and `lane` unset.
7. Step `text` is a short label: verb first, six words or fewer. A decision's
   text is the question it asks.
8. One `start`. An `end` wherever the process stops; there can be several.
   Start and end need no quote.
9. Ids are short and unique: s1, s2, d1. Every arrow in `flows` joins two ids
   that exist.

{extra}Answer with one JSON object and nothing else. It must match this layout:

{schema}

The text:

<<<
{source}
>>>
"""


ANSWERED = """\
10. The text ends with questions the author has already answered. Treat each
    answer as part of the text: build steps from it and quote from it like any
    other passage. Do not ask a question that has been answered.

"""


def reading_prompt(source: str, *, has_answers: bool = False) -> str:
    schema = json.dumps(Process.model_json_schema(by_alias=True), indent=1)
    return RULES.format(schema=schema, source=source.strip(), extra=ANSWERED if has_answers else "")
