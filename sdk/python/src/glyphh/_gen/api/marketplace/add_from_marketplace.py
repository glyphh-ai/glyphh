from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.added import Added
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    listing_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/marketplace/{listing_id}/add".format(
            listing_id=quote(str(listing_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Added | HTTPValidationError | None:
    if response.status_code == 201:
        response_201 = Added.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Added | HTTPValidationError]:
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
) -> Response[Added | HTTPValidationError]:
    """Add

     Copy the live version into my own; what it needs that I lack is listed, to connect or add.

    Args:
        listing_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Added | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        listing_id=listing_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Added | HTTPValidationError | None:
    """Add

     Copy the live version into my own; what it needs that I lack is listed, to connect or add.

    Args:
        listing_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Added | HTTPValidationError
    """

    return sync_detailed(
        listing_id=listing_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Added | HTTPValidationError]:
    """Add

     Copy the live version into my own; what it needs that I lack is listed, to connect or add.

    Args:
        listing_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Added | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        listing_id=listing_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    listing_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Added | HTTPValidationError | None:
    """Add

     Copy the live version into my own; what it needs that I lack is listed, to connect or add.

    Args:
        listing_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Added | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            listing_id=listing_id,
            client=client,
        )
    ).parsed
