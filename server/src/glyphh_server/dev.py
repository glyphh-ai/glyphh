"""Development only: a hosted runtime without Fly, for a rrotor you run yourself (Docker on this machine, an ngrok
name as its address). Makes the person's hosted runtime row with a fresh token and prints the environment the
container takes. Run inside the server's container:

    docker compose exec server python -m glyphh_server.dev runtime <email> [--host <ngrok name>]

Refused in prod."""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.models import Rrotor, User
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.machines import DEFAULT_NAME, DEFAULT_SIZE
from glyphh_server.ops.runtimes import FIRST, NOT_LINKED


async def hosted_runtime(conn: AsyncConnection, email: str) -> tuple[uuid.UUID, str]:
    """The person's first hosted machine (made, or its token rotated): its id and a token shown once."""
    user_id = (await conn.execute(select(User.id).where(User.email == email))).scalar()
    if user_id is None:
        raise SystemExit(f"nobody signed in as {email}")
    token = make_secret()
    mine = select(Rrotor.id).where(Rrotor.user_id == user_id, Rrotor.mode == "hosted").order_by(*FIRST).limit(1)
    runtime_id = (await conn.execute(mine)).scalar()
    if runtime_id is None:
        values = {"user_id": user_id, "mode": "hosted", "state": NOT_LINKED, "region": "local"}
        values |= {"name": DEFAULT_NAME, "size": DEFAULT_SIZE}
        made = insert(Rrotor).values(**values, token_hash=hash_secret(token)).returning(Rrotor.id)
        runtime_id = (await conn.execute(made)).scalar_one()
    else:
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(token_hash=hash_secret(token), seq=0))
    return runtime_id, token


def lines(settings: Settings, runtime_id: uuid.UUID, token: str, host: str | None) -> list[str]:
    env = {
        "RROTOR_MODE": "hosted",
        "RROTOR_SERVER": settings.base_url,
        "RROTOR_RUNTIME_ID": str(runtime_id),
        "RROTOR_RUNTIME_TOKEN": token,
        "RROTOR_PUBLIC_HOST": host or "<your ngrok name>",
    }
    return [f"{k}={v}" for k, v in env.items()]


async def run(argv: Sequence[str], settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="glyphh_server.dev", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    runtime = commands.add_parser("runtime", help="a hosted runtime for a person, run by hand")
    runtime.add_argument("email")
    runtime.add_argument("--host", help="the rrotor's public name (an ngrok domain)")
    args = parser.parse_args(argv)
    cfg = settings or get_settings()
    if cfg.env == "prod":
        print("glyphh_server.dev is for development only.", file=sys.stderr)
        return 2
    engine = make_engine(cfg.database_url)
    try:
        async with engine.begin() as conn:
            runtime_id, token = await hosted_runtime(conn, args.email)
    finally:
        await engine.dispose()
    print("\n".join(lines(cfg, runtime_id, token, args.host)))
    return 0


def main() -> int:  # pragma: no cover  (the command itself)
    return asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
