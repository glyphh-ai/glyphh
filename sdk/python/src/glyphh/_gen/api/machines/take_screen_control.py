from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.screen_hold import ScreenHold
from ...models.screen_view import ScreenView
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    profile: str,
    *,
    body: ScreenHold,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/machines/{machine_id}/screens/{profile}/control".format(
            machine_id=quote(str(machine_id), safe=""),
            profile=quote(str(profile), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ScreenView | None:
    if response.status_code == 200:
        response_200 = ScreenView.from_dict(response.json())

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
) -> Response[HTTPValidationError | ScreenView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenHold,
) -> Response[HTTPValidationError | ScreenView]:
    """Controlled

     Takes control of the screen from a call (`hold`), or hands it back; the super power's browser waits
    meanwhile.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenHold):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScreenView]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        profile=profile,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenHold,
) -> HTTPValidationError | ScreenView | None:
    """Controlled

     Takes control of the screen from a call (`hold`), or hands it back; the super power's browser waits
    meanwhile.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenHold):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScreenView
    """

    return sync_detailed(
        machine_id=machine_id,
        profile=profile,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenHold,
) -> Response[HTTPValidationError | ScreenView]:
    """Controlled

     Takes control of the screen from a call (`hold`), or hands it back; the super power's browser waits
    meanwhile.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenHold):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScreenView]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        profile=profile,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenHold,
) -> HTTPValidationError | ScreenView | None:
    """Controlled

     Takes control of the screen from a call (`hold`), or hands it back; the super power's browser waits
    meanwhile.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenHold):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScreenView
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            profile=profile,
            client=client,
            body=body,
        )
    ).parsed
