from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.usage_use_scope import UsageUseScope
from ...models.use import Use
from ...types import UNSET, Response, Unset


def _get_kwargs(
    use_id: UUID,
    *,
    scope: UsageUseScope | Unset = UsageUseScope.ME,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_scope: str | Unset = UNSET
    if not isinstance(scope, Unset):
        json_scope = scope.value

    params["scope"] = json_scope

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/usage/uses/{use_id}".format(
            use_id=quote(str(use_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Use | None:
    if response.status_code == 200:
        response_200 = Use.from_dict(response.json())

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
) -> Response[HTTPValidationError | Use]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    use_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageUseScope | Unset = UsageUseScope.ME,
) -> Response[HTTPValidationError | Use]:
    """Get Use

    Args:
        use_id (UUID):
        scope (UsageUseScope | Unset):  Default: UsageUseScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Use]
    """

    kwargs = _get_kwargs(
        use_id=use_id,
        scope=scope,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    use_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageUseScope | Unset = UsageUseScope.ME,
) -> HTTPValidationError | Use | None:
    """Get Use

    Args:
        use_id (UUID):
        scope (UsageUseScope | Unset):  Default: UsageUseScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Use
    """

    return sync_detailed(
        use_id=use_id,
        client=client,
        scope=scope,
    ).parsed


async def asyncio_detailed(
    use_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageUseScope | Unset = UsageUseScope.ME,
) -> Response[HTTPValidationError | Use]:
    """Get Use

    Args:
        use_id (UUID):
        scope (UsageUseScope | Unset):  Default: UsageUseScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Use]
    """

    kwargs = _get_kwargs(
        use_id=use_id,
        scope=scope,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    use_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    scope: UsageUseScope | Unset = UsageUseScope.ME,
) -> HTTPValidationError | Use | None:
    """Get Use

    Args:
        use_id (UUID):
        scope (UsageUseScope | Unset):  Default: UsageUseScope.ME.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Use
    """

    return (
        await asyncio_detailed(
            use_id=use_id,
            client=client,
            scope=scope,
        )
    ).parsed
