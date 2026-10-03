import re
import zipfile
from pathlib import Path

import pytest

from cursus.model import Flow, Process, Step
from cursus.preview import read_page, to_svg
from cursus.visio import verify, write_vsdx


@pytest.fixture
def written(expense, tmp_path):
    return write_vsdx(expense, tmp_path / "flow.vsdx")


def page(path):
    with zipfile.ZipFile(path) as z:
        return z.read("visio/pages/page1.xml").decode("utf-8")


def test_file_holds_together(written, hello, tmp_path):
    assert verify(written) == []
    assert verify(write_vsdx(hello, tmp_path / "hello.vsdx", recalc=False)) == []


def test_every_step_is_a_stock_shape_and_every_arrow_is_attached_twice(written, expense):
    w, h, shapes = read_page(written)
    stock = [s for s in shapes if s.master and s.master != "Dynamic connector"]
    arrows = [s for s in shapes if s.master == "Dynamic connector"]
    assert len(stock) == len(expense.steps) + 1  # plus the "Not stated" end
    assert len(arrows) == len(expense.flows) + 1
    xml = page(written)
    assert len(re.findall(r"<Connect ", xml)) == 2 * len(arrows)
    assert xml.count("_WALKGLUE(BegTrigger,EndTrigger,WalkPreference)") == 2 * len(arrows)


def test_arrows_as_stored_touch_the_boxes_they_join(written):
    """Reads the file back: an arrow's stored path must begin and end on the edge of the two shapes it is attached to."""
    w, h, shapes = read_page(written)
    by_sheet = {s.sheet: s for s in shapes}
    xml = page(written)
    joined: dict[int, dict[str, int]] = {}
    for frm, cell, to in re.findall(r"<Connect FromSheet='(\d+)' FromCell='(\w+)' FromPart='\d+' ToSheet='(\d+)'", xml):
        joined.setdefault(int(frm), {})[cell] = int(to)

    def on_edge(pt, s):
        left, bottom = s.pin[0] - s.loc[0], s.pin[1] - s.loc[1]
        right, top = left + s.size[0], bottom + s.size[1]
        x, y = pt
        on_x = min(abs(x - left), abs(x - right)) < 1e-6 and bottom - 1e-6 <= y <= top + 1e-6
        on_y = min(abs(y - bottom), abs(y - top)) < 1e-6 and left - 1e-6 <= x <= right + 1e-6
        return on_x or on_y

    assert joined
    for sheet, ends in joined.items():
        arrow = by_sheet[sheet]
        assert on_edge(arrow.points[0], by_sheet[ends["BeginX"]]), sheet
        assert on_edge(arrow.points[-1], by_sheet[ends["EndX"]]), sheet
        assert 0 <= arrow.points[0][0] <= w and 0 <= arrow.points[0][1] <= h


def test_source_sentence_travels_inside_the_file(written):
    xml = page(written)
    assert "Label' V='Source text'" in xml
    assert "The line manager checks the claim against the travel policy." in xml
    assert "Not stated in the text" in xml  # the dashed stub says so too
    assert "<Cell N='LinePattern' V='2'/>" in xml


def test_text_that_would_break_xml_is_escaped(tmp_path):
    p = Process(
        title="R&D <sign-off>",
        steps=[
            Step(id="a", kind="start", text="Start"),
            Step(id="b", kind="task", text="Check P&L > 5 'units'", quote="it's \"big\" & <odd>"),
            Step(id="c", kind="end", text="End"),
        ],
        flows=[Flow(from_id="a", to_id="b"), Flow(from_id="b", to_id="c", label="a < b")],
    )
    path = write_vsdx(p, tmp_path / "odd.vsdx")
    assert verify(path) == []
    texts = [s.text for s in read_page(path)[2]]
    assert "Check P&L > 5 'units'" in texts and "a < b" in texts


def test_recalc_switch_and_no_leftovers_from_the_seed(expense, tmp_path):
    def parts(path):
        with zipfile.ZipFile(path) as z:
            return {n: z.read(n).decode("utf-8", "replace") for n in z.namelist()}

    on = parts(write_vsdx(expense, tmp_path / "on.vsdx"))
    off = parts(write_vsdx(expense, tmp_path / "off.vsdx", recalc=False))
    assert 'name="RecalcDocument"' in on["docProps/custom.xml"]
    assert "RecalcDocument" not in off["docProps/custom.xml"]
    assert not any(n.startswith("visio/media/") or n.endswith("thumbnail.emf") for n in on)
    assert "thumbnail" not in on["_rels/.rels"]
    assert "<dc:creator>cursus</dc:creator>" in on["docProps/core.xml"]
    assert "CFF Container" not in on["visio/pages/page1.xml"]


def test_starting_from_your_own_visio_file(expense, tmp_path):
    from importlib import resources

    own = tmp_path / "mine.vsdx"
    own.write_bytes(resources.files("cursus").joinpath("seed/cff_seed.vsdx").read_bytes())
    path = write_vsdx(expense, tmp_path / "out.vsdx", seed=own)
    assert verify(path) == []
    xml = page(path)
    assert "#d49f00" not in xml and "EndArrow" not in xml  # the bundled seed's colours are not forced onto another seed

    no_shapes = Path(__file__).resolve().parent / "visio_saved" / "s02_glue_pin.vsdx"
    with pytest.raises(ValueError, match="no 'Decision' stock shape"):
        write_vsdx(expense, tmp_path / "bad.vsdx", seed=no_shapes)


def test_page_grows_to_fit(written):
    w, h, shapes = read_page(written)
    for s in shapes:
        if s.master and s.master != "Dynamic connector":
            assert 0 < s.pin[0] < w and 0 < s.pin[1] < h


def test_verify_catches_a_broken_file(written, tmp_path):
    broken = tmp_path / "broken.vsdx"
    with zipfile.ZipFile(written) as z, zipfile.ZipFile(broken, "w") as out:
        for n in z.namelist():
            data = z.read(n)
            if n == "visio/pages/page1.xml":
                data = re.sub(rb"ToSheet='\d+'", b"ToSheet='9999'", data, count=1)
            out.writestr(n, data)
    assert any("not on the page" in p for p in verify(broken))


def test_preview_draws_every_label(written, expense):
    svg = to_svg(written)
    for s in expense.steps:
        for word in s.text.split():
            assert word in svg
    assert svg.count("<polyline") == len(expense.flows) + 1
