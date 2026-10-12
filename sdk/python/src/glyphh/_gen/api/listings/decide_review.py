from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.listing_view import ListingView
from ...models.review_decision import ReviewDecision
from ...types import Response


def _get_kwargs(
    listing_version_id: UUID,
    *,
    body: ReviewDecision,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/reviews/{listing_version_id}".format(
            listing_version_id=quote(str(listing_version_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListingView | None:
    if response.status_code == 200:
        response_200 = ListingView.from_dict(response.json())

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
) -> Response[HTTPValidationError | ListingView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    listing_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> Response[HTTPValidationError | ListingView]:
    """Decide

     Approve, ask for changes (with notes) or reject (with why).

    Args:
        listing_version_id (UUID):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListingView]
    """

    kwargs = _get_kwargs(
        listing_version_id=listing_version_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    listing_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> HTTPValidationError | ListingView | None:
    """Decide

     Approve, ask for changes (with notes) or reject (with why).

    Args:
        listing_version_id (UUID):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListingView
    """

    return sync_detailed(
        listing_version_id=listing_version_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    listing_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> Response[HTTPValidationError | ListingView]:
    """Decide

     Approve, ask for changes (with notes) or reject (with why).

    Args:
        listing_version_id (UUID):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListingView]
    """

    kwargs = _get_kwargs(
        listing_version_id=listing_version_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    listing_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> HTTPValidationError | ListingView | None:
    """Decide

     Approve, ask for changes (with notes) or reject (with why).

    Args:
        listing_version_id (UUID):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListingView
    """

    return (
        await asyncio_detailed(
            listing_version_id=listing_version_id,
            client=client,
            body=body,
        )
    ).parsed
