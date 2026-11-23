"""A program's file (docs/specs/programs.md, 1): its FLOW read without running it, written back in place with every
other byte kept, checked for each problem at once, and its strings made of earlier results; a template's program
read and checked with its package."""

import json
from typing import Any

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import package_parts, packages
from glyphh_server.ops.programs import flow, store
from glyphh_server.ops.programs.walk import title_of

SOURCE: str = '''"""Mine."""

import json

FLOW = [
    {"id": "find", "kind": "tool", "tool": "gmail-find-email", "input": {"q": "{input}"}, "next": "sum"},
    {"id": "sum", "kind": "code", "function": "count", "next": None},
]  # the steps


def count(given):
    return len(json.dumps(given))
'''
STEPS: list[dict[str, Any]] = [
    {"id": "ask", "kind": "ask", "question": "Go on?", "options": ["Yes", "No"], "next": {"Yes": "go", "else": None}},
    {"id": "go", "kind": "bot", "task": "Do it: {ask}", "bot": "inbox-cat", "at": [10, 20.5], "next": None},
]


def test_a_file_is_read_without_running_it() -> None:
    steps, functions = flow.read(SOURCE)
    assert [s["id"] for s in steps] == ["find", "sum"] and functions == ["count"]
    assert flow.check(steps, functions) == []


@pytest.mark.parametrize(
    ("source", "said"),
    [
        ("FLOW = [", "program.py is not Python: line 1"),
        ("X = 1\n", "program.py has no FLOW"),
        ("FLOW = [step() for step in []]\n", "FLOW must be written out"),
        ("FLOW = {'id': 'a'}\n", "FLOW must be a list of steps"),
        ("FLOW = [1]\n", "FLOW must be a list of steps"),
    ],
)
def test_a_file_that_is_not_a_program_says_why(source: str, said: str) -> None:
    with pytest.raises(flow.Bad, match=said):
        flow.read(source)
    assert store.parsed(source)[2][0].startswith(said)


def test_steps_written_back_keep_every_other_byte() -> None:
    written = flow.write(SOURCE, STEPS)
    assert written.startswith('"""Mine."""\n\nimport json\n\nFLOW = [\n    {"id": "ask"')
    assert written.endswith("]  # the steps\n\n\ndef count(given):\n    return len(json.dumps(given))\n")
    assert flow.read(written) == (STEPS, ["count"])
    assert flow.write(written, STEPS) == written  # the round trip is exact
    appended = flow.write('"""None yet."""\n', STEPS)
    assert appended.startswith('"""None yet."""\n\nFLOW = [') and flow.read(appended)[0] == STEPS
    assert flow.literal([{"next": None, "id": "a", "kind": "ask", "options": (True, 1)}]) == (
        'FLOW = [\n    {"id": "a", "kind": "ask", "options": [True, 1], "next": None},\n]'
    )


def test_every_problem_is_said_at_once() -> None:
    bad = [
        {"id": "Bad Id", "kind": "tool", "colour": "red"},
        {"id": "b", "kind": "nope"},
        {"id": "c", "kind": "code", "function": "missing", "next": "nowhere"},
        {"id": "d", "kind": "ask", "question": "?", "options": "yes", "at": [1]},
        {"id": "d", "kind": "bot", "task": "t", "next": {"x": "c"}},
    ]
    said = flow.check(bad, [])
    assert said == [
        "Bad Id: colour is not a key a step has",
        "Bad Id: its id must be a short lowercase name",
        "Bad Id: a tool step needs its tool",
        "b: its kind must be one of tool, bot, ask, branch, code",
        "c: program.py has no function missing",
        "d: its options must be a list",
        "d: at must be [x, y]",
        "d: two steps have this id",
        "c: there is no step nowhere",
        "d: only an ask or a branch goes on by its result",
    ]
    assert flow.check([{"id": "a", "kind": "ask", "question": "?"}] * 101, []) == ["A program has at most 100 steps."]


def test_a_loop_needs_the_person_in_it() -> None:
    loop = [
        {"id": "a", "kind": "branch", "on": "{a}", "next": {"x": "b", "else": None}},
        {"id": "b", "kind": "bot", "task": "t", "next": "a"},
    ]
    assert flow.check(loop, []) == ["a -> b -> a: this goes round forever with no one asked"]
    asked = [{**loop[0], "next": "c"}, loop[1], {"id": "c", "kind": "ask", "question": "?", "next": "a"}]
    assert flow.check(asked, []) == []


def test_strings_are_made_of_earlier_results() -> None:
    outputs = {"input": "hi", "find": {"n": 2, "who": {"name": "Ada"}}, "none": None}
    assert flow.render("{find}", outputs) == outputs["find"]  # one name alone: the result as it is
    assert flow.render({"a": ["Say {input} to {find.who.name}", "{find.n.x}", 3]}, outputs) == {
        "a": ["Say hi to Ada", None, 3]
    }
    assert flow.render("{find.n} and {none} and {find.who}", outputs) == '2 and  and {"name": "Ada"}'
    ask = {"next": {"Yes": "go", '{"a": 1}': "obj", "else": "other"}}
    assert flow.after(ask, " Yes ") == "go" and flow.after(ask, {"a": 1}) == "obj" and flow.after(ask, "No") == "other"
    assert flow.after({"next": "x"}, "anything") == "x" and flow.after({}, None) is None


def test_store_reads_and_writes_the_file() -> None:
    assert store.slugify("  PR digest!! 2 ") == "pr-digest-2"
    with pytest.raises(Invalid, match="needs a letter"):
        store.slugify("123")
    with pytest.raises(Invalid, match="not both"):
        store.source_of("x", [])
    assert store.source_of(None, None, "kept") == "kept" and store.source_of("given", None) == "given"
    assert flow.read(store.source_of(None, STEPS, "not python (")) == (STEPS, [])  # a broken file starts again
    assert store.can_run_on(flow.read(SOURCE)[0]) == ["rrotor"] and store.can_run_on(STEPS) == ["cloud", "rrotor"]


def test_a_step_is_named_in_plain_words() -> None:
    assert title_of({"title": "Mine", "kind": "tool"}) == "Mine"
    assert title_of({"kind": "tool", "tool": "gmail-find_email"}) == "gmail find email"
    assert title_of({"kind": "branch"}) == "Choose the way on" and title_of({"kind": "x", "id": "z"}) == "z"


def test_a_template_with_a_program_is_checked_with_it() -> None:
    problems: list[str] = []
    assert package_parts.program({}, problems) == [] and problems == []
    assert package_parts.program({"program.py": "FLOW = ["}, problems) == []
    assert problems == ["program.py is not Python: line 1: '[' was never closed."]
    problems.clear()
    steps = package_parts.program({"program.py": "FLOW = [{'id': 'a', 'kind': 'code', 'function': 'f'}]"}, problems)
    assert problems == ["program.py: a: program.py has no function f"] and package_parts.has_code(steps)
    digest = packages.library()["pr-review-digest"]
    assert digest.runs_on == ["cloud", "rrotor"] and "program.py" in digest.files
    files = {**digest.files, "program.py": SOURCE}  # a code step: the package runs on a rrotor only
    with pytest.raises(Invalid) as said:
        packages.check(files)
    assert said.value.detail["problems"] == [
        'runs_on must be ["rrotor"]: code and folders need a rrotor, anything else runs anywhere.'
    ]
    sidecar = json.loads(files["glyphh.json"])
    del sidecar["runs_on"]
    assert packages.check({**files, "glyphh.json": json.dumps(sidecar)}).runs_on == ["rrotor"]
