"""An artifact as the API and the connector show it (docs/specs/artifacts.md, 3.3): the row joined with its rrotor
(name, address, mode) and the people who submitted and reviewed it, and `url`, where the app is."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.orm import aliased

from glyphh_server.models import Artifact, Rrotor, User

LOCAL_URL: str = "http://127.0.0.1:7777"


class Person(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str


class ArtifactView(BaseModel):
    id: uuid.UUID
    runtime_id: uuid.UUID
    runtime_name: str
    runtime_url: str
    name: str
    title: str
    description: str
    version: int
    commit_sha: str
    roles: list[str]
    state: str
    submitted_by: Person | None
    submitted_at: datetime
    reviewed_by: Person | None
    reviewed_at: datetime | None
    reason: str | None
    url: str = Field(description="Where the app is: {runtime_url}/apps/{name}/")


class Page(BaseModel):
    artifacts: list[ArtifactView]
    page: int
    per_page: int
    total: int


def runtime_url(mode: str, public_url: str | None) -> str:
    """A self-hosted rrotor's address, or a local one's on its own machine."""
    return public_url if mode == "self" and public_url else LOCAL_URL


def app_url(mode: str, public_url: str | None, name: str) -> str:
    return f"{runtime_url(mode, public_url)}/apps/{name}/"


Submitter = aliased(User, name="submitter")
Reviewer = aliased(User, name="reviewer")
COLUMNS = (
    Artifact.id,
    Artifact.runtime_id,
    Artifact.name,
    Artifact.title,
    Artifact.description,
    Artifact.version,
    Artifact.commit_sha,
    Artifact.roles,
    Artifact.state,
    Artifact.submitted_at,
    Artifact.reviewed_at,
    Artifact.reason,
    Rrotor.name.label("runtime_name"),
    Rrotor.mode,
    Rrotor.public_url,
    Submitter.id.label("submitter_id"),
    Submitter.name.label("submitter_name"),
    Submitter.email.label("submitter_email"),
    Reviewer.id.label("reviewer_id"),
    Reviewer.name.label("reviewer_name"),
    Reviewer.email.label("reviewer_email"),
)


def query():  # type: ignore[no-untyped-def]
    """The rows with their rrotor and people, to filter and order."""
    return (
        select(*COLUMNS)
        .join(Rrotor, Rrotor.id == Artifact.runtime_id)
        .outerjoin(Submitter, Submitter.id == Artifact.submitted_by)
        .outerjoin(Reviewer, Reviewer.id == Artifact.reviewed_by)
    )


def _person(row: Row, prefix: str) -> Person | None:
    found = getattr(row, f"{prefix}_id")
    if found is None:
        return None
    return Person(id=found, name=getattr(row, f"{prefix}_name"), email=getattr(row, f"{prefix}_email"))


def view(row: Row) -> ArtifactView:
    return ArtifactView(
        id=row.id,
        runtime_id=row.runtime_id,
        runtime_name=row.runtime_name or "local",
        runtime_url=runtime_url(row.mode, row.public_url),
        name=row.name,
        title=row.title,
        description=row.description,
        version=row.version,
        commit_sha=row.commit_sha,
        roles=list(row.roles),
        state=row.state,
        submitted_by=_person(row, "submitter"),
        submitted_at=row.submitted_at,
        reviewed_by=_person(row, "reviewer"),
        reviewed_at=row.reviewed_at,
        reason=row.reason,
        url=app_url(row.mode, row.public_url, row.name),
    )
