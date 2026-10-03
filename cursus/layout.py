"""Where every box and arrow goes on the page.

Lanes run left to right, stacked top to bottom. A step sits in the column
given by how far it is from the start, in the row of its lane. Arrows are
drawn with right-angle bends that keep clear of the boxes.

All sizes are in inches, measured from the bottom-left corner of the page,
because that is how Visio stores them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from cursus.model import Process

MM = 1 / 25.4

BOX_W = 25 * MM  # Visio's stock flowchart shapes are 25 mm wide
BOX_H = 15 * MM
TERMINATOR_H = 10 * MM  # Start/End is shorter
COL = 45 * MM  # column pitch: a box plus a 20 mm gap for arrows
ROW = 30 * MM  # row pitch inside a lane
HEADER_W = 10 * MM  # lane name strip on the left
MARGIN = 10 * MM
TITLE_H = 10 * MM
NUDGE = 2 * MM  # gap between arrows that share a channel
CHANNEL = ROW / 2 - 4 * MM  # how far from a row's middle its arrow channels run: clear of the boxes, clear of the lane line
A4_LANDSCAPE = (297 * MM, 210 * MM)

Point = tuple[float, float]


@dataclass
class Box:
    id: str
    cx: float
    cy: float
    w: float
    h: float
    col: int
    row: int

    @property
    def left(self) -> float:
        return self.cx - self.w / 2

    @property
    def right(self) -> float:
        return self.cx + self.w / 2

    @property
    def top(self) -> float:
        return self.cy + self.h / 2

    @property
    def bottom(self) -> float:
        return self.cy - self.h / 2


@dataclass
class Band:
    lane_id: str
    name: str
    x: float  # left edge
    y: float  # bottom edge
    w: float
    h: float


@dataclass
class Route:
    from_id: str
    to_id: str
    label: str
    points: list[Point]
    label_at: Point


@dataclass
class Layout:
    page_w: float
    page_h: float
    title: str
    title_at: Point
    boxes: dict[str, Box] = field(default_factory=dict)
    bands: list[Band] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)


# ------------------------------------------------------------------ columns


def _columns(p: Process) -> dict[str, int]:
    """Column = longest walk from a start, ignoring arrows that loop back."""
    exits: dict[str, list[str]] = {s.id: [] for s in p.steps}
    for f in p.flows:
        exits[f.from_id].append(f.to_id)

    loops: set[tuple[str, str]] = set()
    state: dict[str, int] = {}
    order: list[str] = []

    def walk(u: str) -> None:
        state[u] = 1
        for v in exits[u]:
            if state.get(v) == 1:
                loops.add((u, v))
            elif v not in state:
                walk(v)
        state[u] = 2
        order.append(u)

    for s in sorted(p.steps, key=lambda s: s.kind != "start"):
        if s.id not in state:
            walk(s.id)

    col = {s.id: 0 for s in p.steps}
    for u in reversed(order):  # reverse finishing order is a valid order for the loop-free arrows
        for v in exits[u]:
            if (u, v) not in loops:
                col[v] = max(col[v], col[u] + 1)
    return col


# ------------------------------------------------------------------ arrows


def _hits(boxes: list[Box], a: Point, b: Point, skip: tuple[str, ...]) -> bool:
    """Does the straight piece a-b cut through a box other than its own two?"""
    x1, x2 = sorted((a[0], b[0]))
    y1, y2 = sorted((a[1], b[1]))
    eps = 1e-6
    for bx in boxes:
        if bx.id in skip:
            continue
        if x2 > bx.left + eps and x1 < bx.right - eps and y2 > bx.bottom + eps and y1 < bx.top - eps:
            return True
    return False


def _clear(boxes: list[Box], pts: list[Point], skip: tuple[str, ...]) -> bool:
    return not any(_hits(boxes, pts[i], pts[i + 1], skip) for i in range(len(pts) - 1))


def _tidy(pts: list[Point]) -> list[Point]:
    """Drop repeated points and points in the middle of a straight run."""
    out: list[Point] = []
    for pt in pts:
        if out and abs(out[-1][0] - pt[0]) < 1e-9 and abs(out[-1][1] - pt[1]) < 1e-9:
            continue
        out.append(pt)
    i = 1
    while i < len(out) - 1:
        (ax, ay), (bx, by), (cx, cy) = out[i - 1], out[i], out[i + 1]
        if (abs(ax - bx) < 1e-9 and abs(bx - cx) < 1e-9) or (abs(ay - by) < 1e-9 and abs(by - cy) < 1e-9):
            del out[i]
        else:
            i += 1
    return out


class _Channels:
    """Hands out slightly different positions to arrows that run along the same gap, so they do not merge into one line."""

    def __init__(self) -> None:
        self.used: dict[tuple[str, float], int] = {}

    def take(self, axis: str, at: float) -> float:
        key = (axis, round(at, 6))
        n = self.used.get(key, 0)
        self.used[key] = n + 1
        step = (n + 1) // 2 * NUDGE
        return at + (step if n % 2 else -step)


def _route(u: Box, v: Box, branch: bool, boxes: list[Box], channels: _Channels) -> list[Point]:
    skip = (u.id, v.id)
    gap = (COL - BOX_W) / 2
    same_row = abs(u.cy - v.cy) < 1e-9

    if v.col > u.col:
        if same_row:
            straight = [(u.right, u.cy), (v.left, v.cy)]
            if _clear(boxes, straight, skip):
                return straight
        else:
            if branch:  # a decision's side exit: out of the top or bottom corner, then across
                edge = u.bottom if v.cy < u.cy else u.top
                elbow = [(u.cx, edge), (u.cx, v.cy), (v.left, v.cy)]
                if _clear(boxes, elbow, skip):
                    return elbow
            for mx in (u.right + gap, v.left - gap):
                if _clear(boxes, [(u.right, u.cy), (mx, u.cy), (mx, v.cy), (v.left, v.cy)], skip):
                    mx = channels.take("x", mx)
                    return [(u.right, u.cy), (mx, u.cy), (mx, v.cy), (v.left, v.cy)]
        # go round: along the gap between rows, where no box sits
        ch = channels.take("y", u.cy - CHANNEL if v.cy <= u.cy else u.cy + CHANNEL)
        x1, x2 = channels.take("x", u.right + gap), channels.take("x", v.left - gap)
        return [(u.right, u.cy), (x1, u.cy), (x1, ch), (x2, ch), (x2, v.cy), (v.left, v.cy)]

    if v.col == u.col:
        down = v.cy < u.cy
        straight = [(u.cx, u.bottom if down else u.top), (v.cx, v.top if down else v.bottom)]
        if _clear(boxes, straight, skip):
            return straight
        side = channels.take("x", u.right + gap)
        return [(u.right, u.cy), (side, u.cy), (side, v.cy), (v.right, v.cy)]

    # back to an earlier step: drop into the gap under the target's row and come up into it
    ch = channels.take("y", v.cy - CHANNEL)
    if u.cy > v.cy + 1e-9:  # the source sits above the target's row: go down its right-hand gap first
        side = channels.take("x", u.right + gap)
        return [(u.right, u.cy), (side, u.cy), (side, ch), (v.cx, ch), (v.cx, v.bottom)]
    start = (u.cx, u.bottom) if abs(u.cy - v.cy) < 1e-9 else (u.cx, u.top)
    return [start, (u.cx, ch), (v.cx, ch), (v.cx, v.bottom)]


def _label_point(pts: list[Point], labelled: bool) -> Point:
    """Decision labels sit near where the arrow leaves; a plain arrow's text handle sits mid-way along its longest piece."""
    if labelled:
        (ax, ay), (bx, by) = pts[0], pts[1]
        length = abs(bx - ax) + abs(by - ay)
        t = min(0.5, (7 * MM) / length) if length else 0.5
        return (ax + (bx - ax) * t, ay + (by - ay) * t)
    best = max(range(len(pts) - 1), key=lambda i: abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1]))
    (ax, ay), (bx, by) = pts[best], pts[best + 1]
    return ((ax + bx) / 2, (ay + by) / 2)


# ------------------------------------------------------------------ the page


def lay_out(p: Process) -> Layout:
    col = _columns(p)
    lanes = [(l.id, l.name) for l in p.lanes] or [("", "")]
    lane_index = {lane_id: i for i, (lane_id, _) in enumerate(lanes)}

    # steps that share a lane and a column stack into rows inside the lane
    cells: dict[tuple[int, int], list[str]] = {}
    for s in p.steps:
        cells.setdefault((lane_index.get(s.lane or "", 0), col[s.id]), []).append(s.id)
    rows_in_lane = [max((len(ids) for (li, _), ids in cells.items() if li == i), default=1) for i in range(len(lanes))]

    n_cols = max(col.values(), default=0) + 1
    header = HEADER_W if p.lanes else 0.0
    body_w = n_cols * COL
    body_h = sum(rows_in_lane) * ROW
    page_w = max(A4_LANDSCAPE[0], 2 * MARGIN + header + body_w)
    page_h = max(A4_LANDSCAPE[1], 2 * MARGIN + TITLE_H + body_h)

    left = MARGIN
    top = page_h - MARGIN - TITLE_H
    out = Layout(page_w=page_w, page_h=page_h, title=p.title, title_at=(left + (header + body_w) / 2, page_h - MARGIN - TITLE_H / 2))

    lane_top = top
    first_row = 0
    kinds = {s.id: s.kind for s in p.steps}
    for i, (lane_id, name) in enumerate(lanes):
        h = rows_in_lane[i] * ROW
        if p.lanes:
            out.bands.append(Band(lane_id=lane_id, name=name, x=left, y=lane_top - h, w=header + body_w, h=h))
        for (li, c), ids in cells.items():
            if li != i:
                continue
            for r, step_id in enumerate(ids):
                out.boxes[step_id] = Box(
                    id=step_id,
                    cx=left + header + (c + 0.5) * COL,
                    cy=lane_top - (r + 0.5) * ROW,
                    w=BOX_W,
                    h=TERMINATOR_H if kinds[step_id] in ("start", "end") else BOX_H,
                    col=c,
                    row=first_row + r,
                )
        lane_top -= h
        first_row += rows_in_lane[i]

    boxes = list(out.boxes.values())
    channels = _Channels()
    for f in p.flows:
        u, v = out.boxes[f.from_id], out.boxes[f.to_id]
        branch = kinds[f.from_id] == "decision"
        pts = _tidy(_route(u, v, branch, boxes, channels))
        out.routes.append(Route(from_id=f.from_id, to_id=f.to_id, label=f.label, points=pts, label_at=_label_point(pts, bool(f.label))))
    return out
