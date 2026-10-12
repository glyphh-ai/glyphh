from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_model import AdminModel
from ...models.http_validation_error import HTTPValidationError
from ...models.model_change import ModelChange
from ...types import Response


def _get_kwargs(
    model_id: UUID,
    *,
    body: ModelChange,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/admin/catalog-models/{model_id}".format(
            model_id=quote(str(model_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AdminModel | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AdminModel.from_dict(response.json())

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
) -> Response[AdminModel | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelChange,
) -> Response[AdminModel | HTTPValidationError]:
    """Admin Change Model

    Args:
        model_id (UUID):
        body (ModelChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminModel | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelChange,
) -> AdminModel | HTTPValidationError | None:
    """Admin Change Model

    Args:
        model_id (UUID):
        body (ModelChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminModel | HTTPValidationError
    """

    return sync_detailed(
        model_id=model_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelChange,
) -> Response[AdminModel | HTTPValidationError]:
    """Admin Change Model

    Args:
        model_id (UUID):
        body (ModelChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminModel | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelChange,
) -> AdminModel | HTTPValidationError | None:
    """Admin Change Model

    Args:
        model_id (UUID):
        body (ModelChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminModel | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            model_id=model_id,
            client=client,
            body=body,
        )
    ).parsed
