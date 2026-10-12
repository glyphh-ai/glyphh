from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_catalog_models_state_type_0 import AdminCatalogModelsStateType0
from ...models.admin_catalog_models_type_type_0 import AdminCatalogModelsTypeType0
from ...models.admin_model_page import AdminModelPage
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    provider: None | str | Unset = UNSET,
    q: str | Unset = "",
    state: AdminCatalogModelsStateType0 | None | Unset = UNSET,
    type_: AdminCatalogModelsTypeType0 | None | Unset = UNSET,
    no_description: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_provider: str | Unset | None
    if isinstance(provider, Unset):
        json_provider = UNSET
    else:
        json_provider = provider
    params["provider"] = json_provider

    params["q"] = q

    json_state: str | Unset | None
    if isinstance(state, Unset):
        json_state = UNSET
    elif isinstance(state, AdminCatalogModelsStateType0):
        json_state = state.value
    else:
        json_state = state
    params["state"] = json_state

    json_type_: str | Unset | None
    if isinstance(type_, Unset):
        json_type_ = UNSET
    elif isinstance(type_, AdminCatalogModelsTypeType0):
        json_type_ = type_.value
    else:
        json_type_ = type_
    params["type"] = json_type_

    params["no_description"] = no_description

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/catalog-models",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AdminModelPage | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AdminModelPage.from_dict(response.json())

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
) -> Response[AdminModelPage | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    provider: None | str | Unset = UNSET,
    q: str | Unset = "",
    state: AdminCatalogModelsStateType0 | None | Unset = UNSET,
    type_: AdminCatalogModelsTypeType0 | None | Unset = UNSET,
    no_description: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[AdminModelPage | HTTPValidationError]:
    """Admin Catalog Models

    Args:
        provider (None | str | Unset):
        q (str | Unset):  Default: ''.
        state (AdminCatalogModelsStateType0 | None | Unset):
        type_ (AdminCatalogModelsTypeType0 | None | Unset):
        no_description (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminModelPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        provider=provider,
        q=q,
        state=state,
        type_=type_,
        no_description=no_description,
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
    provider: None | str | Unset = UNSET,
    q: str | Unset = "",
    state: AdminCatalogModelsStateType0 | None | Unset = UNSET,
    type_: AdminCatalogModelsTypeType0 | None | Unset = UNSET,
    no_description: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> AdminModelPage | HTTPValidationError | None:
    """Admin Catalog Models

    Args:
        provider (None | str | Unset):
        q (str | Unset):  Default: ''.
        state (AdminCatalogModelsStateType0 | None | Unset):
        type_ (AdminCatalogModelsTypeType0 | None | Unset):
        no_description (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminModelPage | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        provider=provider,
        q=q,
        state=state,
        type_=type_,
        no_description=no_description,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    provider: None | str | Unset = UNSET,
    q: str | Unset = "",
    state: AdminCatalogModelsStateType0 | None | Unset = UNSET,
    type_: AdminCatalogModelsTypeType0 | None | Unset = UNSET,
    no_description: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[AdminModelPage | HTTPValidationError]:
    """Admin Catalog Models

    Args:
        provider (None | str | Unset):
        q (str | Unset):  Default: ''.
        state (AdminCatalogModelsStateType0 | None | Unset):
        type_ (AdminCatalogModelsTypeType0 | None | Unset):
        no_description (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AdminModelPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        provider=provider,
        q=q,
        state=state,
        type_=type_,
        no_description=no_description,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    provider: None | str | Unset = UNSET,
    q: str | Unset = "",
    state: AdminCatalogModelsStateType0 | None | Unset = UNSET,
    type_: AdminCatalogModelsTypeType0 | None | Unset = UNSET,
    no_description: bool | Unset = False,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> AdminModelPage | HTTPValidationError | None:
    """Admin Catalog Models

    Args:
        provider (None | str | Unset):
        q (str | Unset):  Default: ''.
        state (AdminCatalogModelsStateType0 | None | Unset):
        type_ (AdminCatalogModelsTypeType0 | None | Unset):
        no_description (bool | Unset):  Default: False.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AdminModelPage | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            provider=provider,
            q=q,
            state=state,
            type_=type_,
            no_description=no_description,
            page=page,
            size=size,
        )
    ).parsed
