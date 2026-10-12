from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.file_text import FileText
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response


def _get_kwargs(
    power_id: UUID,
    *,
    path: str,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["path"] = path

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/powers/custom/{power_id}/file".format(
            power_id=quote(str(power_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> FileText | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = FileText.from_dict(response.json())

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
) -> Response[FileText | HTTPValidationError]:
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
    path: str,
) -> Response[FileText | HTTPValidationError]:
    """Read File

    Args:
        power_id (UUID):
        path (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FileText | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        power_id=power_id,
        path=path,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str,
) -> FileText | HTTPValidationError | None:
    """Read File

    Args:
        power_id (UUID):
        path (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FileText | HTTPValidationError
    """

    return sync_detailed(
        power_id=power_id,
        client=client,
        path=path,
    ).parsed


async def asyncio_detailed(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str,
) -> Response[FileText | HTTPValidationError]:
    """Read File

    Args:
        power_id (UUID):
        path (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FileText | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        power_id=power_id,
        path=path,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    power_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str,
) -> FileText | HTTPValidationError | None:
    """Read File

    Args:
        power_id (UUID):
        path (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FileText | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            power_id=power_id,
            client=client,
            path=path,
        )
    ).parsed
