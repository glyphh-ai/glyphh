from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.limit_view import LimitView
from ...models.set_limit_kind import SetLimitKind
from ...models.switch import Switch
from ...types import UNSET, Response, Unset


def _get_kwargs(
    kind: SetLimitKind,
    *,
    body: Switch,
    team: None | Unset | UUID = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    json_team: str | Unset | None
    if isinstance(team, Unset):
        json_team = UNSET
    elif isinstance(team, UUID):
        json_team = str(team)
    else:
        json_team = team
    params["team"] = json_team

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/v1/org/limits/{kind}/switch".format(
            kind=quote(str(kind), safe=""),
        ),
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | LimitView | None:
    if response.status_code == 200:
        response_200 = LimitView.from_dict(response.json())

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
) -> Response[HTTPValidationError | LimitView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    kind: SetLimitKind,
    *,
    client: AuthenticatedClient | Client,
    body: Switch,
    team: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | LimitView]:
    """Set Limit

    Args:
        kind (SetLimitKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        body (Switch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | LimitView]
    """

    kwargs = _get_kwargs(
        kind=kind,
        body=body,
        team=team,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    kind: SetLimitKind,
    *,
    client: AuthenticatedClient | Client,
    body: Switch,
    team: None | Unset | UUID = UNSET,
) -> HTTPValidationError | LimitView | None:
    """Set Limit

    Args:
        kind (SetLimitKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        body (Switch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | LimitView
    """

    return sync_detailed(
        kind=kind,
        client=client,
        body=body,
        team=team,
    ).parsed


async def asyncio_detailed(
    kind: SetLimitKind,
    *,
    client: AuthenticatedClient | Client,
    body: Switch,
    team: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | LimitView]:
    """Set Limit

    Args:
        kind (SetLimitKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        body (Switch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | LimitView]
    """

    kwargs = _get_kwargs(
        kind=kind,
        body=body,
        team=team,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    kind: SetLimitKind,
    *,
    client: AuthenticatedClient | Client,
    body: Switch,
    team: None | Unset | UUID = UNSET,
) -> HTTPValidationError | LimitView | None:
    """Set Limit

    Args:
        kind (SetLimitKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        body (Switch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | LimitView
    """

    return (
        await asyncio_detailed(
            kind=kind,
            client=client,
            body=body,
            team=team,
        )
    ).parsed
