"""A bot's own mascot (docs/specs/bots.md, 9): a black-and-white SVG kept on the bot, made safe before it is kept,
whoever drew it. Only shapes survive: a short list of elements and attributes, path data and transforms of numbers
and commands only, and the two colours of the Glyphh cats (white and ink); anything else (scripts, styles, links,
images, text, foreign objects, event handlers, entities, other colours) is dropped or refused. The platform shows it
as an image, never as markup, so even what got through could not run."""

import re
import xml.etree.ElementTree as ET

from glyphh_server.errors import Invalid

MAX_BYTES: int = 30_000
DEEPEST: int = 12  # groups inside groups, at most
NS: str = "{http://www.w3.org/2000/svg}"
SHAPES: frozenset[str] = frozenset({"g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon"})
NUMBER: re.Pattern[str] = re.compile(r"-?\d+(\.\d+)?")
PATH: re.Pattern[str] = re.compile(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,\s+-]{1,8000}")
TRANSFORM: re.Pattern[str] = re.compile(r"((translate|rotate|scale|matrix|skewX|skewY)\([0-9eE.,\s+-]*\)\s*)+")
VIEWBOX: re.Pattern[str] = re.compile(r"-?[\d.]+([\s,]+-?[\d.]+){3}")
COLOURS: dict[str, str] = {
    c: v
    for v, names in (("#ffffff", ("#ffffff", "#fff", "white")), ("#0b0a0f", ("#0b0a0f", "#000", "#000000", "black")))
    for c in names
} | {"none": "none"}
SIZES: frozenset[str] = frozenset(
    {"cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "stroke-width", "opacity"}
)
WORDS: dict[str, frozenset[str]] = {
    "stroke-linecap": frozenset({"butt", "round", "square"}),
    "stroke-linejoin": frozenset({"miter", "round", "bevel"}),
    "fill-rule": frozenset({"nonzero", "evenodd"}),
    "clip-rule": frozenset({"nonzero", "evenodd"}),
}


def _kept(name: str, value: str) -> str | None:
    """The attribute's value as kept, or None to drop it."""
    value = value.strip()
    if name in ("fill", "stroke"):
        return COLOURS.get(value.lower())
    if name in SIZES:
        return value if NUMBER.fullmatch(value) else None
    if name in WORDS:
        return value if value in WORDS[name] else None
    if name == "d":
        return value if PATH.fullmatch(value) else None
    if name == "points":
        return value if re.fullmatch(r"[0-9eE.,\s+-]{1,8000}", value) else None
    if name == "transform":
        return value if TRANSFORM.fullmatch(value) else None
    return None


def _shape(node: ET.Element, depth: int = 0) -> ET.Element | None:
    tag = node.tag[len(NS) :] if node.tag.startswith(NS) else node.tag
    if tag not in SHAPES or depth > DEEPEST:
        return None
    out = ET.Element(tag, {k: v for k, raw in node.attrib.items() if (v := _kept(k, raw)) is not None})
    out.extend(kid for child in node if (kid := _shape(child, depth + 1)) is not None)
    return out


def _parsed(text: str) -> ET.Element:
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text.strip())
    if "<!" in text or "<?" in text:  # no doctype, entity, comment or processing instruction
        raise Invalid("A mascot is plain SVG shapes: no doctype, entities or comments.", reason="mascot")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise Invalid(f"A mascot is SVG: {err}.", reason="mascot") from err
    if root.tag not in (f"{NS}svg", "svg"):
        raise Invalid("A mascot is one <svg> element.", reason="mascot")
    return root


def clean(text: str) -> str:
    """The mascot as kept: its shapes only, in black and white; empty for none."""
    if not text.strip():
        return ""
    if len(text.encode()) > MAX_BYTES:
        raise Invalid(f"A mascot is at most {MAX_BYTES // 1000} KB of SVG.", reason="mascot")
    root = _parsed(text)
    box = root.get("viewBox", "").strip()
    out = ET.Element("svg", {"xmlns": NS[1:-1], "viewBox": box if VIEWBOX.fullmatch(box) else "0 0 200 200"})
    out.extend(kid for child in root if (kid := _shape(child)) is not None)
    if not len(out):
        raise Invalid("The mascot has no shapes left once made safe.", reason="mascot")
    return ET.tostring(out, encoding="unicode")
