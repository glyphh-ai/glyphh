"""A drawn mascot made safe: shapes and the two colours kept, everything else dropped or refused."""

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import svg

NS = 'xmlns="http://www.w3.org/2000/svg"'


def test_only_shapes_numbers_and_black_and_white_are_kept() -> None:
    given = (
        f'<?xml version="1.0"?><svg {NS} viewBox="0 0 100 100" onload="x()" width="9">'
        '<script>alert(1)</script><style>*{}</style><a href="javascript:x"><path d="M0 0"/></a>'
        '<g transform="translate(5 5) rotate(10)" opacity="0.5">'
        '<path d="M1 1 L2 2 Z" fill="red" stroke="BLACK" stroke-width="4" stroke-linecap="round" onclick="x()"/>'
        '<circle cx="5" cy="5" r="calc(1)" fill="url(#g)" stroke-linejoin="wobbly"/>'
        '<rect x="1" y="1" width="2" height="2" fill="#fff" style="fill:red" fill-rule="evenodd"/>'
        '<polygon points="1,1 2,2 3,1" fill="none"/><path d="M0 0 expression(x)"/>'
        '<use href="#x"/><image href="http://x"/><text>Hi</text>'
        '<g transform="url(x)"><polyline points="a"/></g></g></svg>'
    )
    assert svg.clean(given) == (
        f'<svg {NS} viewBox="0 0 100 100"><g transform="translate(5 5) rotate(10)" opacity="0.5">'
        '<path d="M1 1 L2 2 Z" stroke="#0b0a0f" stroke-width="4" stroke-linecap="round" />'
        '<circle cx="5" cy="5" /><rect x="1" y="1" width="2" height="2" fill="#ffffff" fill-rule="evenodd" />'
        '<polygon points="1,1 2,2 3,1" fill="none" /><path /><g><polyline /></g></g></svg>'
    )


def test_no_mascot_is_empty_and_a_bad_box_is_the_square() -> None:
    assert svg.clean("  ") == ""
    assert (
        svg.clean('<svg viewBox="0 0 x 1"><circle r="1"/></svg>')
        == f'<svg {NS} viewBox="0 0 200 200"><circle r="1" /></svg>'
    )


def test_groups_too_deep_are_dropped() -> None:
    deep = "<g>" * 20 + '<circle r="1"/>' + "</g>" * 20
    assert svg.clean(f"<svg>{deep}</svg>").count("<g") == svg.DEEPEST + 1


@pytest.mark.parametrize(
    ("given", "says"),
    [
        ("<svg>" + "<g/>" * 9000 + "</svg>", "at most 30 KB"),
        ('<!DOCTYPE svg [<!ENTITY a "b">]><svg>&a;</svg>', "no doctype"),
        ("<svg><!-- hi --><circle/></svg>", "no doctype"),
        ("<svg><circle>", "A mascot is SVG"),
        ("<html><circle/></html>", "one <svg> element"),
        ("<svg><text>Hi</text></svg>", "no shapes left"),
    ],
)
def test_what_is_not_a_mascot_is_refused(given: str, says: str) -> None:
    with pytest.raises(Invalid) as err:
        svg.clean(given)
    assert says in err.value.message and err.value.detail["reason"] == "mascot"
