from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.list_people_role_type_0 import ListPeopleRoleType0
from ...models.people_page import PeoplePage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = "",
    role: ListPeopleRoleType0 | None | Unset = UNSET,
    team: list[str] | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_role: str | Unset | None
    if isinstance(role, Unset):
        json_role = UNSET
    elif isinstance(role, ListPeopleRoleType0):
        json_role = role.value
    else:
        json_role = role
    params["role"] = json_role

    json_team: list[str] | Unset | None
    if isinstance(team, Unset):
        json_team = UNSET
    elif isinstance(team, list):
        json_team = team

    else:
        json_team = team
    params["team"] = json_team

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/people",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | PeoplePage | None:
    if response.status_code == 200:
        response_200 = PeoplePage.from_dict(response.json())

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
) -> Response[HTTPValidationError | PeoplePage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    role: ListPeopleRoleType0 | None | Unset = UNSET,
    team: list[str] | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | PeoplePage]:
    """List People

    Args:
        q (str | Unset):  Default: ''.
        role (ListPeopleRoleType0 | None | Unset):
        team (list[str] | None | Unset): Team ids, or none for people in no team
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PeoplePage]
    """

    kwargs = _get_kwargs(
        q=q,
        role=role,
        team=team,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    role: ListPeopleRoleType0 | None | Unset = UNSET,
    team: list[str] | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | PeoplePage | None:
    """List People

    Args:
        q (str | Unset):  Default: ''.
        role (ListPeopleRoleType0 | None | Unset):
        team (list[str] | None | Unset): Team ids, or none for people in no team
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PeoplePage
    """

    return sync_detailed(
        client=client,
        q=q,
        role=role,
        team=team,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    role: ListPeopleRoleType0 | None | Unset = UNSET,
    team: list[str] | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | PeoplePage]:
    """List People

    Args:
        q (str | Unset):  Default: ''.
        role (ListPeopleRoleType0 | None | Unset):
        team (list[str] | None | Unset): Team ids, or none for people in no team
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PeoplePage]
    """

    kwargs = _get_kwargs(
        q=q,
        role=role,
        team=team,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    role: ListPeopleRoleType0 | None | Unset = UNSET,
    team: list[str] | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | PeoplePage | None:
    """List People

    Args:
        q (str | Unset):  Default: ''.
        role (ListPeopleRoleType0 | None | Unset):
        team (list[str] | None | Unset): Team ids, or none for people in no team
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PeoplePage
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            role=role,
            team=team,
            page=page,
            size=size,
        )
    ).parsed
