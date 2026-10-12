from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.schedule_view import ScheduleView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    target: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_target: str | Unset | None
    if isinstance(target, Unset):
        json_target = UNSET
    elif isinstance(target, UUID):
        json_target = str(target)
    else:
        json_target = target
    params["target"] = json_target

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/schedules",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | list[ScheduleView] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ScheduleView.from_dict(response_200_item_data)

            response_200.append(response_200_item)

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
) -> Response[HTTPValidationError | list[ScheduleView]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    target: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | list[ScheduleView]]:
    """List Schedules

     My schedules, the soonest first; for one super power or task with `target`.

    Args:
        target (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | list[ScheduleView]]
    """

    kwargs = _get_kwargs(
        target=target,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    target: None | Unset | UUID = UNSET,
) -> HTTPValidationError | list[ScheduleView] | None:
    """List Schedules

     My schedules, the soonest first; for one super power or task with `target`.

    Args:
        target (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | list[ScheduleView]
    """

    return sync_detailed(
        client=client,
        target=target,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    target: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | list[ScheduleView]]:
    """List Schedules

     My schedules, the soonest first; for one super power or task with `target`.

    Args:
        target (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | list[ScheduleView]]
    """

    kwargs = _get_kwargs(
        target=target,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    target: None | Unset | UUID = UNSET,
) -> HTTPValidationError | list[ScheduleView] | None:
    """List Schedules

     My schedules, the soonest first; for one super power or task with `target`.

    Args:
        target (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | list[ScheduleView]
    """

    return (
        await asyncio_detailed(
            client=client,
            target=target,
        )
    ).parsed
