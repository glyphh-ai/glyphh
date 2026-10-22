"""The connector's Ada model tools: the org's models, making one from a spec, reading and deleting one; its spec and
settings changed as new versions, its versions listed and one made active again (a rollback)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada.api.models import NewModel
from glyphh_ada.api.tuning import Changes, NewSpec
from glyphh_server.errors import Conflict
from glyphh_server.mcp.tools.ada_base import NAME, Named, ada, args_of
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool


class SpecArgs(NewSpec):
    name: str = NAME


class Delete(Named):
    confirm: str = Field(description="The model's name again: deleting it and every precedent is not undone")


class Levers(Named):
    changes: dict[str, Any] | None = Field(None, description=Changes.model_fields["changes"].description)
    note: str | None = Field(None, max_length=500, description="Why: kept with the version")
    backtest: str | None = Field(None, description="The backtest job this change was chosen by: kept with the version")


class Activate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = NAME
    version: int = Field(ge=1, description="The version to make active (ada_versions lists them)")


def changed(name: str, answer: dict[str, Any]) -> str:
    """A new or reactivated version, in a line: live now, or being made by a job."""
    if answer["active"]:
        return f"Version {answer['version']} of {name} is active."
    job = answer["job"]["id"]
    return (
        f"Version {answer['version']} of {name} is being made by job {job} (the stored cases restated); it goes live "
        "when the job is done (ada_job)."
    )


async def models(ctx: Context, _: NoArgs) -> Done:
    found, _v = await ada(ctx, "", "models", {})
    lines = [f"{m['name']}: version {m['version']}, {m['precedents']:,} precedents" for m in found]
    return Done("\n".join(lines) or "No models yet: ada_model_create makes one.", {"models": found})


async def model(ctx: Context, args: Named) -> Done:
    found, _v = await ada(ctx, args.name, "model", {})
    return Done(f"{args.name}: version {found['version']}, {found['precedents']:,} precedents.", found)


async def create(ctx: Context, args: NewModel) -> Done:
    made, _v = await ada(ctx, args.name, "create", {"spec": args.spec})
    return Done(f"Made {args.name}, version 1, empty: record cases (ada_record_many) or import a file.", made)


async def delete(ctx: Context, args: Delete) -> Done:
    if args.confirm != args.name:
        raise Conflict("Confirm by sending the model's name as confirm.", reason="confirm", model=args.name)
    gone, _v = await ada(ctx, args.name, "delete", {})
    return Done(f"Deleted {args.name} and every precedent it held.", gone)


async def spec(ctx: Context, args: SpecArgs) -> Done:
    made, _v = await ada(ctx, args.name, "spec", args_of(args))
    return Done(changed(args.name, made), made)


async def settings(ctx: Context, args: Levers) -> Done:
    if args.changes is None:
        found, _v = await ada(ctx, args.name, "versions", {"levers": True})
        levers = ", ".join(f"{k} {v}" for k, v in found["settings"].items())
        return Done(f"{args.name}, version {found['version']}: {levers}.", found)
    made, _v = await ada(ctx, args.name, "settings", args_of(args))
    return Done(changed(args.name, made), made)


async def versions(ctx: Context, args: Named) -> Done:
    found, _v = await ada(ctx, args.name, "versions", {})
    lines = [
        f"{v['version']}{' (active)' if v['active'] else ''}: {v['note'] or 'no note'}, by {v['made_by']}, "
        f"{str(v['made_at'])[:10]}" + (", its store dropped" if v["gone"] else "")
        for v in found
    ]
    return Done("\n".join(lines), {"versions": found})


async def activate(ctx: Context, args: Activate) -> Done:
    made, _v = await ada(ctx, args.name, "activate", {"version": args.version})
    return Done(changed(args.name, made), made)


TOOLS: tuple[Tool, ...] = (
    Tool(
        "ada_models",
        "Ada models",
        "The org's Ada models: each one's active version and precedents.",
        NoArgs,
        models,
        True,
    ),
    Tool("ada_model", "Ada model", "One Ada model: its active spec and version, its precedents.", Named, model, True),
    Tool(
        "ada_model_create",
        "Make an Ada model",
        "A new model from its JSON spec (layers, segments, roles, output with its outcomes and costs, settings), "
        "checked by the kernel and the cloud's bounds: version 1, empty.",
        NewModel,
        create,
    ),
    Tool(
        "ada_model_delete",
        "Delete an Ada model",
        "Delete a model and every precedent it holds; confirm repeats its name. Not undone.",
        Delete,
        delete,
    ),
    Tool(
        "ada_spec_update",
        "Change an Ada spec",
        "A new version from a whole spec, with a note: live at once, or (when it changes what a stored case carries) "
        "made by a job that restates the cases while the old version serves. How a role reads its values cannot "
        "change.",
        SpecArgs,
        spec,
    ),
    Tool(
        "ada_settings",
        "Ada settings",
        "Every lever of a model's active version; with changes ({lever: value}), a new version with them changed, "
        "with a note and the backtest that chose it. Backtest a change first (ada_backtest).",
        Levers,
        settings,
    ),
    Tool(
        "ada_versions",
        "Ada versions",
        "Every version of a model: who made it, why, which is active.",
        Named,
        versions,
        True,
    ),
    Tool(
        "ada_activate",
        "Activate an Ada version",
        "Make another version active (a rollback, or forward again): at once, or by a job that brings its store up to "
        "date first.",
        Activate,
        activate,
    ),
)
