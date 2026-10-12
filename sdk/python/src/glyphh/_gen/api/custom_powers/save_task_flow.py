from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.flow import Flow
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    power_id: UUID,
    *,
    body: Flow,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/v1/powers/custom/{power_id}/flow".format(
            power_id=quote(str(power_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Flow | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = Flow.from_dict(response.json())

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
) -> Response[Flow | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Flow,
) -> Response[Flow | HTTPValidationError]:
    """Save Flow

     Save a task's flow; a step that needs attention stops the save and is named.

    Args:
        power_id (UUID):
        body (Flow):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Flow | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        power_id=power_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Flow,
) -> Flow | HTTPValidationError | None:
    """Save Flow

     Save a task's flow; a step that needs attention stops the save and is named.

    Args:
        power_id (UUID):
        body (Flow):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Flow | HTTPValidationError
    """

    return sync_detailed(
        power_id=power_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Flow,
) -> Response[Flow | HTTPValidationError]:
    """Save Flow

     Save a task's flow; a step that needs attention stops the save and is named.

    Args:
        power_id (UUID):
        body (Flow):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Flow | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        power_id=power_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Flow,
) -> Flow | HTTPValidationError | None:
    """Save Flow

     Save a task's flow; a step that needs attention stops the save and is named.

    Args:
        power_id (UUID):
        body (Flow):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Flow | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            power_id=power_id,
            client=client,
            body=body,
        )
    ).parsed
