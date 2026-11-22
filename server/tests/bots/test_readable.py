"""A gate's item made readable (its fields and a label, never raw JSON), the runner's decisions read from its state
(a gate over one case as well as one over many items), and a tool's list answered as a list."""

import uuid
from pathlib import Path
from types import SimpleNamespace

from glyphh.bots.runner import RunStore

from glyphh_server.ops.bots import decided, props, readable


def test_fields_flatten_nested_values_and_lists_and_drop_the_shared_start() -> None:
    item = {"user": {"login": "ada"}, "labels": ["bug", "p1"], "draft": False, "files": [{"name": "a.py"}], "n": None}
    assert readable.fields(item) == {
        "user.login": "ada", "labels": "bug, p1", "draft": "no", "files.1.name": "a.py",
    }  # fmt: skip
    assert readable.fields({"p": {"s": {"title": "Fix it", "id": 7}}}) == {"title": "Fix it", "id": "7"}
    assert readable.fields({"p": {"s": {"title": "Fix it"}}}) == {"title": "Fix it"}
    assert readable.fields({"p": {"a": {"x": 1}, "b": {"y": 2}}}) == {"a.x": "1", "b.y": "2"}  # only `p` is shared
    assert readable.fields(["a", "b"]) == {"value": "a, b"} and readable.fields("plain") == {"value": "plain"}
    assert readable.fields([{"x": 1}]) == {"x": "1"} and readable.fields({"t": "  "}) == {}
    many = readable.fields({f"k{i}": i for i in range(60)})
    assert len(many) == readable.FIELDS_MAX


def test_a_label_is_a_title_drawn_from_the_fields_never_json() -> None:
    assert readable.label("Lunch on Friday?", {}) == "Lunch on Friday?"
    shown = {"user.login": "ada", "title": "Fix   the\nlogin bug"}
    assert readable.label('{"id": 1, "title": "x"}', shown) == "Fix the login bug"
    assert readable.label('{"id": 1, "title": "cut...', shown) == "Fix the login bug"  # the runner's cut JSON
    assert readable.label("{not json", {"a": "1"}) == "{not json"
    assert readable.label("", {"id": "9", "repo": "glyphh", "author": "ada"}) == "repo glyphh · author ada"
    assert readable.label(None, {"id": "9"}) == "An item with no fields"
    assert readable.label("", {}) == "An item with no fields"
    long = readable.label("x" * 300, {})
    assert len(long) == readable.LABEL_MAX and long.endswith("…")
    assert readable.body("L", {"a": "b"}, "gate", None) == "L\na b\ngate"


def test_the_runners_decisions_are_read_from_its_state_one_case_or_many_items(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    store.save("r1", "done", 0, {"worth": {"answer": [{"id": "m1", "subject": "Hi"}], "decisions": []}}, {}, "", [])
    store.keep_decision(run="r1", gate="worth", step="worth", n=1, key="m1", label="Hi", kind="each",
                        case={"m": {"s": {"subject": "Hi"}}}, outcome="answer", by="person", recorded=True)  # fmt: skip
    store.keep_decision(run="r1", gate="worth", step="worth", n=2, key="m2", label="", kind="each",
                        case={"m": {"s": {"subject": "Gone"}}}, outcome="skip", by="ada", p=0.9)  # fmt: skip
    store.keep_decision(run="r1", gate="send", step="send", n=0, key="", label="", kind="gate",
                        case={"c": {"s": {"title": "Weekly"}}}, outcome="yes", by="default", wrong="no")  # fmt: skip
    bot = SimpleNamespace(org_id=uuid.uuid4(), id=uuid.uuid4(), spec={"loop": [{"id": "worth", "key": "id"}]})
    rows = {(r["gate"], r["n"]): r for r in decided.rows(bot, (tmp_path / "runs.sqlite").read_bytes())}
    assert rows[("worth", 1)]["fields"] == {"id": "m1", "subject": "Hi"} and rows[("worth", 1)]["who"] == "you"
    assert rows[("worth", 2)]["label"] == "Gone" and rows[("worth", 2)]["who"] == "ada"  # its item: from its case
    sent = rows[("send", 0)]
    assert sent["label"] == "Weekly" and sent["who"] == "default" and sent["corrected"] == "no"
    assert decided.read(b"not a database") == ([], {})  # a state a runtime sent that is not the runner's


def test_a_tools_list_is_its_list_even_cut_to_fit() -> None:
    cut = {"ret": {"messages": [{"id": "m1"}], "truncated": True, "note": "cut"}, "exports": {}}
    assert props.returned(cut) == {"ret": [{"id": "m1"}], "ret_note": "cut", "exports": {}}
    whole = {"ret": [{"id": "m1"}]}
    assert props.returned(whole) is whole and props.returned(None) is None
    assert props.returned({"ret": {"messages": []}}) == {"ret": {"messages": []}}
