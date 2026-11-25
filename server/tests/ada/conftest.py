"""Ada Cloud under test: the server with GLYPHH_ADA_CLOUD on and `ada.test` as its Ada host, real worker processes'
loops running in threads (the ordinary role the server connects as, so the org schemas' row-level security holds),
pgvector made in the suite's database by its superuser (as Fly's Extensions page does in production)."""

import asyncio
import hashlib
import json
import multiprocessing
import threading
from collections.abc import AsyncIterator, Iterator
from multiprocessing.process import BaseProcess
from typing import Any

import asyncpg
import httpx
import pytest
from redis import Redis
from sqlalchemy import insert, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import loop
from glyphh_ada.process import Worker
from glyphh_ada.protocol import JOBS, SYNC
from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.models import Org, Plan, PlanVersion
from tests.conftest import ADMIN_URL, REDIS_URL, SETTINGS, _client
from tests.db.helpers import Person, person

HOST: str = "ada.test"
ADA: Settings = SETTINGS.model_copy(
    update={
        "ada_cloud": True,
        "ada_hosts": f"{HOST}, other.test",
        "ada_url": f"http://{HOST}",
        "stripe_price_ada": "price_test_ada",
        "stripe_meter_ada": "ada_requests",
    }
)

SHAPES: dict[str, Any] = {
    "name": "shapes",
    "seed": 5,
    "dimension": 2048,
    "layers": [
        {
            "name": "a",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "color"},
                        {"name": "shape"},
                        {"name": "size", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                        {"name": "secret", "security_weight": 0.9},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "output": {"costs": {"good": {"bad": 1}, "bad": {"good": 5}}, "ask_below": 0.55},
}


def shape(i: int, color: str = "r", size: int = 3, kind: str = "sq") -> dict[str, Any]:
    return {"a": {"s": {"color": color, "shape": kind, "size": size, "secret": f"s{i % 3}", "id": f"c{i}"}}}


def rid(i: int) -> str:
    """The id the spec's key part gives case i (glyphh_spec.Spec.key)."""
    return hashlib.sha256(json.dumps(f"c{i}").encode()).hexdigest()[:12]


def cases(n: int, start: int = 0) -> list[dict[str, Any]]:
    """n graded cases: red and small, or green and big, is good."""
    out = []
    for i in range(start, start + n):
        color, size = "rgbk"[i % 4], i % 11
        good = (color in "rg") ^ (size > 6)
        out.append({"data": shape(i, color, size, ["sq", "ci", "tr"][i % 3]), "outcome": "good" if good else "bad"})
    return out


@pytest.fixture(scope="session")
async def vector(engine: AsyncEngine) -> None:
    target = make_url(ADMIN_URL)
    admin = await asyncpg.connect(
        host=target.host, port=target.port, user=target.username, password=target.password, database=target.database
    )
    try:
        await admin.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await admin.close()


def _start(queue: str, kernel: str | None = None) -> Iterator[Worker]:
    stop = threading.Event()
    worker = Worker(ADA, queue, kernel)
    thread = threading.Thread(target=worker.serve, args=(stop,), daemon=True)
    thread.start()
    yield worker
    stop.set()
    thread.join(10)
    worker.ctx.conn.close()


@pytest.fixture
def streams(vector: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[Redis]:
    """Fresh streams for the test, and workers that look for messages often."""
    monkeypatch.setattr(loop, "BLOCK_MS", 100)
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    redis.delete("ada:sync", "ada:jobs", *redis.keys("ada:sync:*"), *redis.keys("ada:jobs:*"))  # each kernel's too
    yield redis
    redis.close()


@pytest.fixture
def worker(streams: Redis) -> Iterator[Worker]:
    yield from _start(SYNC)


@pytest.fixture
def jobs_worker(streams: Redis) -> Iterator[Worker]:
    yield from _start(JOBS)


BETA_KERNEL: str = "3.17.0"  # ada-1-2-beta's: its workers here run the venv's kernel under its name (the routing is
# what these tests prove; that each kernel's own install answers is proved in Docker, docs/specs/ada-cloud.md 12.10)


@pytest.fixture
def beta_worker(streams: Redis) -> Iterator[Worker]:
    yield from _start(SYNC, BETA_KERNEL)


@pytest.fixture
def beta_jobs_worker(streams: Redis) -> Iterator[Worker]:
    yield from _start(JOBS, BETA_KERNEL)


def _serve() -> None:
    Worker(ADA, SYNC).serve(threading.Event())


@pytest.fixture
def spawn(streams: Redis) -> Iterator[list[BaseProcess]]:
    """Worker processes of their own (start_process), as a process group runs them; killed after the test."""
    started: list[BaseProcess] = []
    yield started
    for process in started:
        process.kill()
        process.join(5)


def start_process(started: list[BaseProcess]) -> BaseProcess:
    process = multiprocessing.get_context("spawn").Process(target=_serve, daemon=True)
    process.start()
    started.append(process)
    return process


@pytest.fixture
async def ada(engine: AsyncEngine, vector: None) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(ADA)):
        c.base_url = httpx.URL(f"http://{HOST}")
        yield c


async def key_for(ada: httpx.AsyncClient, who: Person, clearance: float = 1.0) -> dict[str, str]:
    made = await ada.post("/v1/keys", json={"name": "test", "clearance": clearance}, headers=who.headers)
    assert made.status_code == 201, made.text
    return {"authorization": f"Bearer {made.json()['key']}"}


async def an_org(engine: AsyncEngine, ada: httpx.AsyncClient, clearance: float = 1.0) -> tuple[Person, dict[str, str]]:
    who = await person(engine, "Team")
    return who, await key_for(ada, who, clearance)


async def a_model(
    ada: httpx.AsyncClient, key: dict[str, str], name: str = "shapes", n: int = 0, spec: dict[str, Any] = SHAPES
) -> dict[str, Any]:
    made = await ada.post("/v1/models", json={"name": name, "spec": spec}, headers=key)
    assert made.status_code == 201, made.text
    if n:
        done = await ada.post(f"/v1/models/{name}/record_many", json={"cases": cases(n)}, headers=key)
        assert done.status_code == 200, done.text
    return dict(made.json())


async def finished(
    ada: httpx.AsyncClient, key: dict[str, str], job: dict[str, Any], tries: int = 600
) -> dict[str, Any]:
    """The job once it is done or failed (a jobs worker must be running)."""
    for _ in range(tries):
        got = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
        if got["state"] in ("done", "failed"):
            return dict(got)
        await asyncio.sleep(0.1)
    raise AssertionError(f"job {job['id']} never finished: {got}")


def path_of(url: str) -> str:
    """A link's path, for the test client (its host is the Ada host)."""
    return "/" + url.split("://", 1)[1].split("/", 1)[1]


async def pinned(engine: AsyncEngine, org_id: Any, **cloud: Any) -> None:
    """The org on a plan version of its own with these cloud limits (as a contract, or a version since superseded,
    would be): a retired plan's, so no other test's org finds it."""
    async with engine.begin() as conn:
        made = insert(Plan).values(name=f"Test {org_id}", active=False).returning(Plan.id)
        plan_id = (await conn.execute(made)).scalar_one()
        values = {"plan_id": plan_id, "version": 1, "price_cents": 9_900, "billing_interval": "month"}
        version = insert(PlanVersion).values(**values, **cloud).returning(PlanVersion.id)
        version_id = (await conn.execute(version)).scalar_one()
        await conn.execute(update(Org).where(Org.id == org_id).values(plan_version_id=version_id))
