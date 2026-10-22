"""Files in an org's schema (worker side): an import's upload and an export's archive, each named by its job's id and
kept as rows of limits.CHUNK bytes in `files`, so the service needs no volumes and no object storage. Read back as a
stream (one chunk in memory at a time) or into a temporary file (an SQLite store, a zip). Kept only while their job
needs them: an import's upload until the import ends, an export's archive while its download link works."""

import io
import os
import tempfile
from collections.abc import Iterable

import psycopg

from glyphh_ada import limits
from glyphh_ada.catalog import q

_STALE = """
    DELETE FROM {s}.files f USING {s}.jobs j WHERE f.id = j.id AND (
        (j.kind = 'export' AND j.finished_at < now() - make_interval(secs => %(ttl)s))
        OR (j.kind = 'import' AND j.state IN ('done', 'failed'))
        OR (j.state = 'awaiting' AND j.created_at < now() - make_interval(secs => %(ttl)s)))
"""
_EXPIRED = """
    UPDATE {s}.jobs SET state = 'failed', finished_at = now(),
        error = '{{"code": "E_EXPIRED", "message": "No file came while its upload link worked."}}'
    WHERE state = 'awaiting' AND created_at < now() - make_interval(secs => %(ttl)s)
"""


def write(conn: psycopg.Connection, schema: str, fid: str, pieces: Iterable[bytes]) -> int:
    """The file, written whole in one transaction, a piece a row (what was there under this id before, gone).
    Returns its size."""
    size = 0
    with conn.transaction():
        conn.execute(q(schema, "DELETE FROM {s}.files WHERE id = %s"), (fid,))
        for n, piece in enumerate(pieces):
            conn.execute(q(schema, "INSERT INTO {s}.files (id, n, data) VALUES (%s, %s, %s)"), (fid, n, piece))
            size += len(piece)
    return size


class _Chunks(io.RawIOBase):
    """A file's chunks as a raw stream, read one row at a time."""

    def __init__(self, conn: psycopg.Connection, schema: str, fid: str) -> None:
        self.conn, self.query, self.fid = conn, q(schema, "SELECT data FROM {s}.files WHERE id = %s AND n = %s"), fid
        self.n, self.held, self.at = 0, memoryview(b""), 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:  # type: ignore[override]
        if self.at == len(self.held):
            found = self.conn.execute(self.query, (self.fid, self.n)).fetchone()
            if found is None:
                return 0
            self.held, self.at, self.n = memoryview(bytes(found[0])), 0, self.n + 1
        taken = min(len(buffer), len(self.held) - self.at)
        buffer[:taken] = self.held[self.at : self.at + taken]
        self.at += taken
        return taken


def reader(conn: psycopg.Connection, schema: str, fid: str) -> io.BufferedReader:
    return io.BufferedReader(_Chunks(conn, schema, fid))


def to_temp(conn: psycopg.Connection, schema: str, fid: str, suffix: str = "") -> str:
    """The file copied to a temporary file of its own; the caller removes it."""
    handle, path = tempfile.mkstemp(suffix=suffix, prefix="ada-")
    with os.fdopen(handle, "wb") as out, reader(conn, schema, fid) as source:
        while piece := source.read(limits.CHUNK):
            out.write(piece)
    return path


def from_path(conn: psycopg.Connection, schema: str, fid: str, path: str) -> int:
    with open(path, "rb") as source:
        return write(conn, schema, fid, iter(lambda: source.read(limits.CHUNK), b""))


def delete(conn: psycopg.Connection, schema: str, fid: str) -> None:
    conn.execute(q(schema, "DELETE FROM {s}.files WHERE id = %s"), (fid,))


def prune(conn: psycopg.Connection, schema: str) -> None:
    """Files no job needs any more, gone; imports whose file never came within their link's life, failed."""
    conn.execute(q(schema, _STALE), {"ttl": limits.LINK_TTL})
    conn.execute(q(schema, _EXPIRED), {"ttl": limits.LINK_TTL})
