from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.installed_page import InstalledPage
from ...models.list_installed_super_powers_status_type_0 import ListInstalledSuperPowersStatusType0
from ...types import UNSET, Response, Unset


def _get_kwargs(
    machine_id: UUID,
    *,
    q: str | Unset = "",
    status: ListInstalledSuperPowersStatusType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_status: str | Unset | None
    if isinstance(status, Unset):
        json_status = UNSET
    elif isinstance(status, ListInstalledSuperPowersStatusType0):
        json_status = status.value
    else:
        json_status = status
    params["status"] = json_status

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/machines/{machine_id}/super-powers".format(
            machine_id=quote(str(machine_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | InstalledPage | None:
    if response.status_code == 200:
        response_200 = InstalledPage.from_dict(response.json())

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
) -> Response[HTTPValidationError | InstalledPage]:
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
    status: ListInstalledSuperPowersStatusType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> Response[HTTPValidationError | InstalledPage]:
    """Super Powers

     Every super power on one of my machines, searched and filtered, with how many of each status.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        status (ListInstalledSuperPowersStatusType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InstalledPage]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        q=q,
        status=status,
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
    status: ListInstalledSuperPowersStatusType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> HTTPValidationError | InstalledPage | None:
    """Super Powers

     Every super power on one of my machines, searched and filtered, with how many of each status.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        status (ListInstalledSuperPowersStatusType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InstalledPage
    """

    return sync_detailed(
        machine_id=machine_id,
        client=client,
        q=q,
        status=status,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: ListInstalledSuperPowersStatusType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> Response[HTTPValidationError | InstalledPage]:
    """Super Powers

     Every super power on one of my machines, searched and filtered, with how many of each status.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        status (ListInstalledSuperPowersStatusType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InstalledPage]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        q=q,
        status=status,
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
    status: ListInstalledSuperPowersStatusType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> HTTPValidationError | InstalledPage | None:
    """Super Powers

     Every super power on one of my machines, searched and filtered, with how many of each status.

    Args:
        machine_id (UUID):
        q (str | Unset):  Default: ''.
        status (ListInstalledSuperPowersStatusType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InstalledPage
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            client=client,
            q=q,
            status=status,
            page=page,
            size=size,
        )
    ).parsed
