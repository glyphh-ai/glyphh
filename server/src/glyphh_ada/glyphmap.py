"""The platform's 3D view of a model (worker side, a look: nothing counted against the month), after the old
GlyphViewer: a sample of its active store's precedents, up to MAP_MAX (all of them when it holds no more; else a
repeatable block sample of the store), each with its id, its outcomes and its glyph as bits, and each one's nearest
in the sample by the Jaccard similarity of their bits (the viewer's layout springs), worked out here with numpy
rather than in the browser.

A glyph is the case's as stored, or one layer's (`layer`), encoded as the kernel encodes that part of the case.
A reader whose clearance may not see a part of a case gets the glyph of what it may see, made again."""

import base64
from typing import Any

import glyphh_kernel
import glyphh_spec
import numpy as np
import psycopg
from glyphh_postgres import unpack
from psycopg import sql

from glyphh_ada import catalog
from glyphh_ada.cache import Entry
from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal
from glyphh_ada.seen import readable, visible

MAP_MAX: int = 2000
NEIGHBOURS: int = 10
_ALL = "SELECT id, outcome, glyph, situation FROM {s}.{p} LIMIT {n}"
# a block sample of about twice what is shown, so the limit is met however the blocks fall; the same each time
_SAMPLED = "SELECT id, outcome, glyph, situation FROM {s}.{p} TABLESAMPLE SYSTEM ({pct}) REPEATABLE (42) LIMIT {n}"
_NAMED = "SELECT id, output, value FROM {s}.outcomes WHERE model = %s AND id = ANY(%s)"


def _rows(conn: psycopg.Connection, schema: str, store: str, held: int, limit: int) -> list[Any]:
    names = {"s": sql.Identifier(schema), "p": sql.Identifier(catalog._part(store)), "n": sql.Literal(limit)}
    if held <= limit:
        query = sql.SQL(_ALL).format(**names)
    else:
        query = sql.SQL(_SAMPLED).format(**names, pct=sql.Literal(min(100.0, 200.0 * limit / held)))
    with conn.cursor(binary=True) as cur:
        cur.execute(query)
        return cur.fetchall()


def neighbours(bits: np.ndarray, k: int = NEIGHBOURS) -> list[list[Any]]:
    """Each row's k most similar others by the Jaccard similarity of their bits, as undirected edges [i, j, sim],
    i < j, each once; rows with nothing in common share no edge."""
    n = len(bits)
    if n < 2:
        return []
    b = bits.astype(np.float32)
    inter = b @ b.T
    ones = b.sum(axis=1)
    union = ones[:, None] + ones[None, :] - inter
    sim = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    np.fill_diagonal(sim, -1.0)
    k = min(k, n - 1)
    best: dict[tuple[int, int], float] = {}
    for i, row in enumerate(np.argpartition(-sim, k - 1, axis=1)[:, :k]):
        for j in (int(j) for j in row):
            if sim[i, j] > 0:
                best[(min(i, j), max(i, j))] = float(sim[i, j])
    return [[i, j, round(s, 4)] for (i, j), s in sorted(best.items())]


def _glyph(space: glyphh_kernel.Space, spec: glyphh_spec.Spec, row: Any, layer: str | None, clearance: float) -> Any:
    """The row's glyph as booleans (+1 as true), or None when it has nothing in that layer for this reader."""
    situation = row[3]
    seen = visible(spec, situation, clearance)
    if layer is None and seen == situation:
        return unpack(row[2].data, row[2].n) > 0
    part = seen if layer is None else seen.get(layer)
    if not part:
        return None
    return glyphh_kernel.encode(part, None, space.seed, space.dim, space.lexicon) > 0


def _points(rows: list[Any], glyphs: list[Any], named: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "id": r[0],
            "outcome": r[1] or None,
            "outcomes": named.get(r[0], {}),
            "bits": None if g is None else base64.b64encode(np.packbits(g).tobytes()).decode(),
        }
        for r, g in zip(rows, glyphs, strict=True)
    ]


def glyph_map(conn: psycopg.Connection, schema: str, entry: Entry, args: dict[str, Any], clearance: float) -> Any:
    """{version, dim, layers, layer, total, points: [{id, outcome, outcomes, bits}], edges: [[i, j, sim]]}: bits
    are a glyph packed (+1 as 1, first bit highest), base64, or null when the case has nothing there to show; an
    edge's i and j are points' places."""
    spec, space, layer = entry.model.spec, entry.model.space, args.get("layer")
    readable(spec, clearance)
    layers = [each.name for each in spec.layers]
    if layer is not None and layer not in layers:
        raise Refusal("E_LAYER", f"This model's spec has no layer {layer}.", 404, layer=layer, layers=layers)
    held = catalog.count(conn, schema, space.store.model)
    rows = _rows(conn, schema, space.store.model, held, min(int(args.get("limit") or MAP_MAX), MAP_MAX))
    named: dict[str, dict[str, str]] = {}
    for rid, output, value in conn.execute(q(schema, _NAMED), (space.store.model, [r[0] for r in rows])).fetchall():
        named.setdefault(rid, {})[output] = value
    glyphs = [_glyph(space, spec, r, layer, clearance) for r in rows]
    shown = [i for i, g in enumerate(glyphs) if g is not None]
    found = neighbours(np.array([glyphs[i] for i in shown], dtype=np.uint8).reshape(len(shown), space.dim))
    return {
        "version": entry.version,
        "dim": space.dim,
        "layers": layers,
        "layer": layer,
        "total": held,
        "points": _points(rows, glyphs, named),
        "edges": [[shown[i], shown[j], s] for i, j, s in found],
    }
