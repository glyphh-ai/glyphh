from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.machine_card import MachineCard
from ...models.machine_change import MachineChange
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    *,
    body: MachineChange,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/machines/{machine_id}".format(
            machine_id=quote(str(machine_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | MachineCard | None:
    if response.status_code == 200:
        response_200 = MachineCard.from_dict(response.json())

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
) -> Response[HTTPValidationError | MachineCard]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MachineChange,
) -> Response[HTTPValidationError | MachineCard]:
    """Change

     Turn its shell over SSH on or off (off until I turn it on).

    Args:
        machine_id (UUID):
        body (MachineChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MachineCard]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MachineChange,
) -> HTTPValidationError | MachineCard | None:
    """Change

     Turn its shell over SSH on or off (off until I turn it on).

    Args:
        machine_id (UUID):
        body (MachineChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MachineCard
    """

    return sync_detailed(
        machine_id=machine_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MachineChange,
) -> Response[HTTPValidationError | MachineCard]:
    """Change

     Turn its shell over SSH on or off (off until I turn it on).

    Args:
        machine_id (UUID):
        body (MachineChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MachineCard]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MachineChange,
) -> HTTPValidationError | MachineCard | None:
    """Change

     Turn its shell over SSH on or off (off until I turn it on).

    Args:
        machine_id (UUID):
        body (MachineChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MachineCard
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            client=client,
            body=body,
        )
    ).parsed
