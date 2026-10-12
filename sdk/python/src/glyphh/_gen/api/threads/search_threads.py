from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.found import Found
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response


def _get_kwargs(
    *,
    q: str,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/threads/search",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Found | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = Found.from_dict(response.json())

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
) -> Response[Found | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str,
) -> Response[Found | HTTPValidationError]:
    """Search

     My threads found by their goal, and by what was said on every one of my machines that is online.

    Args:
        q (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Found | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str,
) -> Found | HTTPValidationError | None:
    """Search

     My threads found by their goal, and by what was said on every one of my machines that is online.

    Args:
        q (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Found | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        q=q,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str,
) -> Response[Found | HTTPValidationError]:
    """Search

     My threads found by their goal, and by what was said on every one of my machines that is online.

    Args:
        q (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Found | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        q=q,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str,
) -> Found | HTTPValidationError | None:
    """Search

     My threads found by their goal, and by what was said on every one of my machines that is online.

    Args:
        q (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Found | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
        )
    ).parsed
