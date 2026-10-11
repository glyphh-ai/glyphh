from html import escape
from urllib.parse import urlencode

from starlette.responses import HTMLResponse

from glyphh_server.pages.render import page

LABELS: dict[str, str] = {"google": "Continue with Google", "github": "Continue with GitHub"}


def sign_in(request_token: str, providers: list[str]) -> HTMLResponse:
    query = escape(urlencode({"request": request_token}))
    buttons = "".join(f"<a class=btn href='/auth/{p}/start?{query}'>{LABELS[p]}</a>" for p in providers)
    return page("Sign in", f"<h1>Sign in to Glyphh</h1><p>Use the account you work with.</p>{buttons}")


def allow(host: str, email: str, consent: str) -> HTMLResponse:
    token = escape(consent)
    return page(
        "Allow",
        (
            f"<h1>{escape(host)} wants to use your Glyphh</h1>"
            f"<p>Signed in as {escape(email)}. It will act as you, and you can disconnect it at any time.</p>"
            f"<form method=post action=/auth/allow><input type=hidden name=consent value='{token}'>"
            f"<button class='btn primary' name=decision value=allow>Allow</button>"
            f"<button class=btn name=decision value=deny>Deny</button></form>"
        ),
    )


def refused(code: str, message: str, trace_id: str, status: int) -> HTMLResponse:
    return page(
        "Something stopped",
        (
            f"<h1>That didn't work</h1><p>{escape(message)}</p>"
            f"<p><code>{escape(code)} · trace {escape(trace_id)}</code></p>"
        ),
        status=status,
    )


def join(org: str, email: str, role: str, invite: str, providers: list[str]) -> HTMLResponse:
    query = escape(urlencode({"invite": invite}))
    buttons = "".join(f"<a class=btn href='/auth/{p}/start?{query}'>{LABELS[p]}</a>" for p in providers)
    who = "an org admin" if role == "org_admin" else "a member"
    return page(
        "Join",
        (f"<h1>Join {escape(org)} on Glyphh</h1><p>You're invited as {who}. Sign in as {escape(email)}.</p>{buttons}"),
    )


def joined(org: str) -> HTMLResponse:
    return page(
        "Joined", (f"<h1>You've joined {escape(org)}</h1><p>Open Glyphh in Claude, ChatGPT or Codex to start.</p>")
    )
