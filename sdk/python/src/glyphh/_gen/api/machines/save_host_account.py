from http import HTTPStatus
from typing import Any, Literal
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.account_in import AccountIn
from ...models.host_account_view import HostAccountView
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    host: Literal["fly"],
    *,
    body: AccountIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/v1/hosts/{host}/account".format(
            host=quote(str(host), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
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
    body: AccountIn,
) -> Response[HTTPValidationError | HostAccountView]:
    """Save

     My account at the host: a deploy token for my Fly org (and its slug), checked with Fly, kept
    encrypted.

    Args:
        host (Literal['fly']):
        body (AccountIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostAccountView]
    """

    kwargs = _get_kwargs(
        host=host,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
    body: AccountIn,
) -> HTTPValidationError | HostAccountView | None:
    """Save

     My account at the host: a deploy token for my Fly org (and its slug), checked with Fly, kept
    encrypted.

    Args:
        host (Literal['fly']):
        body (AccountIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostAccountView
    """

    return sync_detailed(
        host=host,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
    body: AccountIn,
) -> Response[HTTPValidationError | HostAccountView]:
    """Save

     My account at the host: a deploy token for my Fly org (and its slug), checked with Fly, kept
    encrypted.

    Args:
        host (Literal['fly']):
        body (AccountIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostAccountView]
    """

    kwargs = _get_kwargs(
        host=host,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    host: Literal["fly"],
    *,
    client: AuthenticatedClient | Client,
    body: AccountIn,
) -> HTTPValidationError | HostAccountView | None:
    """Save

     My account at the host: a deploy token for my Fly org (and its slug), checked with Fly, kept
    encrypted.

    Args:
        host (Literal['fly']):
        body (AccountIn):

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
            body=body,
        )
    ).parsed
