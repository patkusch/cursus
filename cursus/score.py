"""How close is a reading to a reference reading of the same text?

Steps are paired up first. Both readings quote the same text, so two steps
that quote the same passage and carry similar labels are taken to be the same
step. Everything else is counted from those pairs: which steps were found,
which arrows agree, whether the right role does each step, and whether a gap
in the text was asked about or papered over.

The reference decides how finely the work is cut. A reading that splits one
reference step in two, or merges two into one, loses a little on steps and
arrows even when a person would call it right.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from cursus.check import fold
from cursus.model import NEEDS_QUOTE, Process, Step, open_decisions

MATCH_AT = 0.4  # pair two steps when 0.6 x quote overlap + 0.4 x label likeness reaches this
_STOP = frozenset("a an the to of for in on at by with and or is are it its be been this that then their them they we i".split())


def words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOP:
            continue
        for tail in ("ing", "ed", "es", "s"):
            if len(w) > len(tail) + 2 and w.endswith(tail) and not w.endswith("ss"):
                w = w[: -len(tail)]
                break
        out.add(w[:-1] if len(w) > 3 and w.endswith("e") else w)  # approve, approves, approved -> approv
    return out


def likeness(a: str, b: str) -> float:
    """Share of words two labels have in common, ignoring endings and filler words."""
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def span(quote: str, folded_source: str) -> tuple[int, int] | None:
    q = fold(quote).strip(" .\"'")
    at = folded_source.find(q) if q else -1
    return (at, at + len(q)) if at >= 0 else None


def overlap(a: tuple[int, int] | None, b: tuple[int, int] | None) -> float:
    """How much of the shorter passage lies inside the other."""
    if a is None or b is None:
        return 0.0
    shared = min(a[1], b[1]) - max(a[0], b[0])
    return max(0.0, shared / min(a[1] - a[0], b[1] - b[0]))


def _family(step: Step) -> str:
    return step.kind if step.kind in ("decision", "parallel") else "work"


def pair_steps(ref: Process, cand: Process, source: str) -> dict[str, str]:
    """reference step id -> the reading's step id, each used once, best pairs first."""
    text = fold(source)
    scored = []
    for r in ref.steps:
        if r.kind not in NEEDS_QUOTE:
            continue
        r_span = span(r.quote, text)
        for c in cand.steps:
            if c.kind not in NEEDS_QUOTE or _family(c) != _family(r):
                continue
            s = 0.6 * overlap(r_span, span(c.quote, text)) + 0.4 * likeness(r.text, c.text)
            if s >= MATCH_AT:
                scored.append((s, r.id, c.id))
    pairs: dict[str, str] = {}
    taken: set[str] = set()
    for _, r_id, c_id in sorted(scored, key=lambda t: -t[0]):
        if r_id not in pairs and c_id not in taken:
            pairs[r_id] = c_id
            taken.add(c_id)
    return pairs


def _arrows(p: Process, name: dict[str, str]) -> set[tuple[str, str]]:
    kind = {s.id: s.kind for s in p.steps}

    def node(step_id: str) -> str:
        if kind.get(step_id) == "start":
            return "START"
        if kind.get(step_id) == "end":
            return "END"
        return name.get(step_id, f"?{step_id}")

    return {(node(f.from_id), node(f.to_id)) for f in p.flows if f.from_id in kind and f.to_id in kind}


def _share(part: int, whole: int) -> float:
    return part / whole if whole else 1.0


@dataclass
class Score:
    steps_found: float  # of the reference's steps, the share the reading has
    steps_right: float  # of the reading's steps, the share that are in the reference
    arrows_found: float
    arrows_right: float
    decisions_found: float
    roles_right: float  # of the paired steps, the share placed with the right role
    gaps: int  # places where the text is silent and the reference asks a question
    gaps_asked: int  # the reading asked too
    gaps_guessed: int  # the reading drew a second way out instead of asking

    def as_dict(self) -> dict:
        return asdict(self)


def score(ref: Process, cand: Process, source: str) -> Score:
    pairs = pair_steps(ref, cand, source)
    back = {c: r for r, c in pairs.items()}
    ref_work = [s for s in ref.steps if s.kind in NEEDS_QUOTE]
    cand_work = [s for s in cand.steps if s.kind in NEEDS_QUOTE]

    ref_arrows = _arrows(ref, {s.id: s.id for s in ref.steps})
    cand_arrows = _arrows(cand, back)
    agreed = ref_arrows & cand_arrows

    ref_decisions = [s for s in ref_work if s.kind == "decision"]

    lane_name = {l.id: l.name for l in ref.lanes}
    cand_lane = {l.id: l.name for l in cand.lanes}
    placed = [s for s in ref_work if s.kind != "parallel" and s.lane and s.id in pairs]
    right_role = 0
    for s in placed:
        theirs = cand_lane.get(cand.step(pairs[s.id]).lane or "", "")
        mine = lane_name.get(s.lane or "", "")
        if theirs and (likeness(mine, theirs) >= 0.5 or words(mine) <= words(theirs) or words(theirs) <= words(mine)):
            right_role += 1

    text = fold(source)
    gaps = open_decisions(ref)
    asked = guessed = 0
    for d in gaps:
        theirs = pairs.get(d.id)
        ref_q = next(q for q in ref.questions if q.about == d.id)
        here = span(d.quote, text)
        cand_quote = {s.id: s.quote for s in cand.steps}
        raised = any(
            (theirs and q.about == theirs)  # asked about the same decision
            or overlap(span(q.quote, text), span(ref_q.quote, text)) >= 0.5  # or about the same passage
            or overlap(span(cand_quote.get(q.about, ""), text), here) >= 0.5  # or about a step drawn from that passage
            for q in cand.questions
        )
        if raised:
            asked += 1
        elif theirs and len(cand.out_of(theirs)) >= 2:
            guessed += 1

    return Score(
        steps_found=_share(len(pairs), len(ref_work)),
        steps_right=_share(len(pairs), len(cand_work)),
        arrows_found=_share(len(agreed), len(ref_arrows)),
        arrows_right=_share(len(agreed), len(cand_arrows)),
        decisions_found=_share(sum(d.id in pairs for d in ref_decisions), len(ref_decisions)),
        roles_right=_share(right_role, len(placed)) if any(s.lane for s in ref_work) else 1.0,
        gaps=len(gaps),
        gaps_asked=asked,
        gaps_guessed=guessed,
    )


ZERO = Score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0)
