"""Tests a reading before anything is drawn.

Two kinds of test. Shape: does the flow hold together (one way in, every path
reaches an end, every decision has labelled exits). Source: is every quote
really in the text. A reading with errors is not drawn.
"""
from __future__ import annotations

from collections import Counter
from typing import Literal, Optional

from pydantic import BaseModel

from cursus.model import NEEDS_QUOTE, Process, fold, open_decisions


class Finding(BaseModel):
    level: Literal["error", "warning"]
    code: str
    where: str
    message: str

    def line(self) -> str:
        return f"{self.level.upper():7} {self.code:18} {self.where:14} {self.message}"


def _err(code: str, where: str, message: str) -> Finding:
    return Finding(level="error", code=code, where=where, message=message)


def _warn(code: str, where: str, message: str) -> Finding:
    return Finding(level="warning", code=code, where=where, message=message)


# ------------------------------------------------------------------ shape


def _reach(starts: list[str], edges: dict[str, list[str]]) -> set[str]:
    seen = set(starts)
    todo = list(starts)
    while todo:
        for nxt in edges.get(todo.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def check_shape(p: Process) -> list[Finding]:
    out: list[Finding] = []
    ids = [s.id for s in p.steps]
    known = set(ids)
    lane_ids = [l.id for l in p.lanes]

    for dup, n in Counter(ids).items():
        if n > 1:
            out.append(_err("duplicate-id", dup, f"{n} steps share this id"))
    for dup, n in Counter(lane_ids).items():
        if n > 1:
            out.append(_err("duplicate-lane", dup, f"{n} lanes share this id"))

    for s in p.steps:
        if not s.text.strip():
            out.append(_err("no-text", s.id, "the step has no label"))
        if p.lanes and s.lane is None:
            out.append(_err("no-lane", s.id, "the process has lanes but this step is in none"))
        if s.lane is not None and s.lane not in lane_ids:
            out.append(_err("unknown-lane", s.id, f"lane '{s.lane}' is not defined"))

    good_flows = []
    seen_pairs: set[tuple[str, str]] = set()
    for f in p.flows:
        where = f"{f.from_id}->{f.to_id}"
        if f.from_id not in known or f.to_id not in known:
            missing = f.from_id if f.from_id not in known else f.to_id
            out.append(_err("unknown-step", where, f"the arrow points at '{missing}', which is not a step"))
            continue
        if f.from_id == f.to_id:
            out.append(_err("self-loop", where, "the arrow leaves and enters the same step"))
            continue
        if (f.from_id, f.to_id) in seen_pairs:
            out.append(_warn("duplicate-arrow", where, "two arrows join the same pair of steps"))
        seen_pairs.add((f.from_id, f.to_id))
        good_flows.append(f)

    fwd: dict[str, list[str]] = {}
    back: dict[str, list[str]] = {}
    for f in good_flows:
        fwd.setdefault(f.from_id, []).append(f.to_id)
        back.setdefault(f.to_id, []).append(f.from_id)

    starts = [s.id for s in p.steps if s.kind == "start"]
    ends = [s.id for s in p.steps if s.kind == "end"]
    if not starts:
        out.append(_err("no-start", "-", "the process has no start"))
    if len(starts) > 1:
        out.append(_warn("many-starts", "-", f"the process has {len(starts)} starts"))
    if not ends:
        out.append(_err("no-end", "-", "the process has no end"))

    open_ids = {s.id for s in open_decisions(p)}
    for s in p.steps:
        exits = [f for f in good_flows if f.from_id == s.id]
        if s.kind == "start" and back.get(s.id):
            out.append(_err("start-has-entry", s.id, "an arrow leads into the start"))
        if s.kind == "end":
            if exits:
                out.append(_err("end-has-exit", s.id, "an arrow leaves an end"))
            continue
        if not exits:
            out.append(_err("dead-end", s.id, "the flow stops here without reaching an end"))
            continue
        if s.kind == "decision":
            if len(exits) < 2:
                if s.id in open_ids:
                    out.append(_warn("open-decision", s.id, "the text gives one exit only; the other is drawn as 'Not stated'"))
                else:
                    out.append(_err("one-exit-decision", s.id, f"this decision has one exit: add the other if the text states it, otherwise add a question with `about` set to '{s.id}' asking what the text leaves out"))
            labels = [f.label.strip().lower() for f in exits]
            if any(not l for l in labels):
                out.append(_err("unlabelled-exit", s.id, "every exit from a decision needs a label, such as Yes or No"))
            if len(set(labels)) < len(labels):
                out.append(_err("repeated-label", s.id, "two exits from this decision carry the same label"))
        elif s.kind != "parallel" and len(exits) > 1:
            out.append(_err("hidden-decision", s.id, "two arrows leave a step that is not a decision"))

    if starts and ends:
        from_start = _reach(starts, fwd)
        to_end = _reach(ends, back)
        for s in p.steps:
            if s.id not in from_start:
                out.append(_err("unreachable", s.id, "no path leads here from the start"))
            elif s.id not in to_end and fwd.get(s.id):
                out.append(_err("no-way-out", s.id, "no path from here reaches an end"))

    for q in p.questions:
        if q.about and q.about not in known:
            out.append(_err("unknown-step", f"question:{q.about}", "the question is about a step that does not exist"))
    return out


# ------------------------------------------------------------------ source

def quote_found(quote: str, source: str) -> bool:
    q = fold(quote).strip(" .\"'")
    return bool(q) and q in fold(source)


def check_source(p: Process, source: str) -> list[Finding]:
    out: list[Finding] = []
    for s in p.steps:
        if s.assumed:
            out.append(_warn("assumed", s.id, f"'{s.text}' is not stated in the text"))
            continue
        if s.kind not in NEEDS_QUOTE and not s.quote:
            continue
        if not s.quote.strip():
            out.append(_err("no-quote", s.id, f"'{s.text}' has no quote and is not marked as assumed"))
        elif not quote_found(s.quote, source):
            out.append(_err("quote-not-found", s.id, f"the quote is not in the text: \"{s.quote}\""))
    for f in p.flows:
        if f.quote.strip() and not quote_found(f.quote, source):
            out.append(_err("quote-not-found", f"{f.from_id}->{f.to_id}", f"the quote is not in the text: \"{f.quote}\""))
    for i, q in enumerate(p.questions, 1):
        if q.quote.strip() and not quote_found(q.quote, source):
            out.append(_err("quote-not-found", f"question {i}", f"the quote is not in the text: \"{q.quote}\""))
    return out


def check(p: Process, source: Optional[str] = None) -> list[Finding]:
    findings = check_shape(p)
    if source is not None:
        findings += check_source(p, source)
    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(f.level == "error" for f in findings)
