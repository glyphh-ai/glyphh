"""A program's steps (docs/specs/programs.md, 1): `FLOW`, the literal list in its `program.py`, read without running
the file; written back in place, every other byte of the file kept; checked; and walked one step at a time (what a
string makes of earlier results, and which step is next)."""

import ast
import json
import re
from typing import Any

KINDS: tuple[str, ...] = ("tool", "bot", "ask", "branch", "code")
KEYS: tuple[str, ...] = (
    "id", "kind", "title", "bot", "tool", "input", "task", "question", "options", "on", "function", "next", "at",
)  # fmt: skip
NEEDS: dict[str, tuple[str, ...]] = {
    "tool": ("tool",), "bot": ("task",), "ask": ("question",), "branch": ("on",), "code": ("function",),
}  # fmt: skip
ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
NAMED = re.compile(r"\{([a-z][a-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*)\}")
ELSE: str = "else"
STEPS_MAX: int = 100
EMPTY: str = '"""A program."""\n\nFLOW = []\n'


class Bad(ValueError):
    """The file's FLOW is not a literal list of steps: why, in plain words."""


def _assign(tree: ast.Module) -> ast.Assign | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["FLOW"]:
            return node
    return None


def read(source: str) -> tuple[list[dict[str, Any]], list[str]]:
    """The file's steps and the names of its top-level functions (what a code step may call)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        raise Bad(f"program.py is not Python: line {err.lineno}: {err.msg}.") from None
    found = _assign(tree)
    if found is None:
        raise Bad("program.py has no FLOW = [...]: the list of its steps.")
    try:
        flow = ast.literal_eval(found.value)
    except ValueError:
        raise Bad("FLOW must be written out as a list of steps, nothing computed.") from None
    if not isinstance(flow, list) or not all(isinstance(s, dict) for s in flow):
        raise Bad("FLOW must be a list of steps, each a {...}.")
    functions = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    return flow, functions


def _value(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(str(k))}: {_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    return repr(value) if value is None or isinstance(value, bool) else json.dumps(value, ensure_ascii=False)


def literal(flow: list[dict[str, Any]]) -> str:
    """`FLOW = [...]`, one step a line, its keys in their order."""
    lines = ["FLOW = ["]
    for step in flow:
        ordered = {k: step[k] for k in KEYS if k in step}
        lines.append(f"    {_value(ordered)},")
    return "\n".join([*lines, "]"])


def write(source: str, flow: list[dict[str, Any]]) -> str:
    """The file with its FLOW replaced by these steps; every other byte as it was (a file without one gets it at the
    end)."""
    tree = ast.parse(source)
    found = _assign(tree)
    if found is None:
        return source.rstrip("\n") + "\n\n" + literal(flow) + "\n"
    lines = source.splitlines(keepends=True)
    start, end = found.lineno - 1, (found.end_lineno or found.lineno)
    tail = lines[end - 1][found.end_col_offset or 0 :] if lines else ""
    head = lines[start][: found.col_offset]
    return "".join(lines[:start]) + head + literal(flow) + tail + "".join(lines[end:])


def _step(step: dict[str, Any], functions: list[str]) -> list[str]:
    sid, kind = step.get("id"), step.get("kind")
    name = sid if isinstance(sid, str) else "a step"
    out = [f"{name}: {k} is not a key a step has" for k in step if k not in KEYS]
    if not isinstance(sid, str) or not ID.fullmatch(sid):
        out.append(f"{name}: its id must be a short lowercase name")
    if kind not in KINDS:
        return [*out, f"{name}: its kind must be one of {', '.join(KINDS)}"]
    out += [f"{name}: a {kind} step needs its {k}" for k in NEEDS[kind] if not step.get(k)]
    if kind == "code" and step.get("function") and step["function"] not in functions:
        out.append(f"{name}: program.py has no function {step['function']}")
    if kind == "ask" and not isinstance(step.get("options", []), list):
        out.append(f"{name}: its options must be a list")
    at = step.get("at")
    if at is not None and not (isinstance(at, list) and len(at) == 2 and all(isinstance(n, int | float) for n in at)):
        out.append(f"{name}: at must be [x, y]")
    return out


def targets(step: dict[str, Any]) -> list[str | None]:
    """The steps a step may go on to (None: the end)."""
    nxt = step.get("next")
    return list(nxt.values()) if isinstance(nxt, dict) else [nxt]


def check(flow: list[dict[str, Any]], functions: list[str]) -> list[str]:
    """Each problem with the steps, in plain words; none for a program that can run."""
    if len(flow) > STEPS_MAX:
        return [f"A program has at most {STEPS_MAX} steps."]
    out = [p for step in flow for p in _step(step, functions)]
    ids = [s.get("id") for s in flow]
    out += [f"{i}: two steps have this id" for i in sorted({i for i in ids if ids.count(i) > 1 and isinstance(i, str)})]
    for step in flow:
        nxt = step.get("next")
        if isinstance(nxt, dict) and step.get("kind") not in ("ask", "branch"):
            out.append(f"{step.get('id')}: only an ask or a branch goes on by its result")
        out += [f"{step.get('id')}: there is no step {t}" for t in targets(step) if t is not None and t not in ids]
    return out or _cycles(flow)


def _cycles(flow: list[dict[str, Any]]) -> list[str]:
    """A loop the walk could follow forever without the person in it."""
    edges = {s["id"]: [t for t in targets(s) if t is not None] for s in flow if s["kind"] != "ask"}
    done: set[str] = set()

    def visit(sid: str, path: list[str]) -> list[str] | None:
        if sid in path:
            return [*path[path.index(sid) :], sid]
        if sid in done or sid not in edges:
            return None
        for t in edges[sid]:
            if loop := visit(t, [*path, sid]):
                return loop
        done.add(sid)
        return None

    for sid in edges:
        if loop := visit(sid, []):
            return [f"{' -> '.join(loop)}: this goes round forever with no one asked"]
    return []


def _of(path: str, outputs: dict[str, Any]) -> Any:
    head, *rest = path.split(".")
    value = outputs.get(head)
    for key in rest:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def render(value: Any, outputs: dict[str, Any]) -> Any:
    """A step's input with `{step}` and `{step.key}` made of earlier results (a string that is only one name takes
    that result as it is)."""
    if isinstance(value, dict):
        return {k: render(v, outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, outputs) for v in value]
    if not isinstance(value, str):
        return value
    whole = NAMED.fullmatch(value)
    if whole:
        return _of(whole.group(1), outputs)

    def text(m: re.Match[str]) -> str:
        got = _of(m.group(1), outputs)
        return got if isinstance(got, str) else "" if got is None else json.dumps(got, ensure_ascii=False)

    return NAMED.sub(text, value)


def after(step: dict[str, Any], result: Any) -> str | None:
    """The step that comes next, by this one's result."""
    nxt = step.get("next")
    if not isinstance(nxt, dict):
        return nxt
    key = result if isinstance(result, str) else json.dumps(result)
    return nxt.get(key.strip(), nxt.get(ELSE))
