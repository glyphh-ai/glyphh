from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.waiting import Waiting
from ...types import Response


def _get_kwargs(
    user_code: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/machine-sign-ins/{user_code}".format(
            user_code=quote(str(user_code), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Waiting | None:
    if response.status_code == 200:
        response_200 = Waiting.from_dict(response.json())

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
) -> Response[HTTPValidationError | Waiting]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    user_code: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | Waiting]:
    """Shown

     The machine waiting with this code: its name, platform, host and SSH fingerprint, to check by eye.

    Args:
        user_code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Waiting]
    """

    kwargs = _get_kwargs(
        user_code=user_code,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_code: str,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | Waiting | None:
    """Shown

     The machine waiting with this code: its name, platform, host and SSH fingerprint, to check by eye.

    Args:
        user_code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Waiting
    """

    return sync_detailed(
        user_code=user_code,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_code: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | Waiting]:
    """Shown

     The machine waiting with this code: its name, platform, host and SSH fingerprint, to check by eye.

    Args:
        user_code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Waiting]
    """

    kwargs = _get_kwargs(
        user_code=user_code,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_code: str,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | Waiting | None:
    """Shown

     The machine waiting with this code: its name, platform, host and SSH fingerprint, to check by eye.

    Args:
        user_code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Waiting
    """

    return (
        await asyncio_detailed(
            user_code=user_code,
            client=client,
        )
    ).parsed
