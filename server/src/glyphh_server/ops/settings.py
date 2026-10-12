"""A person's settings: what the platform remembers for them (the theme, the rail, each list's rows per page)
and, later, rrotor's. Read whole; changed a field at a time, a list's page size merged in by the list's name."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import UserSettings

PageSize = Literal[10, 25, 50, 100]


class Settings(BaseModel):
    theme: Literal["dark", "light", "system"] = "system"
    rail_collapsed: bool = False
    page_sizes: dict[str, PageSize] = Field(default_factory=dict)


class SettingsChange(BaseModel):
    theme: Literal["dark", "light", "system"] | None = None
    rail_collapsed: bool | None = None
    page_sizes: dict[str, PageSize] | None = Field(default=None, max_length=50)


async def settings_of(conn: AsyncConnection, user_id: uuid.UUID) -> Settings:
    row = (
        await conn.execute(
            select(UserSettings.theme, UserSettings.rail_collapsed, UserSettings.page_sizes).where(
                UserSettings.user_id == user_id
            )
        )
    ).first()
    if row is None:
        return Settings()
    return Settings(theme=row.theme, rail_collapsed=row.rail_collapsed, page_sizes=row.page_sizes)


async def change_settings(conn: AsyncConnection, user_id: uuid.UUID, change: SettingsChange) -> Settings:
    now = await settings_of(conn, user_id)
    values = {
        "theme": change.theme or now.theme,
        "rail_collapsed": now.rail_collapsed if change.rail_collapsed is None else change.rail_collapsed,
        "page_sizes": {**now.page_sizes, **(change.page_sizes or {})},
    }
    await conn.execute(
        insert(UserSettings)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(index_elements=[UserSettings.user_id], set_=values)
    )
    return Settings(**values)
