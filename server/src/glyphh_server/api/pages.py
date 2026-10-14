"""The few pages a browser sees: plain HTML, no styling (design comes later). Every value is escaped."""

from html import escape

from starlette.responses import HTMLResponse


def page(title: str, *paragraphs: str, raw: str = "", status: int = 200) -> HTMLResponse:
    """A page with a heading, escaped paragraphs, then `raw` markup the caller built from escaped values."""
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title></head><body><h1>{escape(title)}</h1>{body}{raw}</body></html>"
    )
    return HTMLResponse(html, status_code=status)


def link(href: str, text: str) -> str:
    return f'<p><a href="{escape(href)}">{escape(text)}</a></p>'
