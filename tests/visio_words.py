"""The "words" a Visio file is written in: which cells it sets, with which kind of formula, in which rows.

Used to compare what we write against what Visio itself wrote. Numbers and
shape ids are blanked out, so `Sheet.7!EventXFMod` and `Sheet.12!EventXFMod`
count as the same word.
"""
import re
import zipfile


def _shape(formula: str | None) -> str:
    if formula is None:
        return "-"
    formula = re.sub(r"Sheet\.\d+", "Sheet.N", formula)
    return re.sub(r"\d+(\.\d+)?", "N", formula)


def words_of_xml(xml: str) -> set[tuple]:
    out: set[tuple] = set()
    section = row_type = None
    for m in re.finditer(r"<(/?)(Shape|Section|Row|Cell|Connect|Text)\b([^>]*?)(/?)>", xml):
        closing, tag, attrs, _ = m.groups()
        a = dict(re.findall(r"(\w+)='([^']*)'", attrs))
        if closing:
            if tag == "Section":
                section = None
            if tag == "Row":
                row_type = None
            continue
        if tag == "Section":
            section = a.get("N")
            out.add(("section", section))
        elif tag == "Row":
            row_type = a.get("T") or ("named" if "N" in a else "indexed")
            out.add(("row", section, row_type, "deleted" if a.get("Del") else ""))
        elif tag == "Cell":
            where = section if section else "shape"
            out.add(("cell", where, a.get("N"), _shape(a.get("F"))))
        elif tag == "Connect":
            out.add(("connect", a.get("FromCell"), a.get("FromPart"), re.sub(r"\d+", "N", a.get("ToCell", "")), "glue-to-shape" if a.get("ToPart") == "3" else "glue-to-point"))
        elif tag == "Shape":
            out.add(("shape", a.get("Type"), "from stock shape" if "Master" in a or "MasterShape" in a else "drawn"))
    return out


def words_of_file(path, parts=("visio/pages/", "visio/masters/master")) -> set[tuple]:
    out: set[tuple] = set()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.startswith(parts) and name.endswith(".xml") and "_rels" not in name:
                out |= words_of_xml(z.read(name).decode("utf-8"))
    return out
