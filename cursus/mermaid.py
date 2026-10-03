"""A quick picture of the flow that GitHub and most Markdown viewers draw, for checking a reading before opening Visio."""
from __future__ import annotations

import re

from cursus.model import Process, Step, with_stubs

_OPEN_CLOSE = {
    "start": ("([", "])"),
    "end": ("([", "])"),
    "task": ("[", "]"),
    "decision": ("{", "}"),
    "parallel": ("{{", "}}"),
    "subprocess": ("[[", "]]"),
    "document": ("[/", "/]"),
}


def _id(raw: str) -> str:
    return "n_" + re.sub(r"\W", "_", raw)


def _label(text: str) -> str:
    return '"' + text.replace('"', "#quot;").replace("\n", " ") + '"'


def _node(s: Step) -> str:
    a, b = _OPEN_CLOSE[s.kind]
    return f"{_id(s.id)}{a}{_label(s.text)}{b}"


def to_mermaid(p: Process) -> str:
    p = with_stubs(p)
    lines = ["flowchart LR"]
    if p.lanes:
        for lane in p.lanes:
            lines.append(f"  subgraph {_id(lane.id)}[{_label(lane.name)}]")
            lines += [f"    {_node(s)}" for s in p.steps if s.lane == lane.id]
            lines.append("  end")
    else:
        lines += [f"  {_node(s)}" for s in p.steps]
    for f in p.flows:
        arrow = f"-- {_label(f.label)} -->" if f.label else "-->"
        lines.append(f"  {_id(f.from_id)} {arrow} {_id(f.to_id)}")
    assumed = [_id(s.id) for s in p.steps if s.assumed]
    if assumed:
        lines.append("  classDef assumed stroke-dasharray: 5 5")
        lines.append(f"  class {','.join(assumed)} assumed")
    return "\n".join(lines) + "\n"
