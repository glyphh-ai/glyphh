from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.hosted_view import HostedView
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    hosted_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/hosted-machines/{hosted_id}".format(
            hosted_id=quote(str(hosted_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | HostedView | None:
    if response.status_code == 200:
        response_200 = HostedView.from_dict(response.json())

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
) -> Response[HTTPValidationError | HostedView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    hosted_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostedView]:
    """One

     One of my machines at a host, with what the host says of it now.

    Args:
        hosted_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostedView]
    """

    kwargs = _get_kwargs(
        hosted_id=hosted_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    hosted_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostedView | None:
    """One

     One of my machines at a host, with what the host says of it now.

    Args:
        hosted_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostedView
    """

    return sync_detailed(
        hosted_id=hosted_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    hosted_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostedView]:
    """One

     One of my machines at a host, with what the host says of it now.

    Args:
        hosted_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostedView]
    """

    kwargs = _get_kwargs(
        hosted_id=hosted_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    hosted_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostedView | None:
    """One

     One of my machines at a host, with what the host says of it now.

    Args:
        hosted_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostedView
    """

    return (
        await asyncio_detailed(
            hosted_id=hosted_id,
            client=client,
        )
    ).parsed
