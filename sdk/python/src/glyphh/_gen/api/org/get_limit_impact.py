from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_limit_impact_kind import GetLimitImpactKind
from ...models.http_validation_error import HTTPValidationError
from ...models.impact import Impact
from ...types import UNSET, Response, Unset


def _get_kwargs(
    kind: GetLimitImpactKind,
    *,
    team: None | Unset | UUID = UNSET,
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

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/limits/{kind}/impact".format(
            kind=quote(str(kind), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Impact | None:
    if response.status_code == 200:
        response_200 = Impact.from_dict(response.json())

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
) -> Response[HTTPValidationError | Impact]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    kind: GetLimitImpactKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | Impact]:
    """Get Limit Impact

    Args:
        kind (GetLimitImpactKind):
        team (None | Unset | UUID): A team's list; the org's when left out

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Impact]
    """

    kwargs = _get_kwargs(
        kind=kind,
        team=team,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    kind: GetLimitImpactKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
) -> HTTPValidationError | Impact | None:
    """Get Limit Impact

    Args:
        kind (GetLimitImpactKind):
        team (None | Unset | UUID): A team's list; the org's when left out

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Impact
    """

    return sync_detailed(
        kind=kind,
        client=client,
        team=team,
    ).parsed


async def asyncio_detailed(
    kind: GetLimitImpactKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | Impact]:
    """Get Limit Impact

    Args:
        kind (GetLimitImpactKind):
        team (None | Unset | UUID): A team's list; the org's when left out

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Impact]
    """

    kwargs = _get_kwargs(
        kind=kind,
        team=team,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    kind: GetLimitImpactKind,
    *,
    client: AuthenticatedClient | Client,
    team: None | Unset | UUID = UNSET,
) -> HTTPValidationError | Impact | None:
    """Get Limit Impact

    Args:
        kind (GetLimitImpactKind):
        team (None | Unset | UUID): A team's list; the org's when left out

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Impact
    """

    return (
        await asyncio_detailed(
            kind=kind,
            client=client,
            team=team,
        )
    ).parsed
