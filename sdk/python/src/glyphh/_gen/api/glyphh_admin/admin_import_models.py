from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.import_ import Import
from ...models.imported import Imported
from ...types import Response


def _get_kwargs(
    provider_id: UUID,
    *,
    body: Import,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/admin/providers/{provider_id}/import".format(
            provider_id=quote(str(provider_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Imported | None:
    if response.status_code == 200:
        response_200 = Imported.from_dict(response.json())

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
) -> Response[HTTPValidationError | Imported]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Import,
) -> Response[HTTPValidationError | Imported]:
    """Admin Import

     The provider's own list of models, read with this key (never kept); new ones arrive on, without a
    description.

    Args:
        provider_id (UUID):
        body (Import):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Imported]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Import,
) -> HTTPValidationError | Imported | None:
    """Admin Import

     The provider's own list of models, read with this key (never kept); new ones arrive on, without a
    description.

    Args:
        provider_id (UUID):
        body (Import):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Imported
    """

    return sync_detailed(
        provider_id=provider_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Import,
) -> Response[HTTPValidationError | Imported]:
    """Admin Import

     The provider's own list of models, read with this key (never kept); new ones arrive on, without a
    description.

    Args:
        provider_id (UUID):
        body (Import):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Imported]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: Import,
) -> HTTPValidationError | Imported | None:
    """Admin Import

     The provider's own list of models, read with this key (never kept); new ones arrive on, without a
    description.

    Args:
        provider_id (UUID):
        body (Import):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Imported
    """

    return (
        await asyncio_detailed(
            provider_id=provider_id,
            client=client,
            body=body,
        )
    ).parsed
