"""Writes the Visio file.

We never build a Visio file from nothing. We start from a file Visio itself
saved (seed/cff_seed.vsdx), keep its stock shapes and settings, and replace
only the drawing on the page. Every piece of XML below copies what Visio wrote
for the same thing in that file: a stock shape dropped on the page, an arrow
attached at both ends, a plain rectangle.

`verify` re-opens a written file and tests what can be tested without Visio.
It cannot tell whether Visio will ask to repair the file; only Visio can.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from cursus.layout import HEADER_W, MM, Box, Layout, Route, lay_out
from cursus.model import Process, Step, with_stubs

NS = "http://schemas.microsoft.com/office/visio/2012/main"
PAGE_HEAD = (
    "<?xml version='1.0' encoding='utf-8' ?>\n"
    f"<PageContents xmlns='{NS}' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'>"
)
REL_MASTER = "http://schemas.microsoft.com/visio/2010/relationships/master"

# Which stock shape draws which kind of step. The seed carries these three; a
# sub-process and a document are drawn as a Process box until the seed has them.
STOCK = {
    "start": "Start/End",
    "end": "Start/End",
    "task": "Process",
    "subprocess": "Process",
    "document": "Process",
    "decision": "Decision",
    "parallel": "Decision",
}
# The colours Visio gave each stock shape on the seed page (theme colours, stored per shape).
LOOK = {
    "Start/End": ("#d49f00", "#ffe5c2"),
    "Decision": ("#d49f00", "#ffe5c2"),
    "Process": ("#898989", "#dcdcdc"),
}
STRAIGHT_PAD = 0.1968503937007874  # Visio gives a dead-straight arrow a 5 mm tall box
DASHED = "2"


def num(x: float) -> str:
    return "0" if abs(x) < 1e-12 else f"{x:.15g}"


def attr(text: str) -> str:
    """Text made safe for a single-quoted XML attribute."""
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")


def body(text: str) -> str:
    return text.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------ the seed


def _seed_bytes() -> bytes:
    return resources.files("cursus").joinpath("seed/cff_seed.vsdx").read_bytes()


def seed_masters(parts: dict[str, bytes]) -> dict[str, tuple[int, str]]:
    """Stock shape name -> (its id in the file, the part that holds it)."""
    masters = parts["visio/masters/masters.xml"].decode("utf-8")
    rels = parts["visio/masters/_rels/masters.xml.rels"].decode("utf-8")
    target = dict(re.findall(r'Relationship Id="(rId\d+)"[^>]*?Target="([^"]+)"', rels))
    target.update({k: v for v, k in re.findall(r'Target="([^"]+)"[^>]*?Id="(rId\d+)"', rels)})
    out: dict[str, tuple[int, str]] = {}
    for m in re.finditer(r"<Master ID='(\d+)' NameU='([^']+)'.*?<Rel r:id='(rId\d+)'/>", masters, re.S):
        out[m.group(2)] = (int(m.group(1)), target[m.group(3)])
    return out


# ------------------------------------------------------------------ shapes


def _step_shape(sheet: int, step: Step, box: Box, master_id: int) -> str:
    line, fill = LOOK[STOCK[step.kind]]
    cells = (
        f"<Cell N='PinX' V='{num(box.cx)}'/><Cell N='PinY' V='{num(box.cy)}'/><Cell N='LayerMember' V='0'/>"
        f"<Cell N='LineWeight' V='0.01736111111111111' U='PT' F='Inh'/><Cell N='LineColor' V='{line}' F='Inh'/>"
        f"<Cell N='FillBkgnd' V='{fill}' F='Inh'/>"
    )
    if step.assumed:
        cells += f"<Cell N='LinePattern' V='{DASHED}'/>"
    source = ""
    if step.quote.strip() or step.assumed:
        said = step.quote if step.quote.strip() else "Not stated in the text"
        source = (
            "<Section N='Property'><Row N='SourceText'>"
            f"<Cell N='Value' V='{attr(said)}' U='STR'/><Cell N='Prompt' V=''/><Cell N='Label' V='Source text'/>"
            "<Cell N='Format' V=''/><Cell N='SortKey' V=''/><Cell N='Type' V='0'/><Cell N='Invisible' V='0'/>"
            "<Cell N='Verify' V='0'/><Cell N='DataLinked' V='0' F='No Formula'/><Cell N='LangID' V='en-US'/>"
            "<Cell N='Calendar' V='0'/></Row></Section>"
        )
    return f"<Shape ID='{sheet}' Type='Shape' Master='{master_id}'>{cells}{source}<Text>{body(step.text)}\n</Text></Shape>"


_RECT = (
    "<Section N='Geometry' IX='0'><Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
    "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
    "<Row T='RelMoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
    "<Row T='RelLineTo' IX='2'><Cell N='X' V='1'/><Cell N='Y' V='0'/></Row>"
    "<Row T='RelLineTo' IX='3'><Cell N='X' V='1'/><Cell N='Y' V='1'/></Row>"
    "<Row T='RelLineTo' IX='4'><Cell N='X' V='0'/><Cell N='Y' V='1'/></Row>"
    "<Row T='RelLineTo' IX='5'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row></Section>"
)


def _plain(sheet: int, cx: float, cy: float, w: float, h: float, *, line: bool, fill: Optional[str], text: str = "", upright: bool = True, size_pt: float = 9, bold: bool = False) -> str:
    """A plain rectangle or caption, kept out of the way of arrows (ObjType 4: arrows do not route around it)."""
    cells = (
        f"<Cell N='PinX' V='{num(cx)}'/><Cell N='PinY' V='{num(cy)}'/><Cell N='Width' V='{num(w)}'/><Cell N='Height' V='{num(h)}'/>"
        f"<Cell N='LocPinX' V='{num(w / 2)}' F='Width*0.5'/><Cell N='LocPinY' V='{num(h / 2)}' F='Height*0.5'/>"
        "<Cell N='Angle' V='0'/><Cell N='FlipX' V='0'/><Cell N='FlipY' V='0'/><Cell N='ResizeMode' V='0'/>"
        "<Cell N='ObjType' V='4'/>"
    )
    if not upright:  # text turned to read bottom to top, for a lane name
        cells += (
            f"<Cell N='TxtPinX' V='{num(w / 2)}' F='Width*0.5'/><Cell N='TxtPinY' V='{num(h / 2)}' F='Height*0.5'/>"
            f"<Cell N='TxtWidth' V='{num(h)}' F='Height*1'/><Cell N='TxtHeight' V='{num(w)}' F='Width*1'/>"
            f"<Cell N='TxtLocPinX' V='{num(h / 2)}' F='TxtWidth*0.5'/><Cell N='TxtLocPinY' V='{num(w / 2)}' F='TxtHeight*0.5'/>"
            "<Cell N='TxtAngle' V='1.570796326794897'/>"
        )
    cells += "<Cell N='LineColor' V='#7f7f7f' F='THEMEGUARD(RGB(127,127,127))'/>"
    cells += f"<Cell N='LinePattern' V='{1 if line else 0}' F='THEMEGUARD({1 if line else 0})'/>"
    if fill:
        r, g, b = (int(fill[i : i + 2], 16) for i in (1, 3, 5))
        cells += f"<Cell N='FillForegnd' V='{fill}' F='THEMEGUARD(RGB({r},{g},{b}))'/><Cell N='FillPattern' V='1' F='THEMEGUARD(1)'/>"
    else:
        cells += "<Cell N='FillPattern' V='0' F='THEMEGUARD(0)'/>"
    cells += (
        "<Cell N='ShdwPattern' V='0' F='THEMEGUARD(0)'/><Cell N='LineGradientEnabled' V='0' F='THEMEGUARD(FALSE)'/>"
        "<Cell N='FillGradientEnabled' V='0' F='THEMEGUARD(FALSE)'/>"
    )
    char = (
        f"<Section N='Character'><Row IX='0'><Cell N='Color' V='#404040'/><Cell N='Style' V='{1 if bold else 0}'/>"
        f"<Cell N='Size' V='{num(size_pt / 72)}' U='PT'/></Row></Section>"
    )
    words = f"<Text>{body(text)}\n</Text>" if text else ""
    return f"<Shape ID='{sheet}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>{cells}{char}{_RECT}{words}</Shape>"


def _arrow(sheet: int, route: Route, from_sheet: int, to_sheet: int, master_id: int) -> str:
    """An arrow attached at both ends, written the way Visio writes one it has just routed."""
    (bx, by), (ex, ey) = route.points[0], route.points[-1]
    w, h = ex - bx, ey - by
    flat, upright = abs(h) < 1e-9, abs(w) < 1e-9
    box_w = STRAIGHT_PAD if upright else w
    box_h = STRAIGHT_PAD if flat else h
    width_f = "GUARD(0.19685039370079DL)" if upright else "GUARD(EndX-BeginX)"
    height_f = "GUARD(0.19685039370079DL)" if flat else "GUARD(EndY-BeginY)"

    def local(pt: tuple[float, float]) -> tuple[float, float]:
        return (pt[0] - (bx + ex) / 2 + box_w / 2, pt[1] - (by + ey) / 2 + box_h / 2)

    tx, ty = local(route.label_at)
    begin_f = "_WALKGLUE(BegTrigger,EndTrigger,WalkPreference)"
    end_f = "_WALKGLUE(EndTrigger,BegTrigger,WalkPreference)"
    cells = (
        f"<Cell N='PinX' V='{num((bx + ex) / 2)}' F='Inh'/><Cell N='PinY' V='{num((by + ey) / 2)}' F='Inh'/>"
        f"<Cell N='Width' V='{num(box_w)}' F='{width_f}'/><Cell N='Height' V='{num(box_h)}' F='{height_f}'/>"
        f"<Cell N='LocPinX' V='{num(box_w / 2)}' F='Inh'/><Cell N='LocPinY' V='{num(box_h / 2)}' F='Inh'/>"
        f"<Cell N='BeginX' V='{num(bx)}' F='{begin_f}'/><Cell N='BeginY' V='{num(by)}' F='{begin_f}'/>"
        f"<Cell N='EndX' V='{num(ex)}' F='{end_f}'/><Cell N='EndY' V='{num(ey)}' F='{end_f}'/>"
        "<Cell N='LayerMember' V='1'/>"
        f"<Cell N='BegTrigger' V='2' F='_XFTRIGGER(Sheet.{from_sheet}!EventXFMod)'/>"
        f"<Cell N='EndTrigger' V='2' F='_XFTRIGGER(Sheet.{to_sheet}!EventXFMod)'/>"
        "<Cell N='LineWeight' V='0.01388888888888889' U='PT' F='Inh'/><Cell N='LineColor' V='#7f7f7f' F='Inh'/>"
        "<Cell N='Rounding' V='0.0325' U='IN' F='Inh'/><Cell N='EndArrow' V='5' F='Inh'/><Cell N='BeginArrowSize' V='1' F='Inh'/>"
        f"<Cell N='TxtPinX' V='{num(tx)}' F='Inh'/><Cell N='TxtPinY' V='{num(ty)}' F='Inh'/>"
    )
    label = route.label.strip()
    if label:
        text_w = max(0.5555555555555556, 0.075 * len(label) + 0.11)
        cells += (
            f"<Cell N='TxtWidth' V='{num(text_w)}' F='Inh'/><Cell N='TxtHeight' V='0.2444939358181424' F='Inh'/>"
            f"<Cell N='TxtLocPinX' V='{num(text_w / 2)}' F='Inh'/><Cell N='TxtLocPinY' V='0.1222469679090712' F='Inh'/>"
        )
    control = (
        "<Section N='Control'><Row N='TextPosition'>"
        f"<Cell N='X' V='{num(tx)}'/><Cell N='Y' V='{num(ty)}'/><Cell N='XDyn' V='{num(tx)}' F='Inh'/><Cell N='YDyn' V='{num(ty)}' F='Inh'/>"
        + ("<Cell N='XCon' V='0' F='Inh'/>" if label else "")
        + "</Row></Section>"
    )
    rows = ""
    for i, pt in enumerate(route.points, 1):
        x, y = local(pt)
        rows += f"<Row T='{'MoveTo' if i == 1 else 'LineTo'}' IX='{i}'><Cell N='X' V='{num(x)}'/><Cell N='Y' V='{num(y)}'/></Row>"
    if len(route.points) == 2:  # the stock arrow has three points; a straight one drops the third
        rows += "<Row T='LineTo' IX='3' Del='1'/>"
    words = f"<Text>{body(label)}\n</Text>" if label else ""
    return f"<Shape ID='{sheet}' Type='Shape' Master='{master_id}'>{cells}{control}<Section N='Geometry' IX='0'>{rows}</Section>{words}</Shape>"


def _connects(arrow_sheet: int, from_sheet: int, to_sheet: int) -> str:
    return (
        f"<Connect FromSheet='{arrow_sheet}' FromCell='BeginX' FromPart='9' ToSheet='{from_sheet}' ToCell='PinX' ToPart='3'/>"
        f"<Connect FromSheet='{arrow_sheet}' FromCell='EndX' FromPart='12' ToSheet='{to_sheet}' ToCell='PinX' ToPart='3'/>"
    )


# ------------------------------------------------------------------ the page


def page_xml(p: Process, layout: Layout, masters: dict[str, tuple[int, str]]) -> str:
    shapes: list[str] = []
    sheet = 0

    def next_sheet() -> int:
        nonlocal sheet
        sheet += 1
        return sheet

    for band in layout.bands:  # first in the file means furthest back on the page
        shapes.append(_plain(next_sheet(), band.x + band.w / 2, band.y + band.h / 2, band.w, band.h, line=True, fill=None))
        shapes.append(_plain(next_sheet(), band.x + HEADER_W / 2, band.y + band.h / 2, HEADER_W, band.h, line=True, fill="#f2f2f2", text=band.name, upright=False, bold=True))
    if layout.title.strip():
        tx, ty = layout.title_at
        shapes.append(_plain(next_sheet(), tx, ty, min(layout.page_w - 20 * MM, 200 * MM), 8 * MM, line=False, fill=None, text=layout.title, size_pt=14, bold=True))

    sheet_of: dict[str, int] = {}
    for step in p.steps:
        sheet_of[step.id] = next_sheet()
        shapes.append(_step_shape(sheet_of[step.id], step, layout.boxes[step.id], masters[STOCK[step.kind]][0]))

    connects = ""
    arrow_master = masters["Dynamic connector"][0]
    for route in layout.routes:
        a, b = sheet_of[route.from_id], sheet_of[route.to_id]
        s = next_sheet()
        shapes.append(_arrow(s, route, a, b, arrow_master))
        connects += _connects(s, a, b)

    tail = f"<Connects>{connects}</Connects>" if connects else ""
    return f"{PAGE_HEAD}<Shapes>{''.join(shapes)}</Shapes>{tail}</PageContents>"


def _page_rels(masters: dict[str, tuple[int, str]]) -> str:
    names = sorted(set(STOCK.values()) | {"Dynamic connector"})
    rels = "".join(f'<Relationship Id="rId{i}" Type="{REL_MASTER}" Target="../masters/{masters[n][1]}"/>' for i, n in enumerate(names, 1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'
    )


def _set_cell(xml: str, name: str, value: float) -> str:
    out, n = re.subn(rf"(<Cell N='{name}' V=')[^']*(')", rf"\g<1>{num(value)}\g<2>", xml, count=1)
    if not n:
        raise ValueError(f"the seed page has no {name} cell")
    return out


def _set_view(xml: str, cx: float, cy: float) -> str:
    xml = re.sub(r"ViewCenterX='[^']*'", f"ViewCenterX='{num(cx)}'", xml)
    return re.sub(r"ViewCenterY='[^']*'", f"ViewCenterY='{num(cy)}'", xml)


def _core(xml: str, title: str, when: datetime) -> str:
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{body(title)}</dc:title>", xml, flags=re.S)
    xml = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator>cursus</dc:creator>", xml, flags=re.S)
    xml = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy>cursus</cp:lastModifiedBy>", xml, flags=re.S)
    xml = re.sub(r"<cp:keywords>.*?</cp:keywords>", "<cp:keywords></cp:keywords>", xml, flags=re.S)
    xml = re.sub(r"<cp:lastPrinted>.*?</cp:lastPrinted>", "", xml, flags=re.S)
    return re.sub(r"(<dcterms:(?:created|modified)[^>]*>).*?(</dcterms:)", rf"\g<1>{stamp}\g<2>", xml, flags=re.S)


RECALC = '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="7" name="RecalcDocument"><vt:bool>true</vt:bool></property>'


def write_vsdx(p: Process, path: Path | str, *, recalc: bool = True, when: Optional[datetime] = None) -> Path:
    """Draw the process and save it as a Visio file.

    `recalc` asks Visio to work every formula out again when it opens the file
    (Microsoft's documented switch for files edited outside Visio). With it, a
    box grows to fit long text. Without it, Visio shows exactly what we wrote.
    """
    p = with_stubs(p)
    layout = lay_out(p)
    with zipfile.ZipFile(io.BytesIO(_seed_bytes())) as z:
        parts = {name: z.read(name) for name in z.namelist()}
    masters = seed_masters(parts)
    for name in set(STOCK.values()) | {"Dynamic connector"}:
        if name not in masters:
            raise ValueError(f"the seed file has no '{name}' stock shape")

    def text(name: str) -> str:
        return parts[name].decode("utf-8")

    drop = {n for n in parts if n.startswith("visio/media/") or n == "docProps/thumbnail.emf"}
    for n in drop:
        del parts[n]
    parts["_rels/.rels"] = re.sub(r'<Relationship [^>]*thumbnail[^>]*/>', "", text("_rels/.rels")).encode("utf-8")
    parts["visio/pages/page1.xml"] = page_xml(p, layout, masters).encode("utf-8")
    parts["visio/pages/_rels/page1.xml.rels"] = _page_rels(masters).encode("utf-8")
    pages = _set_cell(_set_cell(text("visio/pages/pages.xml"), "PageWidth", layout.page_w), "PageHeight", layout.page_h)
    parts["visio/pages/pages.xml"] = _set_view(pages, layout.page_w / 2, layout.page_h / 2).encode("utf-8")
    parts["visio/windows.xml"] = _set_view(text("visio/windows.xml"), layout.page_w / 2, layout.page_h / 2).encode("utf-8")
    parts["docProps/core.xml"] = _core(text("docProps/core.xml"), p.title, when or datetime.now(timezone.utc)).encode("utf-8")
    if recalc:
        parts["docProps/custom.xml"] = text("docProps/custom.xml").replace("</Properties>", RECALC + "</Properties>").encode("utf-8")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = "[Content_Types].xml"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for name in [first] + [n for n in parts if n != first]:
            out.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), parts[name], zipfile.ZIP_DEFLATED)
    return path


# ------------------------------------------------------------------ checking a written file


def verify(path: Path | str) -> list[str]:
    """Problems found in a written file. An empty list means it holds together; it does not mean Visio is happy."""
    problems: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        parts = {n: z.read(n) for n in names}

    for name, data in parts.items():
        if name.endswith((".xml", ".rels")):
            try:
                ElementTree.fromstring(data)
            except ElementTree.ParseError as e:
                problems.append(f"{name}: not well-formed XML ({e})")
    if problems:
        return problems

    types = parts["[Content_Types].xml"].decode("utf-8")
    defaults = set(re.findall(r'<Default Extension="([^"]+)"', types))
    overrides = set(re.findall(r'<Override PartName="/([^"]+)"', types))
    for o in overrides - names:
        problems.append(f"content types list a part that is not in the file: {o}")
    for n in names - overrides - {"[Content_Types].xml"}:
        if n.rsplit(".", 1)[-1] not in defaults:
            problems.append(f"part has no content type: {n}")

    for name in [n for n in names if n.endswith(".rels")]:
        folder = name.rsplit("_rels/", 1)[0]
        for target in re.findall(r'Target="([^"]+)"', parts[name].decode("utf-8")):
            full = folder + target
            while "/../" in full:
                full = re.sub(r"[^/]+/\.\./", "", full, count=1)
            if full not in names:
                problems.append(f"{name}: points at a missing part {target}")

    master_ids = {int(i) for i in re.findall(r"<Master ID='(\d+)'", parts["visio/masters/masters.xml"].decode("utf-8"))}
    page = parts["visio/pages/page1.xml"].decode("utf-8")
    sheets = [int(i) for i in re.findall(r"<Shape ID='(\d+)'", page)]
    if len(sheets) != len(set(sheets)):
        problems.append("two shapes share an id")
    known = set(sheets)
    for m in re.findall(r"<Shape ID='\d+'[^>]*? Master='(\d+)'", page):
        if int(m) not in master_ids:
            problems.append(f"a shape uses stock shape {m}, which the file does not hold")
    for ref in re.findall(r"Sheet\.(\d+)!", page):
        if int(ref) not in known:
            problems.append(f"a formula refers to shape {ref}, which is not on the page")
    ends: dict[int, set[str]] = {}
    for frm, cell, to in re.findall(r"<Connect FromSheet='(\d+)' FromCell='(\w+)' FromPart='\d+' ToSheet='(\d+)'", page):
        if int(frm) not in known or int(to) not in known:
            problems.append(f"an attachment names a shape that is not on the page ({frm} -> {to})")
        ends.setdefault(int(frm), set()).add(cell)
    arrows = [int(i) for i in re.findall(r"<Shape ID='(\d+)'[^>]*>(?=<Cell N='PinX' V='[^']*' F='Inh'/>)", page)]
    for a in arrows:
        if ends.get(a) != {"BeginX", "EndX"}:
            problems.append(f"arrow {a} is not attached at both ends")
    return problems
