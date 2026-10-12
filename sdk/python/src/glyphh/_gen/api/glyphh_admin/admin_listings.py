from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_listing_page import AdminListingPage
from ...models.admin_listings_state_type_0 import AdminListingsStateType0
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = "",
    state: AdminListingsStateType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_state: str | Unset | None
    if isinstance(state, Unset):
        json_state = UNSET
    elif isinstance(state, AdminListingsStateType0):
        json_state = state.value
    else:
        json_state = state
    params["state"] = json_state

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/listings",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AdminListingPage | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AdminListingPage.from_dict(response.json())

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
) -> Response[AdminListingPage | HTTPValidationError]:
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
    state: AdminListingsStateType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[AdminListingPage | HTTPValidationError]:
    """Admin Listings

    Args:
        q (str | Unset):  Default: ''.
        state (AdminListingsStateType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminListingPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
        state=state,
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
    state: AdminListingsStateType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> AdminListingPage | HTTPValidationError | None:
    """Admin Listings

    Args:
        q (str | Unset):  Default: ''.
        state (AdminListingsStateType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminListingPage | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        q=q,
        state=state,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    state: AdminListingsStateType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[AdminListingPage | HTTPValidationError]:
    """Admin Listings

    Args:
        q (str | Unset):  Default: ''.
        state (AdminListingsStateType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminListingPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
        state=state,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    state: AdminListingsStateType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> AdminListingPage | HTTPValidationError | None:
    """Admin Listings

    Args:
        q (str | Unset):  Default: ''.
        state (AdminListingsStateType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminListingPage | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            state=state,
            page=page,
            size=size,
        )
    ).parsed
