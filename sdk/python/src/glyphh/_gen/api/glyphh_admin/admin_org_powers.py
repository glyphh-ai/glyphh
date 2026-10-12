from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.org_powers import OrgPowers
from ...types import UNSET, Response, Unset


def _get_kwargs(
    org_id: UUID,
    *,
    kind: None | str | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_kind: str | Unset | None
    if isinstance(kind, Unset):
        json_kind = UNSET
    else:
        json_kind = kind
    params["kind"] = json_kind

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/orgs/{org_id}/powers".format(
            org_id=quote(str(org_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | OrgPowers | None:
    if response.status_code == 200:
        response_200 = OrgPowers.from_dict(response.json())

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
) -> Response[HTTPValidationError | OrgPowers]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | OrgPowers]:
    """Admin Org Powers

    Args:
        org_id (UUID):
        kind (None | str | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgPowers]
    """

    kwargs = _get_kwargs(
        org_id=org_id,
        kind=kind,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | OrgPowers | None:
    """Admin Org Powers

    Args:
        org_id (UUID):
        kind (None | str | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgPowers
    """

    return sync_detailed(
        org_id=org_id,
        client=client,
        kind=kind,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | OrgPowers]:
    """Admin Org Powers

    Args:
        org_id (UUID):
        kind (None | str | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgPowers]
    """

    kwargs = _get_kwargs(
        org_id=org_id,
        kind=kind,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    kind: None | str | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | OrgPowers | None:
    """Admin Org Powers

    Args:
        org_id (UUID):
        kind (None | str | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgPowers
    """

    return (
        await asyncio_detailed(
            org_id=org_id,
            client=client,
            kind=kind,
            page=page,
            size=size,
        )
    ).parsed
