from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.list_runs_scope import ListRunsScope
from ...models.run_list import RunList
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    page: int | Unset = 1,
    size: int | Unset = 25,
    scope: ListRunsScope | Unset = ListRunsScope.ME,
    super_power: None | Unset | UUID = UNSET,
    schedule: None | Unset | UUID = UNSET,
    machine: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page"] = page

    params["size"] = size

    json_scope: str | Unset = UNSET
    if not isinstance(scope, Unset):
        json_scope = scope.value

    params["scope"] = json_scope

    json_super_power: str | Unset | None
    if isinstance(super_power, Unset):
        json_super_power = UNSET
    elif isinstance(super_power, UUID):
        json_super_power = str(super_power)
    else:
        json_super_power = super_power
    params["super_power"] = json_super_power

    json_schedule: str | Unset | None
    if isinstance(schedule, Unset):
        json_schedule = UNSET
    elif isinstance(schedule, UUID):
        json_schedule = str(schedule)
    else:
        json_schedule = schedule
    params["schedule"] = json_schedule

    json_machine: str | Unset | None
    if isinstance(machine, Unset):
        json_machine = UNSET
    elif isinstance(machine, UUID):
        json_machine = str(machine)
    else:
        json_machine = machine
    params["machine"] = json_machine

    json_status: str | Unset | None
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/runs",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | RunList | None:
    if response.status_code == 200:
        response_200 = RunList.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | RunList]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    scope: ListRunsScope | Unset = ListRunsScope.ME,
    super_power: None | Unset | UUID = UNSET,
    schedule: None | Unset | UUID = UNSET,
    machine: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | RunList]:
    """List Runs

     Every run, newest first: by the clock, by hand or by an agent, with its status and what it cost.

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        scope (ListRunsScope | Unset):  Default: ListRunsScope.ME.
        super_power (None | Unset | UUID):
        schedule (None | Unset | UUID):
        machine (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunList]
    """

    kwargs = _get_kwargs(
        page=page,
        size=size,
        scope=scope,
        super_power=super_power,
        schedule=schedule,
        machine=machine,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    scope: ListRunsScope | Unset = ListRunsScope.ME,
    super_power: None | Unset | UUID = UNSET,
    schedule: None | Unset | UUID = UNSET,
    machine: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> HTTPValidationError | RunList | None:
    """List Runs

     Every run, newest first: by the clock, by hand or by an agent, with its status and what it cost.

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        scope (ListRunsScope | Unset):  Default: ListRunsScope.ME.
        super_power (None | Unset | UUID):
        schedule (None | Unset | UUID):
        machine (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunList
    """

    return sync_detailed(
        client=client,
        page=page,
        size=size,
        scope=scope,
        super_power=super_power,
        schedule=schedule,
        machine=machine,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    scope: ListRunsScope | Unset = ListRunsScope.ME,
    super_power: None | Unset | UUID = UNSET,
    schedule: None | Unset | UUID = UNSET,
    machine: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | RunList]:
    """List Runs

     Every run, newest first: by the clock, by hand or by an agent, with its status and what it cost.

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        scope (ListRunsScope | Unset):  Default: ListRunsScope.ME.
        super_power (None | Unset | UUID):
        schedule (None | Unset | UUID):
        machine (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunList]
    """

    kwargs = _get_kwargs(
        page=page,
        size=size,
        scope=scope,
        super_power=super_power,
        schedule=schedule,
        machine=machine,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    scope: ListRunsScope | Unset = ListRunsScope.ME,
    super_power: None | Unset | UUID = UNSET,
    schedule: None | Unset | UUID = UNSET,
    machine: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> HTTPValidationError | RunList | None:
    """List Runs

     Every run, newest first: by the clock, by hand or by an agent, with its status and what it cost.

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        scope (ListRunsScope | Unset):  Default: ListRunsScope.ME.
        super_power (None | Unset | UUID):
        schedule (None | Unset | UUID):
        machine (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunList
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
            size=size,
            scope=scope,
            super_power=super_power,
            schedule=schedule,
            machine=machine,
            status=status,
        )
    ).parsed
