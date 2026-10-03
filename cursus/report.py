"""A page a person can read: the picture, the open questions, and the sentence behind every box."""
from __future__ import annotations

from cursus.check import Finding
from cursus.mermaid import to_mermaid
from cursus.model import Process


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def to_markdown(p: Process, findings: list[Finding]) -> str:
    lane_name = {l.id: l.name for l in p.lanes}
    lines = [f"# {p.title}", "", "```mermaid", to_mermaid(p).rstrip(), "```", ""]

    lines += ["## Questions for the author", ""]
    if p.questions:
        for q in p.questions:
            about = f" (about: {p.step(q.about).text})" if q.about else ""
            lines.append(f"- {q.text}{about}")
            if q.quote:
                lines.append(f"  - The text says: \"{_cell(q.quote)}\"")
    else:
        lines.append("None.")
    lines.append("")

    lines += ["## Where each step came from", "", "| Step | Who | The text says |", "| --- | --- | --- |"]
    for s in p.steps:
        if s.kind in ("start", "end") and not s.quote:
            continue
        said = f"\"{_cell(s.quote)}\"" if s.quote else "*Not stated in the text*"
        lines.append(f"| {_cell(s.text)} | {_cell(lane_name.get(s.lane or '', ''))} | {said} |")
    lines.append("")

    lines += ["## Checks", ""]
    if findings:
        lines += [f"- **{f.level}** ({f.where}): {f.message}" for f in findings]
    else:
        lines.append("All passed.")
    return "\n".join(lines) + "\n"
