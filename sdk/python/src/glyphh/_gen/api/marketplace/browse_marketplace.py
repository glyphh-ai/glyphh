from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.browse_marketplace_kind_type_0 import BrowseMarketplaceKindType0
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    kind: BrowseMarketplaceKindType0 | None | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_kind: str | Unset | None
    if isinstance(kind, Unset):
        json_kind = UNSET
    elif isinstance(kind, BrowseMarketplaceKindType0):
        json_kind = kind.value
    else:
        json_kind = kind
    params["kind"] = json_kind

    json_type_: str | Unset | None
    if isinstance(type_, Unset):
        json_type_ = UNSET
    else:
        json_type_ = type_
    params["type"] = json_type_

    json_category: str | Unset | None
    if isinstance(category, Unset):
        json_category = UNSET
    else:
        json_category = category
    params["category"] = json_category

    params["q"] = q

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/marketplace",
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | None:
    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: BrowseMarketplaceKindType0 | None | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> Response[HTTPValidationError]:
    """Browse

     Search what is listed for me, most added first, with how many of each type and category.

    Args:
        kind (BrowseMarketplaceKindType0 | None | Unset):
        type_ (None | str | Unset):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError]
    """

    kwargs = _get_kwargs(
        kind=kind,
        type_=type_,
        category=category,
        q=q,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    kind: BrowseMarketplaceKindType0 | None | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> HTTPValidationError | None:
    """Browse

     Search what is listed for me, most added first, with how many of each type and category.

    Args:
        kind (BrowseMarketplaceKindType0 | None | Unset):
        type_ (None | str | Unset):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError
    """

    return sync_detailed(
        client=client,
        kind=kind,
        type_=type_,
        category=category,
        q=q,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: BrowseMarketplaceKindType0 | None | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> Response[HTTPValidationError]:
    """Browse

     Search what is listed for me, most added first, with how many of each type and category.

    Args:
        kind (BrowseMarketplaceKindType0 | None | Unset):
        type_ (None | str | Unset):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError]
    """

    kwargs = _get_kwargs(
        kind=kind,
        type_=type_,
        category=category,
        q=q,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    kind: BrowseMarketplaceKindType0 | None | Unset = UNSET,
    type_: None | str | Unset = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 24,
) -> HTTPValidationError | None:
    """Browse

     Search what is listed for me, most added first, with how many of each type and category.

    Args:
        kind (BrowseMarketplaceKindType0 | None | Unset):
        type_ (None | str | Unset):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            kind=kind,
            type_=type_,
            category=category,
            q=q,
            page=page,
            size=size,
        )
    ).parsed
