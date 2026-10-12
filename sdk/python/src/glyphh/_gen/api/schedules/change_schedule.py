from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.schedule_in import ScheduleIn
from ...models.schedule_view import ScheduleView
from ...types import Response


def _get_kwargs(
    schedule_id: UUID,
    *,
    body: ScheduleIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/v1/schedules/{schedule_id}".format(
            schedule_id=quote(str(schedule_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ScheduleView | None:
    if response.status_code == 200:
        response_200 = ScheduleView.from_dict(response.json())

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
) -> Response[HTTPValidationError | ScheduleView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    schedule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleIn,
) -> Response[HTTPValidationError | ScheduleView]:
    """Change Schedule

     Change it, or switch it off (`enabled` false) without losing it.

    Args:
        schedule_id (UUID):
        body (ScheduleIn): A schedule for exactly one of a super power or a task.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScheduleView]
    """

    kwargs = _get_kwargs(
        schedule_id=schedule_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    schedule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleIn,
) -> HTTPValidationError | ScheduleView | None:
    """Change Schedule

     Change it, or switch it off (`enabled` false) without losing it.

    Args:
        schedule_id (UUID):
        body (ScheduleIn): A schedule for exactly one of a super power or a task.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScheduleView
    """

    return sync_detailed(
        schedule_id=schedule_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    schedule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleIn,
) -> Response[HTTPValidationError | ScheduleView]:
    """Change Schedule

     Change it, or switch it off (`enabled` false) without losing it.

    Args:
        schedule_id (UUID):
        body (ScheduleIn): A schedule for exactly one of a super power or a task.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScheduleView]
    """

    kwargs = _get_kwargs(
        schedule_id=schedule_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    schedule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleIn,
) -> HTTPValidationError | ScheduleView | None:
    """Change Schedule

     Change it, or switch it off (`enabled` false) without losing it.

    Args:
        schedule_id (UUID):
        body (ScheduleIn): A schedule for exactly one of a super power or a task.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScheduleView
    """

    return (
        await asyncio_detailed(
            schedule_id=schedule_id,
            client=client,
            body=body,
        )
    ).parsed
