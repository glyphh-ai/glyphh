import datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.usage_page import UsagePage
from ...models.usage_page_scope import UsagePageScope
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    scope: UsagePageScope | Unset = UsagePageScope.ME,
    since: datetime.date | None | Unset = UNSET,
    until: datetime.date | None | Unset = UNSET,
    users: list[UUID] | None | Unset = UNSET,
    teams: list[UUID] | None | Unset = UNSET,
    super_power: None | Unset | UUID = UNSET,
    power: None | Unset | UUID = UNSET,
    service: None | str | Unset = UNSET,
    machine: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_scope: str | Unset = UNSET
    if not isinstance(scope, Unset):
        json_scope = scope.value

    params["scope"] = json_scope

    json_since: str | Unset | None
    if isinstance(since, Unset):
        json_since = UNSET
    elif isinstance(since, datetime.date):
        json_since = since.isoformat()
    else:
        json_since = since
    params["since"] = json_since

    json_until: str | Unset | None
    if isinstance(until, Unset):
        json_until = UNSET
    elif isinstance(until, datetime.date):
        json_until = until.isoformat()
    else:
        json_until = until
    params["until"] = json_until

    json_users: list[str] | Unset | None
    if isinstance(users, Unset):
        json_users = UNSET
    elif isinstance(users, list):
        json_users = []
        for users_type_0_item_data in users:
            users_type_0_item = str(users_type_0_item_data)
            json_users.append(users_type_0_item)

    else:
        json_users = users
    params["users"] = json_users

    json_teams: list[str] | Unset | None
    if isinstance(teams, Unset):
        json_teams = UNSET
    elif isinstance(teams, list):
        json_teams = []
        for teams_type_0_item_data in teams:
            teams_type_0_item = str(teams_type_0_item_data)
            json_teams.append(teams_type_0_item)

    else:
        json_teams = teams
    params["teams"] = json_teams

    json_super_power: str | Unset | None
    if isinstance(super_power, Unset):
        json_super_power = UNSET
    elif isinstance(super_power, UUID):
        json_super_power = str(super_power)
    else:
        json_super_power = super_power
    params["super_power"] = json_super_power

    json_power: str | Unset | None
    if isinstance(power, Unset):
        json_power = UNSET
    elif isinstance(power, UUID):
        json_power = str(power)
    else:
        json_power = power
    params["power"] = json_power

    json_service: str | Unset | None
    if isinstance(service, Unset):
        json_service = UNSET
    else:
        json_service = service
    params["service"] = json_service

    json_machine: str | Unset | None
    if isinstance(machine, Unset):
        json_machine = UNSET
    elif isinstance(machine, UUID):
        json_machine = str(machine)
    else:
        json_machine = machine
    params["machine"] = json_machine

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/usage",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | UsagePage | None:
    if response.status_code == 200:
        response_200 = UsagePage.from_dict(response.json())

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
) -> Response[HTTPValidationError | UsagePage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: UsagePageScope | Unset = UsagePageScope.ME,
    since: datetime.date | None | Unset = UNSET,
    until: datetime.date | None | Unset = UNSET,
    users: list[UUID] | None | Unset = UNSET,
    teams: list[UUID] | None | Unset = UNSET,
    super_power: None | Unset | UUID = UNSET,
    power: None | Unset | UUID = UNSET,
    service: None | str | Unset = UNSET,
    machine: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | UsagePage]:
    """Usage Page

    Args:
        scope (UsagePageScope | Unset):  Default: UsagePageScope.ME.
        since (datetime.date | None | Unset):
        until (datetime.date | None | Unset):
        users (list[UUID] | None | Unset): People, for an org admin
        teams (list[UUID] | None | Unset): Whole teams, for an org admin
        super_power (None | Unset | UUID):
        power (None | Unset | UUID):
        service (None | str | Unset):
        machine (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UsagePage]
    """

    kwargs = _get_kwargs(
        scope=scope,
        since=since,
        until=until,
        users=users,
        teams=teams,
        super_power=super_power,
        power=power,
        service=service,
        machine=machine,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    scope: UsagePageScope | Unset = UsagePageScope.ME,
    since: datetime.date | None | Unset = UNSET,
    until: datetime.date | None | Unset = UNSET,
    users: list[UUID] | None | Unset = UNSET,
    teams: list[UUID] | None | Unset = UNSET,
    super_power: None | Unset | UUID = UNSET,
    power: None | Unset | UUID = UNSET,
    service: None | str | Unset = UNSET,
    machine: None | Unset | UUID = UNSET,
) -> HTTPValidationError | UsagePage | None:
    """Usage Page

    Args:
        scope (UsagePageScope | Unset):  Default: UsagePageScope.ME.
        since (datetime.date | None | Unset):
        until (datetime.date | None | Unset):
        users (list[UUID] | None | Unset): People, for an org admin
        teams (list[UUID] | None | Unset): Whole teams, for an org admin
        super_power (None | Unset | UUID):
        power (None | Unset | UUID):
        service (None | str | Unset):
        machine (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UsagePage
    """

    return sync_detailed(
        client=client,
        scope=scope,
        since=since,
        until=until,
        users=users,
        teams=teams,
        super_power=super_power,
        power=power,
        service=service,
        machine=machine,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: UsagePageScope | Unset = UsagePageScope.ME,
    since: datetime.date | None | Unset = UNSET,
    until: datetime.date | None | Unset = UNSET,
    users: list[UUID] | None | Unset = UNSET,
    teams: list[UUID] | None | Unset = UNSET,
    super_power: None | Unset | UUID = UNSET,
    power: None | Unset | UUID = UNSET,
    service: None | str | Unset = UNSET,
    machine: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | UsagePage]:
    """Usage Page

    Args:
        scope (UsagePageScope | Unset):  Default: UsagePageScope.ME.
        since (datetime.date | None | Unset):
        until (datetime.date | None | Unset):
        users (list[UUID] | None | Unset): People, for an org admin
        teams (list[UUID] | None | Unset): Whole teams, for an org admin
        super_power (None | Unset | UUID):
        power (None | Unset | UUID):
        service (None | str | Unset):
        machine (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UsagePage]
    """

    kwargs = _get_kwargs(
        scope=scope,
        since=since,
        until=until,
        users=users,
        teams=teams,
        super_power=super_power,
        power=power,
        service=service,
        machine=machine,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    scope: UsagePageScope | Unset = UsagePageScope.ME,
    since: datetime.date | None | Unset = UNSET,
    until: datetime.date | None | Unset = UNSET,
    users: list[UUID] | None | Unset = UNSET,
    teams: list[UUID] | None | Unset = UNSET,
    super_power: None | Unset | UUID = UNSET,
    power: None | Unset | UUID = UNSET,
    service: None | str | Unset = UNSET,
    machine: None | Unset | UUID = UNSET,
) -> HTTPValidationError | UsagePage | None:
    """Usage Page

    Args:
        scope (UsagePageScope | Unset):  Default: UsagePageScope.ME.
        since (datetime.date | None | Unset):
        until (datetime.date | None | Unset):
        users (list[UUID] | None | Unset): People, for an org admin
        teams (list[UUID] | None | Unset): Whole teams, for an org admin
        super_power (None | Unset | UUID):
        power (None | Unset | UUID):
        service (None | str | Unset):
        machine (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UsagePage
    """

    return (
        await asyncio_detailed(
            client=client,
            scope=scope,
            since=since,
            until=until,
            users=users,
            teams=teams,
            super_power=super_power,
            power=power,
            service=service,
            machine=machine,
        )
    ).parsed
