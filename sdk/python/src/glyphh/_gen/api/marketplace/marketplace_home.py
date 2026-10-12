from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.home import Home
from ...models.http_validation_error import HTTPValidationError
from ...models.marketplace_home_kind_type_0 import MarketplaceHomeKindType0
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    kind: MarketplaceHomeKindType0 | None | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_kind: str | Unset | None
    if isinstance(kind, Unset):
        json_kind = UNSET
    elif isinstance(kind, MarketplaceHomeKindType0):
        json_kind = kind.value
    else:
        json_kind = kind
    params["kind"] = json_kind

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/marketplace/home",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Home | None:
    if response.status_code == 200:
        response_200 = Home.from_dict(response.json())

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
) -> Response[HTTPValidationError | Home]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: MarketplaceHomeKindType0 | None | Unset = UNSET,
) -> Response[HTTPValidationError | Home]:
    """Home

     Discover: the featured picks, the most added, the newest, and the categories.

    Args:
        kind (MarketplaceHomeKindType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Home]
    """

    kwargs = _get_kwargs(
        kind=kind,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    kind: MarketplaceHomeKindType0 | None | Unset = UNSET,
) -> HTTPValidationError | Home | None:
    """Home

     Discover: the featured picks, the most added, the newest, and the categories.

    Args:
        kind (MarketplaceHomeKindType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Home
    """

    return sync_detailed(
        client=client,
        kind=kind,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: MarketplaceHomeKindType0 | None | Unset = UNSET,
) -> Response[HTTPValidationError | Home]:
    """Home

     Discover: the featured picks, the most added, the newest, and the categories.

    Args:
        kind (MarketplaceHomeKindType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Home]
    """

    kwargs = _get_kwargs(
        kind=kind,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    kind: MarketplaceHomeKindType0 | None | Unset = UNSET,
) -> HTTPValidationError | Home | None:
    """Home

     Discover: the featured picks, the most added, the newest, and the categories.

    Args:
        kind (MarketplaceHomeKindType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Home
    """

    return (
        await asyncio_detailed(
            client=client,
            kind=kind,
        )
    ).parsed
