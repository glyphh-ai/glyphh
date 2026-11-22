"""A bot's own mascot, drawn by Claude from the person's words (docs/specs/bots.md, 9): a new black-and-white Glyphh
cat (or creature) as SVG shapes, in the style of Spike, the cats' own mark: an ink body with a thick white outline,
white eyes and details, nothing else. What Claude draws is made safe (ops/bots/svg.py) before it is shown or kept."""

import re
from typing import Any

from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import maker, svg

DRAW: str = """\
You draw mascots for Glyphh bots: flat, bold, black-and-white characters in the style of Spike, the Glyphh cat.
Spike is a sitting alien cat seen from the front: one solid ink (#0b0a0f) silhouette with pointed ears and a tail,
a thick white (#ffffff) outline around it (stroke-width 10 to 16, round joins), one large white eye ring with an ink
pupil and a white glint, and a few white details. It sits on a dark tile, so the outline is what shows its shape.

Draw the mascot the person describes as a new character in that style (a cat unless they ask for another creature).
Rules: one <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"> filled edge to edge; only g, path,
circle, ellipse, rect, line, polyline and polygon; only the attributes d, cx, cy, r, rx, ry, x, y, width, height,
x1, y1, x2, y2, points, transform, fill, stroke, stroke-width, stroke-linecap, stroke-linejoin, fill-rule, opacity;
only the colours #ffffff, #0b0a0f and none; no text, no style, no gradients, no background rectangle. Keep it under
12 KB. Answer with the SVG alone."""


async def draw(bots: Any, who: Principal, prompt: str) -> str:
    """The mascot as kept: Claude's SVG, made safe."""
    said = await maker.ask(bots, who.org_id, DRAW, f"The mascot: {prompt}")
    found = re.search(r"<svg\b.*</svg>", said, re.S)
    if found is None:
        raise Unavailable("Claude did not draw a mascot: try describing it another way.", reason="mascot")
    return svg.clean(found.group(0))
