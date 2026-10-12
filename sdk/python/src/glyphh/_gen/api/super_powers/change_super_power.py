from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.super_power_change import SuperPowerChange
from ...models.super_power_view import SuperPowerView
from ...types import Response


def _get_kwargs(
    sp_id: UUID,
    *,
    body: SuperPowerChange,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/super-powers/{sp_id}".format(
            sp_id=quote(str(sp_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SuperPowerView | None:
    if response.status_code == 200:
        response_200 = SuperPowerView.from_dict(response.json())

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
) -> Response[HTTPValidationError | SuperPowerView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    sp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SuperPowerChange,
) -> Response[HTTPValidationError | SuperPowerView]:
    """Change Super Power

     Change any of its configuration; machines pick it up the next time they sync.

    Args:
        sp_id (UUID):
        body (SuperPowerChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SuperPowerView]
    """

    kwargs = _get_kwargs(
        sp_id=sp_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    sp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SuperPowerChange,
) -> HTTPValidationError | SuperPowerView | None:
    """Change Super Power

     Change any of its configuration; machines pick it up the next time they sync.

    Args:
        sp_id (UUID):
        body (SuperPowerChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SuperPowerView
    """

    return sync_detailed(
        sp_id=sp_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    sp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SuperPowerChange,
) -> Response[HTTPValidationError | SuperPowerView]:
    """Change Super Power

     Change any of its configuration; machines pick it up the next time they sync.

    Args:
        sp_id (UUID):
        body (SuperPowerChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SuperPowerView]
    """

    kwargs = _get_kwargs(
        sp_id=sp_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    sp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SuperPowerChange,
) -> HTTPValidationError | SuperPowerView | None:
    """Change Super Power

     Change any of its configuration; machines pick it up the next time they sync.

    Args:
        sp_id (UUID):
        body (SuperPowerChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SuperPowerView
    """

    return (
        await asyncio_detailed(
            sp_id=sp_id,
            client=client,
            body=body,
        )
    ).parsed
