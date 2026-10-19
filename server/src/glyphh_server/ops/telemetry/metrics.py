"""The latest value of each of the org's metric series (a runtime's node, a metric and its point's attributes), as
its runtimes last sent it within retention: by runtime, node and metric name."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Rrotor, TelemetryMetric


class Metric(BaseModel):
    runtime_id: uuid.UUID
    runtime: str | None = Field(description="The runtime's name")
    node_id: str | None = Field(description="The node it came from (service.instance.id)")
    name: str = Field(description="rrotor.runs, rrotor.run.seconds, rrotor.precedents, …")
    unit: str
    kind: Literal["gauge", "sum", "histogram"]
    value: float | None = Field(description="A gauge's or sum's value; a histogram's sum")
    count: int | None = Field(description="A histogram's count; null otherwise")
    attributes: dict[str, Any] = Field(description="The point's own: model, function, status, …")
    at: datetime = Field(description="When it was measured")


class Metrics(BaseModel):
    metrics: list[Metric]


async def latest(
    conn: AsyncConnection, org_id: uuid.UUID, runtime: uuid.UUID | None, node: str | None, name: str | None
) -> Metrics:
    m = TelemetryMetric
    q = select(m, Rrotor.name.label("runtime")).join(Rrotor, Rrotor.id == m.rrotor_id).where(m.org_id == org_id)
    for column, wanted in ((m.rrotor_id, runtime), (m.node_id, node), (m.name, name)):
        q = q if wanted is None else q.where(column == wanted)
    q = q.ext(distinct_on(m.rrotor_id, m.series)).order_by(m.rrotor_id, m.series, m.at.desc())
    found = [Metric.model_validate({**r._mapping, "runtime_id": r.rrotor_id}) for r in await conn.execute(q)]
    found.sort(key=lambda x: (x.runtime or "", str(x.runtime_id), x.node_id or "", x.name, repr(x.attributes)))
    return Metrics(metrics=found)
