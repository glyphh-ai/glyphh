from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.thread_row import ThreadRow
from ...models.thread_start import ThreadStart
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    *,
    body: ThreadStart,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/machines/{machine_id}/threads".format(
            machine_id=quote(str(machine_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ThreadRow | None:
    if response.status_code == 201:
        response_201 = ThreadRow.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | ThreadRow]:
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
    body: ThreadStart,
) -> Response[HTTPValidationError | ThreadRow]:
    """Start

     Start a thread on one of my machines: one super power on its own (refused, naming what is missing,
    until
    everything it needs is in place), or a crew Glyphh leads.

    Args:
        machine_id (UUID):
        body (ThreadStart):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ThreadRow]
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
    body: ThreadStart,
) -> HTTPValidationError | ThreadRow | None:
    """Start

     Start a thread on one of my machines: one super power on its own (refused, naming what is missing,
    until
    everything it needs is in place), or a crew Glyphh leads.

    Args:
        machine_id (UUID):
        body (ThreadStart):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ThreadRow
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
    body: ThreadStart,
) -> Response[HTTPValidationError | ThreadRow]:
    """Start

     Start a thread on one of my machines: one super power on its own (refused, naming what is missing,
    until
    everything it needs is in place), or a crew Glyphh leads.

    Args:
        machine_id (UUID):
        body (ThreadStart):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ThreadRow]
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
    body: ThreadStart,
) -> HTTPValidationError | ThreadRow | None:
    """Start

     Start a thread on one of my machines: one super power on its own (refused, naming what is missing,
    until
    everything it needs is in place), or a crew Glyphh leads.

    Args:
        machine_id (UUID):
        body (ThreadStart):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ThreadRow
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            client=client,
            body=body,
        )
    ).parsed
