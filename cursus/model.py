"""The process as data: who does what, in what order, and where the text says so.

A model reads the source text and fills this in (see prompts.py). Everything
after that is plain code: check.py tests it, and the writers draw it.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["start", "task", "decision", "parallel", "subprocess", "document", "end"]

# Start and end are drawn so the flow has edges; the text rarely says "the process starts".
NEEDS_QUOTE: frozenset[str] = frozenset({"task", "decision", "parallel", "subprocess", "document"})


class Lane(BaseModel):
    id: str
    name: str = Field(description="Who does the work, as the text names them")


class Step(BaseModel):
    id: str
    kind: Kind
    text: str = Field(description="Short label, verb first, six words or fewer")
    lane: Optional[str] = Field(default=None, description="Lane id of whoever does this step")
    quote: str = Field(default="", description="The passage this step came from, copied word for word")
    assumed: bool = Field(default=False, description="True when the text does not state this step")


class Flow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_id: str = Field(alias="from")
    to_id: str = Field(alias="to")
    label: str = Field(default="", description="The answer that leads this way, on exits from a decision")
    quote: str = ""


class Question(BaseModel):
    about: str = Field(default="", description="Step id the question is about, if any")
    text: str
    quote: str = ""


class Process(BaseModel):
    title: str
    lanes: list[Lane] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    flows: list[Flow] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)

    def step(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)

    def out_of(self, step_id: str) -> list[Flow]:
        return [f for f in self.flows if f.from_id == step_id]

    def into(self, step_id: str) -> list[Flow]:
        return [f for f in self.flows if f.to_id == step_id]


NOT_STATED = "Not stated"

_FOLD = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u00a0": " "})


def fold(text: str) -> str:
    """Lower case, straight quotes, single spaces: differences a reader would not call a different sentence."""
    return re.sub(r"\s+", " ", text.translate(_FOLD)).strip().lower()


def _same_passage(a: str, b: str) -> bool:
    a, b = fold(a).strip(" .\"'"), fold(b).strip(" .\"'")
    return bool(a) and bool(b) and (a in b or b in a)


def asked_about(p: Process, decision: Step) -> bool:
    """Is there a question about this decision? Named by id, or, when the question names no step, by quoting the same passage."""
    return any(q.about == decision.id or (not q.about and _same_passage(q.quote, decision.quote)) for q in p.questions)


def open_decisions(p: Process) -> list[Step]:
    """Decisions with one exit that the reader asked a question about, instead of inventing the other exit."""
    return [s for s in p.steps if s.kind == "decision" and len(p.out_of(s.id)) == 1 and asked_about(p, s)]


def settle(p: Process) -> Process:
    """Tidy the parts of a reading that code can settle without guessing. Changes `p` and returns it.

    A step that quotes the text is a claim about the text, so it is checked as
    one and cannot call itself assumed. A start or end left without a lane
    takes the lane of the step next to it: they are drawn for the reader, and
    the text never says whose they are.
    """
    lanes = {l.id for l in p.lanes}
    by_id = {s.id: s for s in p.steps}
    for s in p.steps:
        if s.quote.strip():
            s.assumed = False
        if not lanes or s.lane is not None or s.kind not in ("start", "end"):
            continue
        beside = [f.to_id for f in p.flows if f.from_id == s.id] if s.kind == "start" else [f.from_id for f in p.flows if f.to_id == s.id]
        for other in beside:
            if other in by_id and by_id[other].lane in lanes:
                s.lane = by_id[other].lane
                break
    return p


def with_stubs(p: Process) -> Process:
    """A copy where every open decision gets a dashed "Not stated" end, so the gap is drawn, not hidden."""
    out = p.model_copy(deep=True)
    taken = {s.id for s in out.steps}
    for d in open_decisions(p):
        stub_id = f"{d.id}_not_stated"
        while stub_id in taken:
            stub_id += "_"
        taken.add(stub_id)
        out.steps.append(Step(id=stub_id, kind="end", text=NOT_STATED, lane=d.lane, assumed=True))
        out.flows.append(Flow(from_id=d.id, to_id=stub_id, label="?"))
    return out
