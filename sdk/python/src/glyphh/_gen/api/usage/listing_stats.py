from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.listing_stats import ListingStats
from ...types import UNSET, Response, Unset


def _get_kwargs(
    listing_id: UUID,
    *,
    days: int | Unset = 30,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["days"] = days

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/listings/{listing_id}/stats".format(
            listing_id=quote(str(listing_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListingStats | None:
    if response.status_code == 200:
        response_200 = ListingStats.from_dict(response.json())

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
) -> Response[HTTPValidationError | ListingStats]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    days: int | Unset = 30,
) -> Response[HTTPValidationError | ListingStats]:
    """Stats

    Args:
        listing_id (UUID):
        days (int | Unset):  Default: 30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListingStats]
    """

    kwargs = _get_kwargs(
        listing_id=listing_id,
        days=days,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    days: int | Unset = 30,
) -> HTTPValidationError | ListingStats | None:
    """Stats

    Args:
        listing_id (UUID):
        days (int | Unset):  Default: 30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListingStats
    """

    return sync_detailed(
        listing_id=listing_id,
        client=client,
        days=days,
    ).parsed


async def asyncio_detailed(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    days: int | Unset = 30,
) -> Response[HTTPValidationError | ListingStats]:
    """Stats

    Args:
        listing_id (UUID):
        days (int | Unset):  Default: 30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListingStats]
    """

    kwargs = _get_kwargs(
        listing_id=listing_id,
        days=days,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    days: int | Unset = 30,
) -> HTTPValidationError | ListingStats | None:
    """Stats

    Args:
        listing_id (UUID):
        days (int | Unset):  Default: 30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListingStats
    """

    return (
        await asyncio_detailed(
            listing_id=listing_id,
            client=client,
            days=days,
        )
    ).parsed
