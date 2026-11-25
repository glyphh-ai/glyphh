"""What a Word file itself says (filefacts.py): the application that wrote it, its author and who saved it
last, when it was made and last changed, its revision number, its fonts, the tracked changes left in it (insertions
and deletions never accepted) and the text a reader would not see: marked hidden (w:vanish), white, or smaller
than a reader can read. A file that is not a Word document raises ValueError."""

import io
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

W: str = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CP: str = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"
DC: str = "{http://purl.org/dc/elements/1.1/}"
TERMS: str = "{http://purl.org/dc/terms/}"
APP: str = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"
XML_MAX: int = 10_000_000
TINY_HALF_POINTS: int = 8  # w:sz is in half points: under 4 points a reader does not see words


def _xml(z: zipfile.ZipFile, path: str) -> ET.Element | None:
    if path not in z.namelist() or z.getinfo(path).file_size > XML_MAX:
        return None
    return ET.fromstring(z.read(path))


def _said(root: ET.Element | None, tag: str) -> str:
    found = root.find(tag) if root is not None else None
    return (found.text or "").strip() if found is not None else ""


def _run(run: ET.Element) -> tuple[int, str, str]:
    """A run of text: how many characters, what hides them (hidden, white, tiny or nothing), and its font."""
    props = run.find(f"{W}rPr")
    n = sum(len(t.text or "") for t in run.iter(f"{W}t"))
    if props is None:
        return n, "", ""
    font = (props.find(f"{W}rFonts").get(f"{W}ascii") or "") if props.find(f"{W}rFonts") is not None else ""
    colour, size = props.find(f"{W}color"), props.find(f"{W}sz")
    if props.find(f"{W}vanish") is not None:
        return n, "hidden", font
    if colour is not None and (colour.get(f"{W}val") or "").upper() == "FFFFFF":
        return n, "white", font
    if size is not None and (size.get(f"{W}val") or "").isdigit() and int(size.get(f"{W}val") or 0) < TINY_HALF_POINTS:
        return n, "tiny", font
    return n, "", font


def facts(data: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body, core, app = _xml(z, "word/document.xml"), _xml(z, "docProps/core.xml"), _xml(z, "docProps/app.xml")
    if body is None:
        raise ValueError("it has no document in it")
    out: dict[str, Any] = {"hidden": 0, "white": 0, "tiny": 0}
    fonts: set[str] = set()
    for run in body.iter(f"{W}r"):
        n, how, font = _run(run)
        fonts.add(font)
        if how:
            out[how] += n
    revision = _said(core, f"{CP}revision")
    tracked = len(list(body.iter(f"{W}ins"))) + len(list(body.iter(f"{W}del")))
    return out | {
        "producer": _said(app, f"{APP}Application"), "creator": "",
        "author": f"{_said(core, f'{DC}creator')} {_said(core, f'{CP}lastModifiedBy')}".strip(),
        "created": _said(core, f"{TERMS}created")[:19], "modified": _said(core, f"{TERMS}modified")[:19],
        "saves": int(revision) if revision.isdigit() else 1, "fonts": sorted(f for f in fonts if f), "tracked": tracked,
    }  # fmt: skip
