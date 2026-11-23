"""What a run brought back that the person can open, read out of its steps' data when the run is shown (nothing
more is kept): `links`, the pages its steps made or touched (a pull request, a Slack message, a doc, an app), and
`apps`, the MCP App UI resources its steps' tool results carry (MCP Apps: an embedded `ui://` resource with its
page, or a result naming one by `_meta.ui.resourceUri`), which the platform shows inline in a sandboxed frame. The
same on Glyphh cloud and for a run on a rrotor: a step's data comes back whole either way."""

import urllib.parse
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, Field

from glyphh_server.ops.bots.files import RunFile

MIME: str = "text/html;profile=mcp-app"
URL_KEYS: tuple[str, ...] = ("html_url", "permalink", "webViewLink", "web_url", "url", "link")
TITLE_KEYS: tuple[str, ...] = ("title", "name", "subject", "text")
LINKS_MAX: int = 6
APPS_MAX: int = 4
LIST_MAX: int = 3  # a longer list is what a step read (a search's hits), not what the run made
DEPTH: int = 6
HTML_MAX: int = 400_000
TITLE_MAX: int = 120
KINDS: tuple[tuple[str, str, str], ...] = (
    ("github.com", "/pull/", "Pull request"),
    ("github.com", "/issues/", "Issue"),
    ("github.com", "", "GitHub"),
    ("slack.com", "", "Slack"),
    ("docs.google.com", "", "Doc"),
    ("drive.google.com", "", "Doc"),
    ("notion.so", "", "Notion"),
    ("linear.app", "", "Linear"),
    ("glyphh.app", "/apps/", "App"),
)


class RunLink(BaseModel):
    url: str
    title: str
    kind: str = Field(description="Pull request, Issue, GitHub, Slack, Doc, Notion, Linear or App")


class RunApp(BaseModel):
    step: str = Field(description="The step whose tool result carries it")
    uri: str = Field(description="The UI resource's address, ui://...")
    title: str
    html: str | None = Field(description="Its page, when the result embeds it; else read it by its address")
    input: Any = Field(None, description="What the tool was given, when the result says")
    result: Any = Field(None, description="The tool's result, which the page renders")


class RunStep(BaseModel):
    tool: str = Field(description="The tool's key (never shown to the person)")
    title: str = Field(description="What it did, in plain words: Send Email, Decided urgency for 4 items")
    app: str = Field(description="The app's name, when it is an app's tool")
    ok: bool = Field(description="False when it failed or was refused")


class Shown(BaseModel):
    """What a run says of itself and brought back (a RunView's)."""

    summary: str = Field("", description="A plain sentence for a run with no words of its own; else empty")
    hint: str = Field("", description="Always empty: a bot answers what it is told (kept for older clients)")
    steps: list[RunStep] = Field(default_factory=list, description="What it used during the turn, in order")
    links: list[RunLink] = Field(default_factory=list, description="Pages its steps made or touched")
    apps: list[RunApp] = Field(default_factory=list, description="MCP App UI resources its tool results carry")
    files: list[RunFile] = Field(
        default_factory=list,
        description="On a rrotor: the files of its folders it read and changed, by name (never what is in them)",
    )


def _dicts(value: Any, depth: int = 0) -> Iterator[dict[str, Any]]:
    """Every object in a step's data, outermost first; long lists (what a step read) and deep nests left alone."""
    if depth > DEPTH:
        return
    if isinstance(value, dict):
        yield value
        for inner in value.values():
            yield from _dicts(inner, depth + 1)
    elif isinstance(value, list) and len(value) <= LIST_MAX:
        for inner in value:
            yield from _dicts(inner, depth + 1)


def _steps(run: Any) -> Iterator[tuple[str, Any]]:
    data = run.data if isinstance(run.data, dict) else {}
    return ((k, v) for k, v in data.items() if k != "input" and not k.startswith("_"))


def steps(run: Any) -> list[RunStep]:
    """What the run used, as its desk noted it (ops/bots/agent/desk.py)."""
    data = run.data if isinstance(run.data, dict) else {}
    return [RunStep(**s) for s in data.get("_steps") or []]


def kind_of(url: str) -> str | None:
    """What a page is, by where it is; None for a page of no kind we name (it gets no card)."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return None
    for domain, path, kind in KINDS:
        if (host == domain or host.endswith("." + domain)) and path in parsed.path:
            return kind
    return None


def _link(found: dict[str, Any]) -> RunLink | None:
    url = next((found[k] for k in URL_KEYS if isinstance(found.get(k), str)), None)
    kind = kind_of(url) if url else None
    if url is None or kind is None:
        return None
    title = next((found[k] for k in TITLE_KEYS if isinstance(found.get(k), str) and found[k].strip()), kind)
    return RunLink(url=url, title=" ".join(title.split())[:TITLE_MAX], kind=kind)


def links(run: Any) -> list[RunLink]:
    """The pages the run's steps made or touched, each once, LINKS_MAX at most."""
    out: dict[str, RunLink] = {}
    for _, data in _steps(run):
        for found in _dicts(data):
            link = _link(found)
            if link is not None and len(out) < LINKS_MAX:
                out.setdefault(link.url, link)
    return list(out.values())


def _embedded(found: dict[str, Any]) -> dict[str, Any] | None:
    """An MCP tool result's embedded UI resource: {type: resource, resource: {uri: ui://..., mimeType, text}}."""
    blocks = found.get("content") if isinstance(found.get("content"), list) else []
    for block in blocks:
        inner = block.get("resource") if isinstance(block, dict) and block.get("type") == "resource" else None
        if isinstance(inner, dict) and str(inner.get("uri", "")).startswith("ui://") and inner.get("mimeType") == MIME:
            return inner
    return None


def _named(found: dict[str, Any]) -> str | None:
    """The UI resource a tool result names: `_meta.ui.resourceUri`."""
    meta = found.get("_meta") if isinstance(found.get("_meta"), dict) else {}
    ui = meta.get("ui") if isinstance(meta.get("ui"), dict) else {}
    uri = ui.get("resourceUri")
    return uri if isinstance(uri, str) and uri.startswith("ui://") else None


def _app(step: str, found: dict[str, Any]) -> RunApp | None:
    embedded = _embedded(found)
    uri = str(embedded["uri"]) if embedded else _named(found)
    if uri is None:
        return None
    text = embedded.get("text") if embedded else None
    html = text if isinstance(text, str) and len(text) <= HTML_MAX else None
    result = found.get("structuredContent", {k: v for k, v in found.items() if k not in ("_meta", "content")})
    title = str((embedded or {}).get("title") or found.get("title") or uri.removeprefix("ui://").split("/")[-2:][0])
    return RunApp(step=step, uri=uri, title=title[:TITLE_MAX], html=html, input=found.get("input"), result=result)


def apps(run: Any) -> list[RunApp]:
    """The MCP App UI resources the run's tool results carry, in step order, APPS_MAX at most."""
    out: list[RunApp] = []
    for step, data in _steps(run):
        for found in _dicts(data):
            app = _app(step, found)
            if app is not None and len(out) < APPS_MAX:
                out.append(app)
    return out
