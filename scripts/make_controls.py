"""Writes controls/: files whose answer we already know, to test whatever is testing our files.

A checker that passes everything proves nothing. So next to our own files we
hand it one file Visio itself saved (it must pass) and files broken on
purpose (it should complain).
"""
import re
import zipfile
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "controls"
OURS = ROOT / "testpack" / "2-expense-claim.vsdx"


def rewrite(source: Path, target: Path, change) -> None:
    with zipfile.ZipFile(source) as z, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for name in z.namelist():
            out.writestr(name, change(name, z.read(name)))


def page(fn):
    return lambda name, data: fn(data.decode("utf-8")).encode("utf-8") if name == "visio/pages/page1.xml" else data


OUT.mkdir(exist_ok=True)
(OUT / "good-saved-by-visio.vsdx").write_bytes(resources.files("cursus").joinpath("seed/cff_seed.vsdx").read_bytes())
rewrite(OURS, OUT / "bad-cut-off-xml.vsdx", page(lambda xml: xml[: len(xml) // 2]))
rewrite(OURS, OUT / "bad-missing-stock-shape.vsdx", page(lambda xml: re.sub(r"Master='12'", "Master='999'", xml)))
rewrite(OURS, OUT / "bad-arrow-to-nowhere.vsdx", page(lambda xml: re.sub(r"ToSheet='\d+'", "ToSheet='9999'", xml)))
rewrite(OURS, OUT / "bad-no-page-part.vsdx", lambda name, data: b"" if name == "visio/pages/page1.xml" else data)
for path in sorted(OUT.iterdir()):
    print("wrote", path)
