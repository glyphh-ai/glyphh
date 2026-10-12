from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.keys_page import KeysPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    owner: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_owner: str | Unset | None
    if isinstance(owner, Unset):
        json_owner = UNSET
    elif isinstance(owner, UUID):
        json_owner = str(owner)
    else:
        json_owner = owner
    params["owner"] = json_owner

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/api-keys",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | KeysPage | None:
    if response.status_code == 200:
        response_200 = KeysPage.from_dict(response.json())

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
) -> Response[HTTPValidationError | KeysPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    owner: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | KeysPage]:
    """List Org Keys

    Args:
        owner (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KeysPage]
    """

    kwargs = _get_kwargs(
        owner=owner,
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
    owner: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | KeysPage | None:
    """List Org Keys

    Args:
        owner (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KeysPage
    """

    return sync_detailed(
        client=client,
        owner=owner,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    owner: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | KeysPage]:
    """List Org Keys

    Args:
        owner (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KeysPage]
    """

    kwargs = _get_kwargs(
        owner=owner,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    owner: None | Unset | UUID = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | KeysPage | None:
    """List Org Keys

    Args:
        owner (None | Unset | UUID):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KeysPage
    """

    return (
        await asyncio_detailed(
            client=client,
            owner=owner,
            page=page,
            size=size,
        )
    ).parsed
