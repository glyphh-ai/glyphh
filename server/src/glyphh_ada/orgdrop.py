"""An org's Ada data gone with the org (docs/specs/ada-cloud.md, 6.5): its whole schema dropped in the transaction that
removes the org, so every model, precedent, version, job and file of it leaves the live database at once. Workers
holding one of its models find its tables gone on their next message and answer E_MODEL_MISSING (handlers.py). The
managed database's backups keep it until they age out (docs/architecture.md, Ada Cloud)."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.pg import schema_for


async def drop(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_for(str(org_id))}" CASCADE'))
