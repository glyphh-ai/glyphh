from http import HTTPStatus
from typing import Any, Literal
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.host_account_view import HostAccountView
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    host: Literal["fly"],
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/hosts/{host}/account".format(
            host=quote(str(host), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | HostAccountView | None:
    if response.status_code == 200:
        response_200 = HostAccountView.from_dict(response.json())

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
) -> Response[HTTPValidationError | HostAccountView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostAccountView]:
    """Shown

     Which account at the host I deploy to: its org and the token's last four characters.

    Args:
        host (Literal['fly']):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostAccountView]
    """

    kwargs = _get_kwargs(
        host=host,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostAccountView | None:
    """Shown

     Which account at the host I deploy to: its org and the token's last four characters.

    Args:
        host (Literal['fly']):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostAccountView
    """

    return sync_detailed(
        host=host,
        client=client,
    ).parsed


async def asyncio_detailed(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostAccountView]:
    """Shown

     Which account at the host I deploy to: its org and the token's last four characters.

    Args:
        host (Literal['fly']):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostAccountView]
    """

    kwargs = _get_kwargs(
        host=host,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostAccountView | None:
    """Shown

     Which account at the host I deploy to: its org and the token's last four characters.

    Args:
        host (Literal['fly']):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostAccountView
    """

    return (
        await asyncio_detailed(
            host=host,
            client=client,
        )
    ).parsed
