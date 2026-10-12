from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.page import Page
from ...types import UNSET, Response, Unset


def _get_kwargs(
    thread_id: UUID,
    *,
    before: int | None | Unset = UNSET,
    limit: int | Unset = 50,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_before: int | Unset | None
    if isinstance(before, Unset):
        json_before = UNSET
    else:
        json_before = before
    params["before"] = json_before

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/threads/{thread_id}/messages".format(
            thread_id=quote(str(thread_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Page | None:
    if response.status_code == 200:
        response_200 = Page.from_dict(response.json())

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
) -> Response[HTTPValidationError | Page]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    thread_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    before: int | None | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[HTTPValidationError | Page]:
    """Messages

     A page of a thread's events from its machine, oldest first: the newest, or those before a number.

    Args:
        thread_id (UUID):
        before (int | None | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Page]
    """

    kwargs = _get_kwargs(
        thread_id=thread_id,
        before=before,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    thread_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    before: int | None | Unset = UNSET,
    limit: int | Unset = 50,
) -> HTTPValidationError | Page | None:
    """Messages

     A page of a thread's events from its machine, oldest first: the newest, or those before a number.

    Args:
        thread_id (UUID):
        before (int | None | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Page
    """

    return sync_detailed(
        thread_id=thread_id,
        client=client,
        before=before,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    thread_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    before: int | None | Unset = UNSET,
    limit: int | Unset = 50,
) -> Response[HTTPValidationError | Page]:
    """Messages

     A page of a thread's events from its machine, oldest first: the newest, or those before a number.

    Args:
        thread_id (UUID):
        before (int | None | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Page]
    """

    kwargs = _get_kwargs(
        thread_id=thread_id,
        before=before,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    thread_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    before: int | None | Unset = UNSET,
    limit: int | Unset = 50,
) -> HTTPValidationError | Page | None:
    """Messages

     A page of a thread's events from its machine, oldest first: the newest, or those before a number.

    Args:
        thread_id (UUID):
        before (int | None | Unset):
        limit (int | Unset):  Default: 50.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Page
    """

    return (
        await asyncio_detailed(
            thread_id=thread_id,
            client=client,
            before=before,
            limit=limit,
        )
    ).parsed
