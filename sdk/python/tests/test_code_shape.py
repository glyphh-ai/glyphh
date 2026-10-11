"""The hand-written SDK stays small enough for an agent to hold in view (the generated client is exempt)."""

import ast
from pathlib import Path

SRC: Path = Path(__file__).resolve().parent.parent / "src" / "glyphh"


def test_files_functions_and_classes_are_small() -> None:
    big: dict[str, int] = {}
    for path in SRC.glob("*.py"):
        lines = len(path.read_text().splitlines())
        if lines > 200:
            big[path.name] = lines
        for node in ast.walk(ast.parse(path.read_text())):
            limit = 40 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else 120
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                span = (node.end_lineno or node.lineno) - node.lineno + 1
                if span > limit:
                    big[f"{path.name}:{node.name}"] = span
    assert big == {}
