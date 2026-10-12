from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.thread_page import ThreadPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    machine_id: UUID,
    *,
    q: str | Unset = "",
    super_power: None | Unset | UUID = UNSET,
    archived: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_super_power: str | Unset | None
    if isinstance(super_power, Unset):
        json_super_power = UNSET
    elif isinstance(super_power, UUID):
        json_super_power = str(super_power)
    else:
        json_super_power = super_power
    params["super_power"] = json_super_power

    params["archived"] = archived

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/machines/{machine_id}/threads".format(
            machine_id=quote(str(machine_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ThreadPage | None:
    if response.status_code == 200:
        response_200 = ThreadPage.from_dict(response.json())

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
) -> Response[HTTPValidationError | ThreadPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    super_power: None | Unset | UUID = UNSET,
    archived: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | ThreadPage]:
    """Threads

     A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or
    not.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        super_power (None | Unset | UUID):
        archived (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ThreadPage]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        q=q,
        super_power=super_power,
        archived=archived,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    super_power: None | Unset | UUID = UNSET,
    archived: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | ThreadPage | None:
    """Threads

     A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or
    not.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        super_power (None | Unset | UUID):
        archived (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ThreadPage
    """

    return sync_detailed(
        machine_id=machine_id,
        client=client,
        q=q,
        super_power=super_power,
        archived=archived,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    super_power: None | Unset | UUID = UNSET,
    archived: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | ThreadPage]:
    """Threads

     A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or
    not.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        super_power (None | Unset | UUID):
        archived (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ThreadPage]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        q=q,
        super_power=super_power,
        archived=archived,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    super_power: None | Unset | UUID = UNSET,
    archived: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | ThreadPage | None:
    """Threads

     A machine's threads (Recents): pinned first, then the newest; by goal, by a super power, archived or
    not.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        super_power (None | Unset | UUID):
        archived (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ThreadPage
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            client=client,
            q=q,
            super_power=super_power,
            archived=archived,
            page=page,
            size=size,
        )
    ).parsed
