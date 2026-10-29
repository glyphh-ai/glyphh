"""Stored situations read by another spec: what a re-encode, a rollback and a backtest need. The store keeps each case
as the kernel holds it (its spec's situation, restated with what was learned), not as it was sent, so a spec that
reads a value differently (a number's bins, a text's encoding, a key part) cannot be applied to it: that needs the
cases sent again, into a new model. Everything else can: another seed or dimension, roles added or taken away,
weights, interactions, learning levers and the lexicon, outputs and their costs.

Also the learned state a store keeps (its meta: learned weights and temperatures), read and written whole: what a
version keeps when it stops being active, and gets back when it is made active again."""

from typing import Any

import glyphh_spec
import psycopg
from psycopg.types.json import Jsonb

from glyphh_ada.catalog import q
from glyphh_ada.errors import Refusal

READING: tuple[str, ...] = ("numeric_config", "text_encoding", "key_part")
# The settings that change what a stored case carries (its learned word weights and pairs, its words' glyphs)
STORED_SETTINGS: tuple[str, ...] = (*glyphh_spec.Settings.LEARNING, "lexicon", "word_reach")  # word_reach: 3.16.0
_LEARNED = "(key = 'learned' OR key LIKE 'learned:%%' OR key = 'tau' OR key LIKE 'tau:%%')"


def _roles(spec: glyphh_spec.Spec) -> dict[str, Any]:
    return {f"{ln.name}.{s.name}.{r.name}": r for ln in spec.layers for s in ln.segments for r in s.roles}


def strip(stored: dict[str, Any], spec: glyphh_spec.Spec) -> dict[str, Any]:
    """The stored situation cut to the roles this spec names (its interactions layer left out: restate makes it)."""
    roles = _roles(spec)
    out: dict[str, Any] = {}
    for ln, segs in stored.items():
        for sn, values in segs.items() if isinstance(segs, dict) else ():
            kept = {rn: v for rn, v in values.items() if f"{ln}.{sn}.{rn}" in roles}
            if kept:
                out.setdefault(ln, {})[sn] = kept
    return out


def restated(stored: dict[str, Any], spec: glyphh_spec.Spec) -> dict[str, Any]:
    """The stored situation as this spec (with whatever it learned) would hold it."""
    return spec.restate(strip(stored, spec))


def check_reading(old: glyphh_spec.Spec, new: glyphh_spec.Spec, at: str = "spec") -> None:
    """Refused (422 E_SPEC_READING) when the new spec reads a role both name differently."""
    before = _roles(old)
    moved = sorted(
        path
        for path, role in _roles(new).items()
        if path in before and any(getattr(role, k) != getattr(before[path], k) for k in READING)
    )
    if moved:
        raise Refusal(
            "E_SPEC_READING",
            f"These roles would read their values differently ({', '.join(READING)}), which the stored cases cannot "
            "be read again by: make a new model and import the cases into it.",
            422,
            roles=moved,
            at=at,
        )


def _canon(spec: glyphh_spec.Spec) -> Any:
    """What of a spec the stored cases depend on: the encoding, the roles and how each is read (with value weights
    given by hand), declared pairs and the settings that restate; not weights, security, outputs or other levers."""
    roles = {p: (r.key_part, r.numeric_config, r.text_encoding, r.value_weights) for p, r in _roles(spec).items()}
    pairs = sorted(i.roles for i in spec.interactions)
    # a setting an older kernel lacks reads as its default there: word_reach 1, the reading before 3.16.0
    return spec.dimension, spec.seed, roles, pairs, [getattr(spec.settings, k, 1) for k in STORED_SETTINGS]


def same_store(old: glyphh_spec.Spec, new: glyphh_spec.Spec) -> bool:
    """Whether the new spec reads the old one's store as it is (no re-encode)."""
    return bool(_canon(old) == _canon(new))


def learned_of(conn: psycopg.Connection, schema: str, key: str) -> dict[str, Any]:
    """A store's learned weights and temperatures, by meta key."""
    rows = conn.execute(q(schema, "SELECT key, value FROM {s}.meta WHERE model = %s AND " + _LEARNED), (key,))
    return {k: v for k, v in rows.fetchall()}


def set_learned(conn: psycopg.Connection, schema: str, key: str, kept: dict[str, Any]) -> None:
    """The store's learned state made exactly this (what it had and this lacks, gone)."""
    conn.execute(q(schema, "DELETE FROM {s}.meta WHERE model = %s AND " + _LEARNED), (key,))
    for name, value in kept.items():
        conn.execute(
            q(schema, "INSERT INTO {s}.meta (model, key, value) VALUES (%s, %s, %s)"), (key, name, Jsonb(value))
        )
