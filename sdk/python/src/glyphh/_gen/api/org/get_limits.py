from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_limits_kind import GetLimitsKind
from ...models.http_validation_error import HTTPValidationError
from ...models.limit_view import LimitView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    kind: GetLimitsKind,
    *,
    team: None | Unset | UUID = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_team: str | Unset | None
    if isinstance(team, Unset):
        json_team = UNSET
    elif isinstance(team, UUID):
        json_team = str(team)
    else:
        json_team = team
    params["team"] = json_team

    params["q"] = q

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/limits/{kind}".format(
            kind=quote(str(kind), safe=""),
        ),
        "params": params,
    }

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
    kind: GetLimitsKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | LimitView]:
    """Get Limits

    Args:
        kind (GetLimitsKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | LimitView]
    """

    kwargs = _get_kwargs(
        kind=kind,
        team=team,
        q=q,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    kind: GetLimitsKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | LimitView | None:
    """Get Limits

    Args:
        kind (GetLimitsKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | LimitView
    """

    return sync_detailed(
        kind=kind,
        client=client,
        team=team,
        q=q,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    kind: GetLimitsKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | LimitView]:
    """Get Limits

    Args:
        kind (GetLimitsKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | LimitView]
    """

    kwargs = _get_kwargs(
        kind=kind,
        team=team,
        q=q,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    kind: GetLimitsKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | LimitView | None:
    """Get Limits

    Args:
        kind (GetLimitsKind):
        team (None | Unset | UUID): A team's list; the org's when left out
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

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
            team=team,
            q=q,
            page=page,
            size=size,
        )
    ).parsed
