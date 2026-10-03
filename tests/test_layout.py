from cursus.layout import BOX_W, COL, lay_out
from cursus.model import with_stubs


def test_no_two_boxes_overlap(expense):
    boxes = list(lay_out(with_stubs(expense)).boxes.values())
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            apart = a.right <= b.left or b.right <= a.left or a.top <= b.bottom or b.top <= a.bottom
            assert apart, f"{a.id} overlaps {b.id}"


def test_every_step_sits_inside_its_lane(expense):
    p = with_stubs(expense)
    layout = lay_out(p)
    band = {b.lane_id: b for b in layout.bands}
    for s in p.steps:
        box, lane = layout.boxes[s.id], band[s.lane]
        assert lane.y < box.bottom and box.top < lane.y + lane.h
        assert lane.x < box.left and box.right < lane.x + lane.w


def test_flow_runs_left_to_right_and_loops_go_back(expense):
    layout = lay_out(with_stubs(expense))
    col = {k: b.col for k, b in layout.boxes.items()}
    assert col["start"] == 0
    assert col["s2"] < col["s3"] < col["d1"] < col["s4"]
    assert col["s6"] > col["s2"]  # the "correct and resubmit" arrow is the one that goes back


def test_arrows_start_and_end_on_their_boxes_and_miss_the_others(expense):
    layout = lay_out(with_stubs(expense))
    boxes = layout.boxes

    def on_edge(pt, b):
        x, y = pt
        on_x = abs(x - b.left) < 1e-6 or abs(x - b.right) < 1e-6
        on_y = abs(y - b.bottom) < 1e-6 or abs(y - b.top) < 1e-6
        return (on_x and b.bottom - 1e-6 <= y <= b.top + 1e-6) or (on_y and b.left - 1e-6 <= x <= b.right + 1e-6)

    for r in layout.routes:
        assert on_edge(r.points[0], boxes[r.from_id]), (r.from_id, r.to_id)
        assert on_edge(r.points[-1], boxes[r.to_id]), (r.from_id, r.to_id)
        for a, b in zip(r.points, r.points[1:]):
            assert abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9, "arrows bend at right angles"
            for other in boxes.values():
                if other.id in (r.from_id, r.to_id):
                    continue
                x1, x2 = sorted((a[0], b[0]))
                y1, y2 = sorted((a[1], b[1]))
                through = x2 > other.left + 1e-6 and x1 < other.right - 1e-6 and y2 > other.bottom + 1e-6 and y1 < other.top - 1e-6
                assert not through, f"{r.from_id}->{r.to_id} cuts through {other.id}"


def test_no_lanes_means_one_row(hello):
    layout = lay_out(hello)
    assert layout.bands == []
    assert len({round(b.cy, 6) for b in layout.boxes.values()}) == 1
    xs = sorted(b.cx for b in layout.boxes.values())
    assert all(abs((b - a) - COL) < 1e-9 for a, b in zip(xs, xs[1:]))
    assert COL > BOX_W
