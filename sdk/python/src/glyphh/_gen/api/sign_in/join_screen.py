from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.join_screen import JoinScreen
from ...types import UNSET, Response


def _get_kwargs(
    *,
    invite: str,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["invite"] = invite

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/auth/join",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | JoinScreen | None:
    if response.status_code == 200:
        response_200 = JoinScreen.from_dict(response.json())

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
) -> Response[HTTPValidationError | JoinScreen]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    invite: str,
) -> Response[HTTPValidationError | JoinScreen]:
    """Join Screen

    Args:
        invite (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JoinScreen]
    """

    kwargs = _get_kwargs(
        invite=invite,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    invite: str,
) -> HTTPValidationError | JoinScreen | None:
    """Join Screen

    Args:
        invite (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JoinScreen
    """

    return sync_detailed(
        client=client,
        invite=invite,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    invite: str,
) -> Response[HTTPValidationError | JoinScreen]:
    """Join Screen

    Args:
        invite (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JoinScreen]
    """

    kwargs = _get_kwargs(
        invite=invite,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    invite: str,
) -> HTTPValidationError | JoinScreen | None:
    """Join Screen

    Args:
        invite (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JoinScreen
    """

    return (
        await asyncio_detailed(
            client=client,
            invite=invite,
        )
    ).parsed
