"""The question-and-answer loop.

A reading lists what the text leaves unsaid. `questions_markdown` turns that
list into a page the author fills in. The answers are then added to the end of
the text and the whole thing is read again, so an answered gap becomes an
ordinary step with an ordinary quote, taken from the author's answer.
"""
from __future__ import annotations

import re

from cursus.model import Process

ANSWER = "Answer:"
JOIN = "The author was asked about gaps in the text above and answered:"


def questions_markdown(p: Process) -> str:
    lines = [f"# Questions: {p.title}", "", f"Write each answer after \"{ANSWER}\". Leave it empty if you do not know.", ""]
    for i, q in enumerate(p.questions, 1):
        lines.append(f"## {i}. {' '.join(q.text.split())}")
        if q.about:
            try:
                lines.append(f"About the step: {p.step(q.about).text}")
            except KeyError:
                pass
        if q.quote:
            lines.append(f"The text says: \"{' '.join(q.quote.split())}\"")
        lines += ["", ANSWER + " ", ""]
    if not p.questions:
        lines.append("The reading raised no questions.")
    return "\n".join(lines) + "\n"


def parse_answers(markdown: str) -> list[tuple[str, str]]:
    """(question, answer) for every question that has an answer."""
    out: list[tuple[str, str]] = []
    for block in re.split(r"^## +", markdown, flags=re.M)[1:]:
        head, _, rest = block.partition("\n")
        question = re.sub(r"^\d+\.\s*", "", head).strip()
        if ANSWER not in rest:
            continue
        answer = " ".join(rest.split(ANSWER, 1)[1].split())
        if question and answer:
            out.append((question, answer))
    return out


def text_with_answers(source: str, answers_markdown: str) -> str:
    """The source text with the author's answers added at the end, as more text to read and quote from."""
    pairs = parse_answers(answers_markdown)
    if not pairs:
        return source
    body = "\n\n".join(f"Question: {q}\nAnswer: {a}" for q, a in pairs)
    return f"{source.rstrip()}\n\n{JOIN}\n\n{body}\n"
