"""An import's file read as cases, one at a time (the file is never held whole): JSON Lines, one case a line ({data,
outcome?, outcomes?, ts?, id?}); CSV with a header, each column a role by its path (layer.segment.role), `outcome`,
`outcome.<output>`, `ts` or `id`, by its header or by the import's mapping ({header: target}, a null target skips the
column), each cell read by its role's kind (a number for a numeric role, text for a text role, a set for a plain
role's `;`-separated values, an empty cell nothing); or an export of a model (export.py), whose cases are stored
situations, read as they were kept.

Each case comes with its row number (a JSON line's, or a CSV record's, counting the header as row 1), or a refusal
for that row (path, message) instead."""

import csv
import io
import json
import zipfile
from collections.abc import Callable, Iterator
from typing import Any

import glyphh_spec

from glyphh_ada.errors import Refusal

Row = tuple[int, dict[str, Any] | None, tuple[str, str] | None]
TOP: tuple[str, ...] = ("outcome", "ts", "id")
ZIP_MAGIC: bytes = b"PK\x03\x04"


def jsonl(stream: io.BufferedIOBase, at: int = 0) -> Iterator[Row]:
    for n, line in enumerate(io.TextIOWrapper(stream, encoding="utf-8", errors="strict"), start=1):
        if n <= at or not line.strip():
            continue
        try:
            case = json.loads(line)
        except ValueError as e:
            yield n, None, ("", f"not JSON: {e}")
            continue
        yield (n, case, None) if isinstance(case, dict) else (n, None, ("", "a case is a JSON object"))


def _role(spec: glyphh_spec.Spec, path: str) -> Any:
    try:
        layer_name, seg_name, role_name = path.split(".")
        layer = spec._layer(layer_name)
        return spec._role(spec._segment(layer, seg_name, layer_name), role_name, f"{layer_name}.{seg_name}")
    except (ValueError, glyphh_spec.SpecError):
        return None


def target(spec: glyphh_spec.Spec, name: str) -> Callable[[dict[str, Any], str], None] | None:
    """What a column writes into a case, by its target's name; None for a target the spec does not know."""
    if name in TOP:
        return lambda case, cell: case.__setitem__(name, float(cell) if name == "ts" else cell)
    if name.startswith("outcome."):
        output = name.removeprefix("outcome.")
        if output not in dict(spec.outputs):
            return None
        return lambda case, cell: case.setdefault("outcomes", {}).__setitem__(output, cell)
    role = _role(spec, name)
    if role is None:
        return None
    ln, sn, rn = name.split(".")

    def put(case: dict[str, Any], cell: str) -> None:
        value: Any = cell
        if role.numeric_config is not None:
            value = float(cell)
        elif not role.text_encoding and ";" in cell:
            value = [part.strip() for part in cell.split(";") if part.strip()]
        case.setdefault("data", {}).setdefault(ln, {}).setdefault(sn, {})[rn] = value

    return put


def columns(spec: glyphh_spec.Spec, header: list[str], mapping: dict[str, str | None]) -> list[Any]:
    """Each column's writer (None: skipped), or the whole import refused naming the column the spec cannot take."""
    out = []
    for name in header:
        aim = mapping.get(name, name)
        put = None if aim is None else target(spec, aim)
        if aim is not None and put is None:
            message = f"The column {name!r} is {aim!r}, which is no role of the spec, nor outcome, ts or id."
            raise Refusal("E_MAPPING", message, 422, column=name, target=aim)
        out.append(put)
    return out


def table(stream: io.BufferedIOBase, spec: glyphh_spec.Spec, mapping: dict[str, Any], at: int = 0) -> Iterator[Row]:
    reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
    writers = columns(spec, next(reader, []), mapping)
    for n, record in enumerate(reader, start=2):
        if n <= at or not any(cell.strip() for cell in record):
            continue
        case: dict[str, Any] = {}
        try:
            for put, cell in zip(writers, record, strict=False):
                if put is not None and cell.strip():
                    put(case, cell.strip())
        except ValueError:
            yield n, None, ("", "a numeric column holds something that is not a number")
            continue
        yield (n, case, None) if "data" in case else (n, None, ("", "no role carries a value"))


def exported(archive: zipfile.ZipFile, at: int = 0) -> Iterator[Row]:
    """An export's precedents, as kept: {id, situation, outcome, outcomes, ts, author}."""
    with archive.open("precedents.jsonl") as stream:
        yield from jsonl(stream, at)  # type: ignore[arg-type]


def is_zip(stream: io.BufferedReader) -> bool:
    return stream.peek(4)[:4] == ZIP_MAGIC
