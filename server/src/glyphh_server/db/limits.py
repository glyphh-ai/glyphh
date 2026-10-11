"""Plan limits the database itself enforces, so a bug in a route cannot get around them.

Seats: active users plus open invites never pass the plan's max_seats. The check locks the org's row
before counting, so requests at the same moment are taken one after another and exactly one gets the
last seat. Only adding is checked: a downgrade never cuts anyone off. Re-run on every boot."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

LIMIT_MARK: str = "E_LIMIT"

SEATS_FUNCTION: str = """
CREATE OR REPLACE FUNCTION glyphh_check_seats() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  allowed int;
  taken int;
  me uuid := NEW.id;
BEGIN
  SELECT p.max_seats INTO allowed FROM orgs o JOIN plans p ON p.id = o.plan_id WHERE o.id = NEW.org_id FOR UPDATE OF o;
  IF allowed IS NULL THEN RETURN NEW; END IF;
  SELECT (SELECT count(*) FROM users u WHERE u.org_id = NEW.org_id AND u.disabled_at IS NULL AND u.id <> me)
       + (SELECT count(*) FROM invites i WHERE i.org_id = NEW.org_id AND i.accepted_at IS NULL
            AND i.revoked_at IS NULL AND i.expires_at > now() AND i.id <> me)
    INTO taken;
  IF taken >= allowed THEN
    RAISE EXCEPTION 'E_LIMIT seats %', allowed USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END $$;
"""

SEATS_TRIGGERS: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS users_seats_insert ON users",
    "CREATE TRIGGER users_seats_insert BEFORE INSERT ON users FOR EACH ROW EXECUTE FUNCTION glyphh_check_seats()",
    "DROP TRIGGER IF EXISTS users_seats_return ON users",
    "CREATE TRIGGER users_seats_return BEFORE UPDATE OF disabled_at, org_id ON users FOR EACH ROW"
    " WHEN (NEW.disabled_at IS NULL AND (OLD.disabled_at IS NOT NULL OR OLD.org_id <> NEW.org_id))"
    " EXECUTE FUNCTION glyphh_check_seats()",
    "DROP TRIGGER IF EXISTS invites_seats_insert ON invites",
    "CREATE TRIGGER invites_seats_insert BEFORE INSERT ON invites FOR EACH ROW EXECUTE FUNCTION glyphh_check_seats()",
)


async def apply_limits(conn: AsyncConnection) -> None:
    await conn.execute(text(SEATS_FUNCTION))
    for statement in SEATS_TRIGGERS:
        await conn.execute(text(statement))


def is_limit(error: BaseException) -> bool:
    """Was this database error a plan limit refusing the write?"""
    return LIMIT_MARK in str(error)
