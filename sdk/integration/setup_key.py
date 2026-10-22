"""Run inside the server's container (built from glyphh-ai/server's ada-cloud-connector): two people and their Free orgs
made straight in the database, as the server's own load script does, then an API key for each made through the Ada
API by that person's sign-in. The second org's month is used already: its Free plan's requests (cloud_requests),
counted in ada_usage as the server's minute tick leaves them, so its next read is refused 403 E_LIMIT `requests`.
Prints the two keys, one a line, nothing else. Never against production."""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import insert, select

from glyphh_server.config import get_settings
from glyphh_server.db import tenancy
from glyphh_server.db.engine import make_engine
from glyphh_server.models import AdaUsage, Install, User
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.orgs import new_person
from glyphh_server.ops.plans import org_version


async def signed_in(month_used: bool) -> str:
    engine = make_engine(get_settings().database_url)
    async with engine.begin() as conn:
        user_id = await new_person(conn, f"sdk-{uuid.uuid4().hex[:8]}@sdk.test", "SDK Test")
        values = {"user_id": user_id, "machine_id": uuid.uuid4().hex, "name": "sdk", "surface": "desktop"}
        values["mod_version"] = "1.0.0"
        install_id = (await conn.execute(insert(Install).values(values).returning(Install.id))).scalar_one()
        token = await tokens.issue(conn, install_id)
        if month_used:
            org_id = (await conn.execute(select(User.org_id).where(User.id == user_id))).scalar_one()
            await tenancy.enter(conn, org_id)
            cap = (await org_version(conn, org_id)).cloud_requests
            month = datetime.now(UTC).strftime("%Y-%m")
            await conn.execute(insert(AdaUsage).values(org_id=org_id, period=month, requests=cap))
    await engine.dispose()
    return token


async def key(http: httpx.AsyncClient, month_used: bool) -> str:
    token = await signed_in(month_used)
    made = await http.post("/v1/keys", json={"name": "sdk integration"}, headers={"authorization": f"Bearer {token}"})
    made.raise_for_status()
    return str(made.json()["key"])


async def main() -> None:
    url = os.environ.get("ADA_URL", "http://ada:8080")
    async with httpx.AsyncClient(base_url=url, timeout=30) as http:
        keys = [await key(http, False), await key(http, True)]
    sys.stdout.write("\n".join(keys) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
