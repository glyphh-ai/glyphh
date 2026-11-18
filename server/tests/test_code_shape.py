"""The code stays small enough for an agent to hold in view: these limits fail CI when crossed."""

import ast
from pathlib import Path

SRC: Path = Path(__file__).resolve().parent.parent / "src"  # glyphh_server
MAX_FILE_LINES: int = 200
MAX_FUNCTION_LINES: int = 40
MAX_CLASS_LINES: int = 120


def _sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _span(node: ast.AST) -> int:
    return (node.end_lineno or node.lineno) - node.lineno + 1  # type: ignore[attr-defined]


def test_every_source_file_is_small() -> None:
    big = {str(p.relative_to(SRC)): n for p in _sources() if (n := len(p.read_text().splitlines())) > MAX_FILE_LINES}
    assert big == {}, f"files over {MAX_FILE_LINES} lines: {big}"


def test_every_function_and_class_is_small() -> None:
    big: dict[str, int] = {}
    for path in _sources():
        for node in ast.walk(ast.parse(path.read_text())):
            limit = {
                ast.FunctionDef: MAX_FUNCTION_LINES,
                ast.AsyncFunctionDef: MAX_FUNCTION_LINES,
                ast.ClassDef: MAX_CLASS_LINES,
            }.get(type(node))
            if limit and _span(node) > limit:
                big[f"{path.relative_to(SRC)}:{node.name}"] = _span(node)  # type: ignore[attr-defined]
    assert big == {}, f"functions over {MAX_FUNCTION_LINES} or classes over {MAX_CLASS_LINES} lines: {big}"
