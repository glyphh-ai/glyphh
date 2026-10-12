from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.call import Call
from ...models.http_validation_error import HTTPValidationError
from ...models.usage_call_scope import UsageCallScope
from ...types import UNSET, Response, Unset


def _get_kwargs(
    call_id: UUID,
    *,
    scope: UsageCallScope | Unset = UsageCallScope.ME,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_scope: str | Unset = UNSET
    if not isinstance(scope, Unset):
        json_scope = scope.value

    params["scope"] = json_scope

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/usage/calls/{call_id}".format(
            call_id=quote(str(call_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Call | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = Call.from_dict(response.json())

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
) -> Response[Call | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    call_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageCallScope | Unset = UsageCallScope.ME,
) -> Response[Call | HTTPValidationError]:
    """Get Call

    Args:
        call_id (UUID):
        scope (UsageCallScope | Unset):  Default: UsageCallScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Call | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        call_id=call_id,
        scope=scope,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    call_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageCallScope | Unset = UsageCallScope.ME,
) -> Call | HTTPValidationError | None:
    """Get Call

    Args:
        call_id (UUID):
        scope (UsageCallScope | Unset):  Default: UsageCallScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Call | HTTPValidationError
    """

    return sync_detailed(
        call_id=call_id,
        client=client,
        scope=scope,
    ).parsed


async def asyncio_detailed(
    call_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageCallScope | Unset = UsageCallScope.ME,
) -> Response[Call | HTTPValidationError]:
    """Get Call

    Args:
        call_id (UUID):
        scope (UsageCallScope | Unset):  Default: UsageCallScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Call | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        call_id=call_id,
        scope=scope,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    call_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageCallScope | Unset = UsageCallScope.ME,
) -> Call | HTTPValidationError | None:
    """Get Call

    Args:
        call_id (UUID):
        scope (UsageCallScope | Unset):  Default: UsageCallScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Call | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            call_id=call_id,
            client=client,
            scope=scope,
        )
    ).parsed
