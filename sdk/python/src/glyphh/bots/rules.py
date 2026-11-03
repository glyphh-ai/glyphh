"""Hard gates, as code a bot.json declares: paths into a run's data (`$id.path`), `requires` expressions (a tiny,
safe language: comparisons, and/or/not, len(), numbers, strings, `$id.path`; no eval), a JSON Schema subset for an
agent step's answer, `quiet_hours`, and the answers to a batch of per-item questions. Each is checked when a package
loads, so a malformed one is refused before it runs."""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: A step id and a path into its data: `$stories.items`, `$worth.read.0.title`.
REF = re.compile(r"\$(\w+(?:\.\w+)*)")


def resolve(path: str, data: Mapping[str, Any], default: Any = None) -> Any:
    """`id.path` (no `$`) in a run's data: dict keys and list indices; `default` where it leads nowhere."""
    found: Any = data
    for part in path.split("."):
        if isinstance(found, Mapping) and part in found:
            found = found[part]
        elif isinstance(found, (list, tuple)) and part.isdigit() and int(part) < len(found):
            found = found[int(part)]
        else:
            return default
    return found


def resolve_in(item: Any, path: Optional[str]) -> Any:
    """A path into one item (`title`, `story.url`); the item itself for no path."""
    if not path:
        return item
    return resolve(path, item if isinstance(item, Mapping) else {}, None)


# requires: a tiny expression language

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<num>-?\d+(?:\.\d+)?)
      | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
      | (?P<ref>\$\w+(?:\.\w+)*)
      | (?P<op>==|!=|<=|>=|<|>|\(|\)|,)
      | (?P<word>[A-Za-z_]\w*)
    )""",
    re.X,
)
_WORDS = {"and", "or", "not", "true", "false", "null", "len"}
_COMPARE = {"==", "!=", "<", "<=", ">", ">="}


class ExprError(ValueError):
    """A `requires` expression that does not parse."""


def _tokens(text: str) -> List[Tuple[str, str]]:
    out, at = [], 0
    text = text.rstrip()
    while at < len(text):
        m = _TOKEN.match(text, at)
        if not m or m.end() == at:
            raise ExprError(f"cannot read {text[at:at + 12]!r}")
        kind = m.lastgroup or ""
        value = m.group(kind)
        if kind == "word" and value not in _WORDS:
            raise ExprError(f"unknown word {value!r} (only and, or, not, true, false, null, len)")
        out.append((kind, value))
        at = m.end()
    return out


class _Parser:
    def __init__(self, text: str) -> None:
        self.toks, self.i = _tokens(text), 0

    def peek(self) -> Tuple[str, str]:
        return self.toks[self.i] if self.i < len(self.toks) else ("end", "")

    def take(self, value: Optional[str] = None) -> Tuple[str, str]:
        tok = self.peek()
        if tok[0] == "end" or (value is not None and tok[1] != value):
            raise ExprError(f"expected {value or 'more'}, found {tok[1] or 'the end'}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        if not self.toks:
            raise ExprError("it is empty")
        node = self.or_()
        if self.peek()[0] != "end":
            raise ExprError(f"unexpected {self.peek()[1]}")
        return node

    def or_(self) -> Any:
        node = self.and_()
        while self.peek() == ("word", "or"):
            self.take()
            node = ("or", node, self.and_())
        return node

    def and_(self) -> Any:
        node = self.not_()
        while self.peek() == ("word", "and"):
            self.take()
            node = ("and", node, self.not_())
        return node

    def not_(self) -> Any:
        if self.peek() == ("word", "not"):
            self.take()
            return ("not", self.not_())
        return self.compare()

    def compare(self) -> Any:
        node = self.atom()
        if self.peek()[0] == "op" and self.peek()[1] in _COMPARE:
            op = self.take()[1]
            node = ("cmp", op, node, self.atom())
        return node

    def atom(self) -> Any:
        kind, value = self.take()
        if kind == "num":
            return ("lit", float(value) if "." in value else int(value))
        if kind == "str":
            return ("lit", json.loads(value) if value[0] == '"' else value[1:-1].replace("\\'", "'"))
        if kind == "ref":
            return ("ref", value[1:])
        if kind == "word" and value in ("true", "false", "null"):
            return ("lit", {"true": True, "false": False, "null": None}[value])
        if kind == "word" and value == "len":
            self.take("(")
            inner = self.or_()
            self.take(")")
            return ("len", inner)
        if (kind, value) == ("op", "("):
            inner = self.or_()
            self.take(")")
            return inner
        raise ExprError(f"unexpected {value}")


def parse_expr(text: str) -> Any:
    """A `requires` expression, parsed; ExprError says why it does not parse."""
    if not isinstance(text, str):
        raise ExprError("it must be a string")
    return _Parser(text).parse()


def expr_refs(node: Any) -> List[str]:
    """The step ids an expression reads."""
    if node[0] == "ref":
        return [node[1].split(".")[0]]
    return [r for part in node[1:] if isinstance(part, tuple) for r in expr_refs(part)]


def evaluate(node: Any, data: Mapping[str, Any]) -> Any:
    """An expression's value over a run's data. Comparing what cannot be compared is false, never an error."""
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "ref":
        return resolve(node[1], data)
    if kind == "len":
        got = evaluate(node[1], data)
        try:
            return len(got)
        except TypeError:
            return 0
    if kind == "not":
        return not evaluate(node[1], data)
    if kind == "and":
        return bool(evaluate(node[1], data)) and bool(evaluate(node[2], data))
    if kind == "or":
        return bool(evaluate(node[1], data)) or bool(evaluate(node[2], data))
    op, a, b = node[1], evaluate(node[2], data), evaluate(node[3], data)
    try:
        return {"==": lambda: a == b, "!=": lambda: a != b, "<": lambda: a < b, "<=": lambda: a <= b,
                ">": lambda: a > b, ">=": lambda: a >= b}[op]()
    except TypeError:
        return False


def holds(text: str, data: Mapping[str, Any]) -> bool:
    return bool(evaluate(parse_expr(text), data))


# an agent's answer: JSON, against a JSON Schema subset

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties", "items", "enum", "const", "minimum",
               "maximum", "minLength", "maxLength", "minItems", "maxItems", "pattern", "anyOf", "description",
               "title", "$schema"}


def check_schema(schema: Any, path: str = "schema") -> List[str]:
    """Why a JSON Schema is outside the subset the runner checks; [] when it is right."""
    if not isinstance(schema, dict):
        return [f"{path} must be an object"]
    problems = [f"{path}: {k} is not a keyword the runner checks" for k in schema if k not in SCHEMA_KEYS]
    t = schema.get("type")
    for one in t if isinstance(t, list) else [t] if t is not None else []:
        if one not in _TYPES:
            problems.append(f"{path}: type {one} is not one of {', '.join(_TYPES)}")
    for name, sub in (schema.get("properties") or {}).items():
        problems += check_schema(sub, f"{path}.{name}")
    if isinstance(schema.get("items"), dict):
        problems += check_schema(schema["items"], f"{path}[]")
    if isinstance(schema.get("additionalProperties"), dict):
        problems += check_schema(schema["additionalProperties"], f"{path}.*")
    for i, sub in enumerate(schema.get("anyOf") or []):
        problems += check_schema(sub, f"{path}|{i}")
    return problems


def validate(value: Any, schema: Mapping[str, Any], path: str = "$") -> List[str]:
    """Where `value` does not fit `schema`, one line each; [] when it fits."""
    if "anyOf" in schema:
        if not any(not validate(value, s, path) for s in schema["anyOf"]):
            return [f"{path} fits none of anyOf"]
    t = schema.get("type")
    if t is not None:
        kinds = t if isinstance(t, list) else [t]
        if not any(_TYPES[k](value) for k in kinds):
            return [f"{path} is not {' or '.join(kinds)}"]
    out: List[str] = []
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path} is not one of {json.dumps(schema['enum'])}")
    if "const" in schema and value != schema["const"]:
        out.append(f"{path} is not {json.dumps(schema['const'])}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path} is under {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path} is over {schema['maximum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(f"{path} is shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{path} is longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path} does not match {schema['pattern']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(f"{path} has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path} has more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, v in enumerate(value):
                out += validate(v, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in value:
                out.append(f"{path}.{name} is missing")
        for name, v in value.items():
            if name in props:
                out += validate(v, props[name], f"{path}.{name}")
            elif schema.get("additionalProperties") is False:
                out.append(f"{path}.{name} is not allowed")
            elif isinstance(schema.get("additionalProperties"), dict):
                out += validate(v, schema["additionalProperties"], f"{path}.{name}")
    return out


def json_answer(text: str) -> Any:
    """An agent's answer read as JSON: as it is, inside a ``` fence, or the first {...} or [...] in it."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    for candidate in ([fenced.group(1)] if fenced else []) + [text]:
        try:
            return json.loads(candidate)
        except ValueError:
            pass
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = text.find(open_), text.rfind(close)
        if 0 <= a < b:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                pass
    raise ValueError("the answer is not JSON")


# quiet hours

QUIET = re.compile(r"([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)")


def quiet(span: str, now: dt.datetime) -> bool:
    """Whether `now` (local) is inside "HH:MM-HH:MM" (it may wrap midnight: "22:00-07:00")."""
    m = QUIET.fullmatch(span)
    if not m:
        raise ValueError(span)
    a, b = int(m.group(1)) * 60 + int(m.group(2)), int(m.group(3)) * 60 + int(m.group(4))
    t = now.hour * 60 + now.minute
    return a <= t < b if a <= b else t >= a or t < b


# the answers to a batch of per-item questions

def parse_answers(answer: Any, numbers: Sequence[int], options: Sequence[str]) -> Dict[int, str]:
    """The person's answers to a batch, by item number: a map ({"1": "read"}), JSON of one, `1=read 2=skip` (spaces
    or commas; a list of such), `rest=skip` (or `all=skip`) for the ones not named, or one bare outcome for a batch of
    one. Every item must be answered with one of the options."""
    pairs: List[Tuple[str, Any]] = []
    if isinstance(answer, Mapping):
        pairs = [(str(k), v) for k, v in answer.items()]
    else:
        parts = [answer] if isinstance(answer, str) else [str(a) for a in (answer or [])]
        text = " ".join(parts).strip()
        if text.startswith("{"):
            try:
                got = json.loads(text)
            except ValueError:
                raise ValueError("the answers are not JSON") from None
            return parse_answers(got, numbers, options)
        for word in re.split(r"[\s,;]+", text):
            if not word:
                continue
            k, sep, v = word.partition("=")
            if not sep:
                if len(numbers) == 1:
                    pairs.append((str(numbers[0]), word))
                    continue
                raise ValueError(f"{word}: answer each as N=outcome (1=read 2=skip, rest=skip)")
            pairs.append((k, v))
    allowed = {o.lower(): o for o in options}
    got: Dict[int, str] = {}
    rest: Optional[str] = None
    for k, v in pairs:
        o = allowed.get(str(v).strip().lower())
        if o is None:
            raise ValueError(f"{k}={v}: {v} is not one of {', '.join(options)}")
        key = k.strip().lower()
        if key in ("rest", "all", "*"):
            rest = o
        elif key.isdigit() and int(key) in numbers:
            got[int(key)] = o
        else:
            raise ValueError(f"{k} is not one of the items asked ({', '.join(str(n) for n in numbers)})")
    missing = [n for n in numbers if n not in got]
    if missing and rest is None:
        raise ValueError(f"answer every one: {', '.join(str(n) for n in missing)} not answered (or rest=<outcome>)")
    return {n: got.get(n, rest or "") for n in numbers}
