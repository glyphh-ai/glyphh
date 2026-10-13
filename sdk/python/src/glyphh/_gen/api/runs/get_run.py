from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_run_scope import GetRunScope
from ...models.http_validation_error import HTTPValidationError
from ...models.run_view import RunView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    run_id: UUID,
    *,
    scope: GetRunScope | Unset = GetRunScope.ME,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_scope: str | Unset = UNSET
    if not isinstance(scope, Unset):
        json_scope = scope.value

    params["scope"] = json_scope

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/runs/{run_id}".format(
            run_id=quote(str(run_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | RunView | None:
    if response.status_code == 200:
        response_200 = RunView.from_dict(response.json())

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
) -> Response[HTTPValidationError | RunView]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: GetRunScope | Unset = GetRunScope.ME,
) -> Response[HTTPValidationError | RunView]:
    """Get Run

    Args:
        run_id (UUID):
        scope (GetRunScope | Unset):  Default: GetRunScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunView]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        scope=scope,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: GetRunScope | Unset = GetRunScope.ME,
) -> HTTPValidationError | RunView | None:
    """Get Run

    Args:
        run_id (UUID):
        scope (GetRunScope | Unset):  Default: GetRunScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunView
    """

    return sync_detailed(
        run_id=run_id,
        client=client,
        scope=scope,
    ).parsed


async def asyncio_detailed(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: GetRunScope | Unset = GetRunScope.ME,
) -> Response[HTTPValidationError | RunView]:
    """Get Run

    Args:
        run_id (UUID):
        scope (GetRunScope | Unset):  Default: GetRunScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunView]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        scope=scope,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: GetRunScope | Unset = GetRunScope.ME,
) -> HTTPValidationError | RunView | None:
    """Get Run

    Args:
        run_id (UUID):
        scope (GetRunScope | Unset):  Default: GetRunScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunView
    """

    return (
        await asyncio_detailed(
            run_id=run_id,
            client=client,
            scope=scope,
        )
    ).parsed
