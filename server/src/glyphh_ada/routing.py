"""Which kernel answers a message (docs/specs/ada-cloud.md, 12.4). A model's answers, learning and jobs are computed
by the kernel of its active version's Ada version; a new model's by the one it is made on; a re-encode's by the
version it makes active (an upgrade's target, or a rollback's old version); a backtest's by each candidate's, one
kernel after another. Ops that touch no kernel (protocol.ANY_KERNEL) are answered by whichever worker took them.

The kernel a process imported is the one it serves (`installed`): the venv's (the latest stable's) unless its worker
was started with another first on its path (worker.py)."""

import importlib.metadata
from typing import Any

import glyphh_kernel
import psycopg

from glyphh_ada import catalog, registry, versions
from glyphh_ada.errors import Refusal
from glyphh_ada.protocol import ANY_KERNEL, Message

NOTICES: frozenset[str] = frozenset({"deprecated", "moved", "retired"})  # told on every answer, as a header


def installed() -> str:
    """The kernel release this process imported."""
    return getattr(glyphh_kernel, "__version__", None) or importlib.metadata.version("glyphh-kernel")


def for_message(conn: psycopg.Connection, schema: str, msg: Message) -> tuple[str | None, catalog.Live | None]:
    """(the kernel that must answer this message, or None for any; the live model, when there is one)."""
    reg = registry.registry()
    if msg.op == "create":
        return reg.choose(msg.args.get("ada"), registry.today()).kernel, None
    if not msg.model:
        return None, None
    found = catalog.active(conn, schema, msg.model)
    if found is None or msg.op in ANY_KERNEL:
        return None, found
    return reg.kernel_of(found.ada), found


def for_job(conn: psycopg.Connection, schema: str, job: dict[str, Any]) -> str:
    """The kernel a job runs on."""
    nxt = (job.get("result") or {}).get("next")
    if job["kind"] == "backtest" and nxt:
        return str(nxt)
    found = catalog.live(conn, schema, job["model"])
    ada = found.ada
    if job["kind"] == "reencode":
        ada = versions.row(conn, schema, found, int(job["args"]["version"]))[5]
    return registry.registry().kernel_of(ada)


def check(kernel: str) -> None:
    """Refused (503 E_ADA_UNAVAILABLE) when this deploy runs no worker for the kernel."""
    if kernel not in registry.registry().kernels():
        raise Refusal(
            "E_ADA_UNAVAILABLE", "This model's Ada version is not running here: try again shortly.", 503, kernel=kernel
        )


def about(found: catalog.Live | None) -> dict[str, Any] | None:
    """The model's Ada version for the API's headers, with what every answer should tell the caller."""
    if found is None:
        return None
    notice = catalog.ada_of(found)["ada_notice"]
    return {"name": found.ada, "notice": notice if notice and notice["kind"] in NOTICES else None}
