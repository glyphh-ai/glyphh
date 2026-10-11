"""One shell for every page, with headers that keep it from being framed, scripted or leaking its URL."""

from html import escape

from starlette.responses import HTMLResponse

STYLE: str = """
:root{color-scheme:dark;--bg:#0b0b0e;--card:#15151a;--line:#2a2a31;--text:#f3f3f5;--muted:#a3a3ad;--accent:#a96bff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:var(--bg);
color:var(--text);font:16px/1.5 system-ui,-apple-system,sans-serif}
main{width:100%;max-width:400px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:32px;
display:grid;gap:16px;text-align:center}
.mark{font:700 20px ui-monospace,monospace;letter-spacing:-.02em}
h1{margin:0;font-size:22px}p{margin:0;color:var(--muted)}
.btn{display:flex;align-items:center;justify-content:center;min-height:46px;border-radius:10px;
border:1px solid var(--line);
background:#1d1d23;color:var(--text);font:600 15px system-ui;text-decoration:none;cursor:pointer;width:100%}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}form{display:grid;gap:10px;margin:0}
code{font:12px ui-monospace,monospace;color:var(--muted)}
"""

HEADERS: dict[str, str] = {
    "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data: https:; "
    "form-action 'self' http: https:; frame-ancestors 'none'; base-uri 'none'",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}


def page(title: str, body: str, status: int = 200) -> HTMLResponse:
    """`body` is trusted markup built by the views; every value inside it is escaped there."""
    html = (
        f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport "
        f"content='width=device-width,initial-scale=1'><title>{escape(title)} · Glyphh</title>"
        f"<style>{STYLE}</style></head><body><main><div class=mark>glyphh</div>{body}</main></body></html>"
    )
    return HTMLResponse(html, status_code=status, headers=HEADERS)
