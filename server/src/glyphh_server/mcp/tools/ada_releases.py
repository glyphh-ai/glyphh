"""The connector's Ada versions (docs/specs/ada-cloud.md, 12): every version with its status and release notes and
how many of the org's models run it (ada_releases), and a model moved to another (ada_upgrade). The tool named
ada_versions is a model's own versions (ada_models.py)."""

from collections import Counter
from typing import Any

from pydantic import Field

from glyphh_ada import registry
from glyphh_ada.api.tuning import Upgrade
from glyphh_server.mcp.tools.ada_base import NAME, ada
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool


class UpgradeArgs(Upgrade):
    name: str = NAME
    ada: str | None = Field(
        None, max_length=40, description="The Ada version (ada_releases); left out, the latest stable"
    )


def _line(v: dict[str, Any]) -> str:
    status = v["status"] + (f" (ends {v['ends']})" if v["ends"] else "")
    change = "changes answers" if v["changes_answers"] else "answers as the version before"
    return f"{v['name']}: {status}, released {v['released']}, {change}; {v['models']} of your models. {v['summary']}"


async def releases(ctx: Context, _: NoArgs) -> Done:
    reg, day = registry.registry(), registry.today()
    found, _v = await ada(ctx, "", "models", {})
    running = Counter(getattr(reg.find(m["ada"]), "name", m["ada"]) for m in found)
    out = [{**reg.view(v, day), "models": running[v.name]} for v in reg.versions]
    latest = reg.latest(day).name
    text = "\n".join(
        [f"The latest stable is {latest}, which new models get unless another is named."] + [_line(v) for v in out]
    )
    return Done(text, {"latest_stable": latest, "contract": registry.CONTRACT, "versions": out})


async def upgrade(ctx: Context, args: UpgradeArgs) -> Done:
    made, _v = await ada(ctx, args.name, "upgrade", args.model_dump(exclude_none=True, exclude={"name"}))
    text = (
        f"Version {made['version']} of {args.name} on {made['ada']} (from {made['from']}) is being made by job "
        f"{made['job']['id']}: the cases re-encoded, learned and calibrated by {made['ada']}. It goes live when the "
        f"job is done (ada_job); roll back by activating the version before it (ada_activate)."
    )
    return Done(text, made)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "ada_releases",
        "Ada versions",
        "Every Ada version (ada-1-0, ada-1-1-beta, ...): stable, beta, deprecated with its end date, or retired; "
        "whether it changes answers; its release notes; how many of the org's models run it; and the latest "
        "stable, which a new model gets unless another is named.",
        NoArgs,
        releases,
        True,
    ),
    Tool(
        "ada_upgrade",
        "Upgrade a model's Ada",
        "Move a model to another Ada version (left out, the latest stable; any supported one, older too): a new "
        "version re-encoded, learned and calibrated by that version's kernel, by a job, live when it is done. "
        "Backtest against it first (ada_backtest with ada). Roll back with ada_activate.",
        UpgradeArgs,
        upgrade,
    ),
)
