from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.list_super_powers_status import ListSuperPowersStatus
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = "",
    status: ListSuperPowersStatus | Unset = ListSuperPowersStatus.ALL,
    machine: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 12,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_status: str | Unset = UNSET
    if not isinstance(status, Unset):
        json_status = status.value

    params["status"] = json_status

    json_machine: str | Unset | None
    if isinstance(machine, Unset):
        json_machine = UNSET
    elif isinstance(machine, UUID):
        json_machine = str(machine)
    else:
        json_machine = machine
    params["machine"] = json_machine

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/super-powers",
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | None:
    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError]:
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
    status: ListSuperPowersStatus | Unset = ListSuperPowersStatus.ALL,
    machine: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 12,
) -> Response[HTTPValidationError]:
    """List Super Powers

     Every super power I have, across my machines, newest activity first, with how many of each status.

    Args:
        q (str | Unset):  Default: ''.
        status (ListSuperPowersStatus | Unset):  Default: ListSuperPowersStatus.ALL.
        machine (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 12.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        machine=machine,
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
    status: ListSuperPowersStatus | Unset = ListSuperPowersStatus.ALL,
    machine: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 12,
) -> HTTPValidationError | None:
    """List Super Powers

     Every super power I have, across my machines, newest activity first, with how many of each status.

    Args:
        q (str | Unset):  Default: ''.
        status (ListSuperPowersStatus | Unset):  Default: ListSuperPowersStatus.ALL.
        machine (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 12.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError
    """

    return sync_detailed(
        client=client,
        q=q,
        status=status,
        machine=machine,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: ListSuperPowersStatus | Unset = ListSuperPowersStatus.ALL,
    machine: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 12,
) -> Response[HTTPValidationError]:
    """List Super Powers

     Every super power I have, across my machines, newest activity first, with how many of each status.

    Args:
        q (str | Unset):  Default: ''.
        status (ListSuperPowersStatus | Unset):  Default: ListSuperPowersStatus.ALL.
        machine (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 12.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        machine=machine,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: ListSuperPowersStatus | Unset = ListSuperPowersStatus.ALL,
    machine: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 12,
) -> HTTPValidationError | None:
    """List Super Powers

     Every super power I have, across my machines, newest activity first, with how many of each status.

    Args:
        q (str | Unset):  Default: ''.
        status (ListSuperPowersStatus | Unset):  Default: ListSuperPowersStatus.ALL.
        machine (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 12.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            status=status,
            machine=machine,
            page=page,
            size=size,
        )
    ).parsed
