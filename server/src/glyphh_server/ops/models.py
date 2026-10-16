"""Models: the server's record of what a person's rrotor runs. A model is a name and maybe its repo; each version is
one commit, numbered as it is added; a deploy puts a version on a runtime, which answers `deployed` on its link, and
that version is the active one there. The code, its data and its secrets stay in the repo and the rrotor.

Ada's `models` limit, from the plan or the add-on, is checked when a model is made; without Ada, none may be."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Row, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Forbidden, LimitReached, NotFound
from glyphh_server.models import Deployment, Model, ModelVersion
from glyphh_server.ops.addons import licensed
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.limits import lock_user
from glyphh_server.ops.link.calls import DeployAction, send_deploy
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.plans import org_plan
from glyphh_server.ops.runtimes import runtime_for

ADA: str = "ada"


class VersionView(BaseModel):
    id: uuid.UUID
    version: int
    commit_sha: str
    created_at: datetime
    active_on: list[uuid.UUID] = Field(default_factory=list, description="The runtimes this version is active on")


class ModelView(BaseModel):
    id: uuid.UUID
    name: str
    repo: str | None
    created_at: datetime
    versions: list[VersionView]


class Deployed(BaseModel):
    model: str
    version: int
    runtime_id: uuid.UUID
    action: DeployAction


_VERSION = (ModelVersion.id, ModelVersion.model_id, ModelVersion.version, ModelVersion.commit_sha)


async def models_allowed(conn: AsyncConnection, who: Principal) -> int | None:
    """How many models Ada allows the person (None: no limit); E_FORBIDDEN when the org has no Ada."""
    plan = await org_plan(conn, who.org_id)
    mods = plan.mods | await licensed(conn, who.org_id, plan.name)
    if ADA not in mods:
        raise Forbidden("Ada is not on your plan. Add it as an add-on first.", reason="no_ada")
    return mods[ADA].limits.get("models")


async def _views(conn: AsyncConnection, where: Any) -> list[ModelView]:
    rows = await conn.execute(select(Model).where(where).order_by(Model.created_at, Model.id))
    found = {r.id: ModelView(id=r.id, name=r.name, repo=r.repo, created_at=r.created_at, versions=[]) for r in rows}
    if not found:
        return []
    versions = (
        select(*_VERSION, ModelVersion.created_at)
        .where(ModelVersion.model_id.in_(found))
        .order_by(ModelVersion.model_id, ModelVersion.version)
    )
    seen: dict[uuid.UUID, VersionView] = {}
    for v in await conn.execute(versions):
        seen[v.id] = VersionView(id=v.id, version=v.version, commit_sha=v.commit_sha, created_at=v.created_at)
        found[v.model_id].versions.append(seen[v.id])
    active = select(Deployment.model_version_id, Deployment.rrotor_id).where(
        Deployment.model_version_id.in_(seen), Deployment.active.is_(True)
    )
    for d in await conn.execute(active.order_by(Deployment.deployed_at, Deployment.rrotor_id)):
        seen[d.model_version_id].active_on.append(d.rrotor_id)
    return list(found.values())


async def list_models(conn: AsyncConnection, who: Principal) -> list[ModelView]:
    return await _views(conn, Model.user_id == who.user_id)


async def get_model(conn: AsyncConnection, who: Principal, model_id: uuid.UUID) -> ModelView:
    found = await _views(conn, (Model.user_id == who.user_id) & (Model.id == model_id))
    if not found:
        raise NotFound("You have no such model.", model_id=str(model_id))
    return found[0]


async def by_name(conn: AsyncConnection, who: Principal, name: str) -> uuid.UUID:
    """The person's model of that name (the newest, should a name have been used twice)."""
    mine = select(Model.id).where(Model.user_id == who.user_id, Model.name == name)
    found = (await conn.execute(mine.order_by(Model.created_at.desc(), Model.id.desc()).limit(1))).scalar()
    if found is None:
        raise NotFound("You have no model of that name.", model=name)
    return found


async def create_model(conn: AsyncConnection, who: Principal, name: str, repo: str | None) -> ModelView:
    """A new model, within Ada's models limit, its name new to the person; no versions yet."""
    await lock_user(conn, who.user_id)
    allowed = await models_allowed(conn, who)
    used = int((await conn.execute(select(func.count()).where(Model.user_id == who.user_id))).scalar_one())
    if allowed is not None and used >= allowed:
        raise LimitReached(
            f"Ada allows you {allowed} models. Remove one first.", limit="models", used=used, max=allowed, plan=None
        )
    taken = select(Model.id).where(Model.user_id == who.user_id, Model.name == name)
    if (await conn.execute(taken)).first() is not None:
        raise Conflict("You already have a model of that name.", reason="name_taken", model=name)
    values = {"user_id": who.user_id, "org_id": who.org_id, "name": name, "repo": repo}
    model_id = (await conn.execute(insert(Model).values(values).returning(Model.id))).scalar_one()
    return await get_model(conn, who, model_id)


async def delete_model(conn: AsyncConnection, who: Principal, model_id: uuid.UUID) -> None:
    """The record goes, with its versions, deployments and runs; the rrotor keeps its copy until told to remove it."""
    gone = await conn.execute(delete(Model).where(Model.id == model_id, Model.user_id == who.user_id))
    if gone.rowcount == 0:
        raise NotFound("You have no such model.", model_id=str(model_id))


async def _mine(conn: AsyncConnection, who: Principal, model_id: uuid.UUID) -> Row:
    """The person's model, its row locked: versions are numbered one at a time."""
    mine = select(Model.id, Model.name).where(Model.id == model_id, Model.user_id == who.user_id).with_for_update()
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no such model.", model_id=str(model_id))
    return row


async def add_version(
    conn: AsyncConnection, who: Principal, model_id: uuid.UUID, commit_sha: str, manifest: dict[str, Any]
) -> VersionView:
    """The next version: a commit not yet a version, with its manifest (glyphh.json) as the rrotor reads it."""
    await _mine(conn, who, model_id)
    known = select(ModelVersion.version).where(ModelVersion.model_id == model_id, ModelVersion.commit_sha == commit_sha)
    if (had := (await conn.execute(known)).scalar()) is not None:
        raise Conflict("That commit is already a version.", reason="commit_known", version=had)
    last = (
        await conn.execute(select(func.max(ModelVersion.version)).where(ModelVersion.model_id == model_id))
    ).scalar()
    values = {"model_id": model_id, "version": (last or 0) + 1, "commit_sha": commit_sha, "manifest": manifest}
    made = insert(ModelVersion).values(values).returning(*_VERSION, ModelVersion.created_at)
    row = (await conn.execute(made)).one()
    return VersionView(id=row.id, version=row.version, commit_sha=row.commit_sha, created_at=row.created_at)


async def deploy_version(
    conn: AsyncConnection,
    hub: Hub,
    github: GitHubApp | None,
    who: Principal,
    model_id: uuid.UUID,
    version: int,
    runtime_id: uuid.UUID | None,
    action: DeployAction,
) -> Deployed:
    """Deploy, activate or remove one version on a runtime (the caller's own, as runtime_for picks it). The rrotor
    fetches the commit and answers `deployed` on its link; until then the version is not active there."""
    model = await _mine(conn, who, model_id)
    found = select(ModelVersion.id).where(ModelVersion.model_id == model_id, ModelVersion.version == version)
    version_id = (await conn.execute(found)).scalar()
    if version_id is None:
        raise NotFound("That model has no such version.", model_id=str(model_id), version=version)
    runtime = await runtime_for(conn, who, runtime_id)
    await send_deploy(conn, hub, github, runtime, version_id, action)
    return Deployed(model=model.name, version=version, runtime_id=runtime, action=action)
