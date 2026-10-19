"""The connector's machine tools: the person's hosted machines listed, one made (named, of a size) and started, one
restarted, and one deleted with its name typed to confirm. start_runtime and stop_runtime (mcp/tools/runtime.py) take
a machine's id too. With hosting off (GLYPHH_HOSTING) making, starting and restarting are refused, E_UNAVAILABLE
`hosting_off`; stopping and deleting still work."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.models.rrotor import SIZES_SAID, SizeName
from glyphh_server.ops import machines
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.machines import Machine

OFF: str = "Glyphh's managed cloud is off: run rrotor yourself and register it with register_self_runtime."


class NewMachine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What it is called: 'research'")
    size: SizeName = Field(description=SIZES_SAID)


class MachineId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(description="The machine's id (runtimes lists them)")


class DeleteMachine(MachineId):
    confirm: str = Field(description="The machine's name, exactly: what the person typed to confirm")


def line(m: Machine) -> str:
    hours = f"{m.month_seconds / 3600:.1f} h this month"
    return f"{m.name} ({m.size}) is {m.state} at {m.address}, {hours}, id {m.id}"


async def list_machines(ctx: Context, _: NoArgs) -> Done:
    found = await machines.list_machines(ctx.conn, ctx.who, ctx.settings.fly_public_domain)
    none = "You have no hosted machines yet: create_runtime makes one." if ctx.settings.hosting else OFF
    text = "\n".join(line(m) for m in found) or none
    return Done(text, {"runtimes": [dump(m) for m in found]})


async def create(ctx: Context, args: NewMachine) -> Done:
    made = await machines.create(ctx.conn, Fly(ctx.http, ctx.settings), ctx.who, args.name.strip(), args.size)
    return Done(line(made) + ". Add it to Claude as a connector: its /mcp, with a runtime key.", dump(made))


async def restart(ctx: Context, args: MachineId) -> Done:
    done = await machines.restart(ctx.conn, Fly(ctx.http, ctx.settings), ctx.who, args.id)
    return Done(line(done) + ".", dump(done))


async def delete(ctx: Context, args: DeleteMachine) -> Done:
    gone = await machines.machine(ctx.conn, ctx.who, args.id, ctx.settings.fly_public_domain)
    await machines.destroy(ctx.conn, Fly(ctx.http, ctx.settings), ctx.who, args.id, args.confirm)
    return Done(f"{gone.name} is deleted: its machine and its disk are gone.", {"id": str(gone.id), "deleted": True})


TOOLS: tuple[Tool, ...] = (
    Tool(
        "runtimes",
        "Machines",
        "Your hosted machines: each one's name, size, state, address and hours this month.",
        NoArgs,
        list_machines,
        True,
    ),
    Tool(
        "create_runtime",
        "Create a machine",
        "Make a hosted machine of a size on Glyphh's managed cloud and start it (up to your plan's machines). While "
        "the managed cloud is off, refused (hosting_off): register a self-hosted runtime instead.",
        NewMachine,
        create,
    ),
    Tool(
        "restart_runtime",
        "Restart a machine",
        "Restart one of your hosted machines; refused (hosting_off) while the managed cloud is off.",
        MachineId,
        restart,
    ),
    Tool(
        "delete_runtime",
        "Delete a machine",
        "Delete a hosted machine: its machine and its disk, every model, version, precedent and file on it. Fly keeps"
        " daily snapshots for 5 days; Glyphh keeps no other backup. Ask the person to type its name, and pass that as"
        " confirm.",
        DeleteMachine,
        delete,
    ),
)
