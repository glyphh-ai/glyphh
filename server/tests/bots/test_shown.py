"""What a run brought back that the person can open: the pages its steps made or touched, and the MCP App UI
resources its tool results carry."""

from types import SimpleNamespace
from typing import Any

from glyphh_server.ops.bots import shown
from glyphh_server.ops.bots.shown import MIME

PR = "https://github.com/acme/app/pull/7"


def run(**data: Any) -> Any:
    return SimpleNamespace(data=data)


def test_a_page_is_named_by_where_it_is() -> None:
    assert shown.kind_of(PR) == "Pull request"
    assert shown.kind_of("https://github.com/acme/app/issues/3") == "Issue"
    assert shown.kind_of("https://github.com/acme/app") == "GitHub"
    assert shown.kind_of("https://acme.slack.com/archives/C1/p1") == "Slack"
    assert shown.kind_of("https://docs.google.com/document/d/1") == "Doc"
    assert shown.kind_of("https://www.notion.so/Weekly-1") == "Notion"
    assert shown.kind_of("https://a1b2c3.glyphh.app/apps/board") == "App"
    assert shown.kind_of("https://a1b2c3.glyphh.app/v1/programs") is None
    assert shown.kind_of("http://github.com/acme/app/pull/7") is None
    assert shown.kind_of("https://example.com/x") is None
    assert shown.kind_of("https://notgithub.com/x") is None


def test_links_are_the_pages_steps_made_not_the_lists_they_read() -> None:
    hits = [{"html_url": f"https://github.com/acme/app/pull/{n}", "title": f"PR {n}"} for n in range(9)]
    got = shown.links(
        run(
            input="https://github.com/typed/by/pull/1",
            _approved={"url": PR},
            prs={"ret": {"items": hits}},
            opened={"ret": {"html_url": PR, "title": "  Fix the\n login  "}},
            again={"ret": {"html_url": PR, "title": "the same page"}},
            slack={"ret": {"permalink": "https://acme.slack.com/archives/C1/p1", "ts": "1"}},
            other={"url": "https://example.com/nothing", "name": "no card"},
            none={"title": "no url"},
        )
    )
    assert [(g.kind, g.title, g.url) for g in got] == [
        ("Pull request", "Fix the login", PR),
        ("Slack", "Slack", "https://acme.slack.com/archives/C1/p1"),
    ]
    many = {f"s{n}": {"url": f"https://github.com/acme/app/pull/{n}"} for n in range(9)}
    assert len(shown.links(run(**many))) == shown.LINKS_MAX
    assert shown.links(SimpleNamespace(data=None)) == []
    deep: Any = {"url": PR}
    for _ in range(shown.DEPTH + 1):
        deep = {"in": deep}
    assert shown.links(run(step=deep)) == []


def test_an_embedded_ui_resource_comes_back_with_its_page() -> None:
    page = "<!doctype html><p>card</p>"
    result = {
        "content": [
            {"type": "text", "text": "Decided"},
            {"type": "resource", "resource": {"uri": "ui://acme/card/1", "mimeType": MIME, "text": page}},
        ],
        "structuredContent": {"outcome": "approve"},
        "input": {"case": 1},
    }
    (app,) = shown.apps(run(decide=result))
    assert (app.step, app.uri, app.title, app.html) == ("decide", "ui://acme/card/1", "card", page)
    assert (app.input, app.result) == ({"case": 1}, {"outcome": "approve"})
    big = {"content": [{"type": "resource", "resource": {"uri": "ui://x", "mimeType": MIME, "text": "x" * 400_001}}]}
    assert shown.apps(run(big=big))[0].html is None
    not_ui = {"content": ["text", {"type": "resource", "resource": {"uri": "file:///a", "mimeType": MIME}}]}
    wrong_mime = {"content": [{"type": "resource", "resource": {"uri": "ui://x/1", "mimeType": "text/html"}}]}
    assert shown.apps(run(a=not_ui, b=wrong_mime, c={"content": "words"})) == []


def test_a_result_naming_a_ui_resource_comes_back_without_a_page() -> None:
    result = {"_meta": {"ui": {"resourceUri": "ui://glyphh/decision/1"}}, "outcome": "approve", "title": "Refund"}
    (app,) = shown.apps(run(decide={"ret": result}))
    assert (app.uri, app.title, app.html, app.result) == (
        "ui://glyphh/decision/1",
        "Refund",
        None,
        {"outcome": "approve", "title": "Refund"},
    )
    bad = [{"_meta": "x"}, {"_meta": {"ui": 3}}, {"_meta": {"ui": {"resourceUri": "https://x"}}}]
    assert shown.apps(run(a=bad)) == []
    many = {f"s{n}": result for n in range(9)}
    assert len(shown.apps(run(**many))) == shown.APPS_MAX


def test_the_steps_a_run_used_are_what_its_desk_noted_in_order() -> None:
    noted = [
        {"tool": "gmail-find-email", "title": "Find Email", "app": "Gmail", "ok": True},
        {"tool": "decide", "title": "Decided worth for 2 items", "app": "Ada", "ok": True},
        {"tool": "gmail-send-email", "title": "Send Email", "app": "Gmail", "ok": False},
    ]
    got = shown.steps(run(_steps=noted, worth={"decisions": []}))
    assert [(s.tool, s.title, s.app, s.ok) for s in got] == [
        ("gmail-find-email", "Find Email", "Gmail", True),
        ("decide", "Decided worth for 2 items", "Ada", True),
        ("gmail-send-email", "Send Email", "Gmail", False),
    ]
    assert shown.steps(run()) == [] and shown.steps(run(_steps=None)) == []
    assert shown.steps(SimpleNamespace(data=None)) == []  # a run with nothing kept
    assert shown.links(run(_steps=[{"url": PR}])) == []  # what the desk noted is not what the run made
