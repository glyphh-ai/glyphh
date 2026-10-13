"""One-click hosting on my own Fly account, as calls: the account's deploy token (checked with Fly, kept encrypted,
never answered back), deploying a machine there that signs itself in, and keeping it: its state as the Deploy page
shows it, waking it, moving it to a new image, destroying it; and at the other hosts, launching one (the code with
AWS's quick-create link, Deploy to Azure, the first boot to paste, or the line for a VPS), the first-boot script and
the templates."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.machines import (
    deploy_machine,
    destroy_hosted_machine,
    first_boot_script,
    get_host_account,
    get_hosted_machine,
    host_template,
    launch_host,
    list_hosted_machines,
    remove_host_account,
    save_host_account,
    start_hosted_machine,
    update_hosted_machine,
)
from glyphh._gen.models import AccountIn, DeployIn, HostTemplateHost, ImageIn, LaunchHostHost, LaunchIn
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]


def _id(hosted_id: str) -> dict[str, Any]:
    return {"hosted_id": UUID(hosted_id)}


HOSTING_SPECS: dict[str, Callable[..., Spec]] = {
    "save_account": lambda token, account="personal", host="fly": (
        _call(save_host_account),
        {"host": host, "body": AccountIn(token=token, account=account)},
    ),
    "account": lambda host="fly": (_call(get_host_account), {"host": host}),
    "remove_account": lambda host="fly": (_call(remove_host_account), {"host": host}),
    "deploy": lambda name, region="iad": (_call(deploy_machine), {"body": DeployIn(name=name, region=region)}),
    "list": lambda: (_call(list_hosted_machines), {}),
    "get": lambda hosted_id: (_call(get_hosted_machine), _id(hosted_id)),
    "start": lambda hosted_id: (_call(start_hosted_machine), _id(hosted_id)),
    "update": lambda hosted_id, image=None: (
        _call(update_hosted_machine),
        {**_id(hosted_id), "body": ImageIn(image=image)},
    ),
    "destroy": lambda hosted_id: (_call(destroy_hosted_machine), _id(hosted_id)),
    "launch": lambda host, name=None: (
        _call(launch_host),
        {"host": LaunchHostHost(host), "body": LaunchIn(name=name if name else UNSET)},
    ),
    "first_boot_script": lambda: (_call(first_boot_script), {}),
    "template": lambda host: (_call(host_template), {"host": HostTemplateHost(host)}),
}
