"""Draws a written Visio file back out as an SVG picture.

This reads the file, not the plan it was written from, so it shows what is
really stored: where each box sits and the path each arrow takes. It is how we
look at a file on a machine without Visio. It is a rough picture, not Visio's
rendering: stock shapes are drawn as plain outlines.
"""
from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from cursus.visio import seed_masters

PX = 96  # pixels per inch


@dataclass
class Seen:
    sheet: int
    master: str  # stock shape name, or "" for a plain shape
    pin: tuple[float, float]
    size: tuple[float, float]
    loc: tuple[float, float]
    text: str
    points: list[tuple[float, float]] = field(default_factory=list)  # page coordinates, arrows only
    text_at: tuple[float, float] | None = None
    dashed: bool = False
    filled: bool = False
    line: bool = True
    turned: bool = False


def _cell(xml: str, name: str) -> float | None:
    m = re.search(rf"<Cell N='{name}' V='([^']*)'", xml)
    return float(m.group(1)) if m else None


def read_page(path: Path | str) -> tuple[float, float, list[Seen]]:
    """Page width, page height and every shape on page 1."""
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    masters = seed_masters(parts)
    by_id = {mid: (name, parts["visio/masters/" + target].decode("utf-8")) for name, (mid, target) in masters.items()}
    pages = parts["visio/pages/pages.xml"].decode("utf-8")
    page = parts["visio/pages/page1.xml"].decode("utf-8")
    out: list[Seen] = []
    for m in re.finditer(r"<Shape ID='(\d+)'([^>]*)>(.*?)</Shape>", page, re.S):
        sheet, attrs, inner = int(m.group(1)), m.group(2), m.group(3)
        mm = re.search(r"Master='(\d+)'", attrs)
        name, master_xml = by_id[int(mm.group(1))] if mm else ("", "")
        geometry = inner[inner.find("<Section N='Geometry'") :] if "<Section N='Geometry'" in inner else ""
        head = inner[: inner.find("<Section")] if "<Section" in inner else inner

        def val(cell: str) -> float:
            own = _cell(head, cell)
            return own if own is not None else (_cell(master_xml, cell) or 0.0)

        text = re.search(r"<Text>(.*?)</Text>", inner, re.S)
        seen = Seen(
            sheet=sheet,
            master=name,
            pin=(val("PinX"), val("PinY")),
            size=(val("Width"), val("Height")),
            loc=(val("LocPinX"), val("LocPinY")),
            text=html.unescape(re.sub(r"<[^>]+>", "", text.group(1))).strip() if text else "",
            dashed=_cell(head, "LinePattern") == 2,
            filled=_cell(head, "FillPattern") == 1,
            line=_cell(head, "LinePattern") != 0,
            turned=_cell(head, "TxtAngle") is not None and abs(_cell(head, "TxtAngle") or 0) > 0.1,
        )
        if name == "Dynamic connector":
            ox, oy = seen.pin[0] - seen.loc[0], seen.pin[1] - seen.loc[1]
            for row in re.finditer(r"<Row T='(?:MoveTo|LineTo)' IX='\d+'><Cell N='X' V='([^']*)'/><Cell N='Y' V='([^']*)'/></Row>", geometry):
                seen.points.append((ox + float(row.group(1)), oy + float(row.group(2))))
            seen.text_at = (ox + val("TxtPinX"), oy + val("TxtPinY"))
        out.append(seen)
    return _cell(pages, "PageWidth") or 0.0, _cell(pages, "PageHeight") or 0.0, out


def _wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def to_svg(path: Path | str) -> str:
    page_w, page_h, shapes = read_page(path)

    def xy(pt: tuple[float, float]) -> tuple[float, float]:
        return (pt[0] * PX, (page_h - pt[1]) * PX)

    def words(lines: list[str], cx: float, cy: float, size: int, extra: str = "") -> str:
        top = cy - (len(lines) - 1) * size * 0.6
        return "".join(
            f'<text x="{cx:.1f}" y="{top + i * size * 1.2:.1f}" font-size="{size}" text-anchor="middle" dominant-baseline="middle"{extra}>{html.escape(l)}</text>'
            for i, l in enumerate(lines)
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w * PX:.0f}" height="{page_h * PX:.0f}" viewBox="0 0 {page_w * PX:.0f} {page_h * PX:.0f}" font-family="Helvetica, Arial, sans-serif">',
        '<defs><marker id="tip" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 z" fill="#555"/></marker></defs>',
        f'<rect width="100%" height="100%" fill="white"/>',
    ]
    for s in shapes:
        if s.master == "Dynamic connector":
            continue
        w, h = s.size[0] * PX, s.size[1] * PX
        x, y = xy((s.pin[0] - s.loc[0], s.pin[1] - s.loc[1] + s.size[1]))
        cx, cy = x + w / 2, y + h / 2
        dash = ' stroke-dasharray="6 4"' if s.dashed else ""
        if s.master == "Decision":
            parts.append(f'<polygon points="{x:.1f},{cy:.1f} {cx:.1f},{y:.1f} {x + w:.1f},{cy:.1f} {cx:.1f},{y + h:.1f}" fill="#ffe5c2" stroke="#d49f00"{dash}/>')
        elif s.master == "Start/End":
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="#ffe5c2" stroke="#d49f00"{dash}/>')
        elif s.master == "Process":
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#dcdcdc" stroke="#898989"{dash}/>')
        else:
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{"#f2f2f2" if s.filled else "none"}" stroke="{"#7f7f7f" if s.line else "none"}"/>')
        if s.text:
            if s.turned:
                parts.append(f'<g transform="rotate(-90 {cx:.1f} {cy:.1f})">{words([s.text], cx, cy, 12, " font-weight=\"bold\"")}</g>')
            elif s.master:
                parts.append(words(_wrap(s.text, 15), cx, cy, 10))
            else:
                parts.append(words([s.text], cx, cy, 16, ' font-weight="bold"'))
    for s in shapes:
        if s.master != "Dynamic connector" or len(s.points) < 2:
            continue
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in map(xy, s.points))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#555" stroke-width="1.3" marker-end="url(#tip)"/>')
        if s.text and s.text_at:
            tx, ty = xy(s.text_at)
            box_w = 7 * len(s.text) + 6
            parts.append(f'<rect x="{tx - box_w / 2:.1f}" y="{ty - 8:.1f}" width="{box_w}" height="16" fill="white"/>')
            parts.append(words([s.text], tx, ty, 10))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
