from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.custom_page import CustomPage
from ...models.http_validation_error import HTTPValidationError
from ...models.list_custom_powers_kind_type_0 import ListCustomPowersKindType0
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    kind: ListCustomPowersKindType0 | None | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_kind: str | Unset | None
    if isinstance(kind, Unset):
        json_kind = UNSET
    elif isinstance(kind, ListCustomPowersKindType0):
        json_kind = kind.value
    else:
        json_kind = kind
    params["kind"] = json_kind

    params["q"] = q

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/powers/custom",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CustomPage | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = CustomPage.from_dict(response.json())

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
) -> Response[CustomPage | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: ListCustomPowersKindType0 | None | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[CustomPage | HTTPValidationError]:
    """List Custom

     My skills, plugins, tasks and apps, newest change first, with how many of each.

    Args:
        kind (ListCustomPowersKindType0 | None | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CustomPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        kind=kind,
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
    kind: ListCustomPowersKindType0 | None | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> CustomPage | HTTPValidationError | None:
    """List Custom

     My skills, plugins, tasks and apps, newest change first, with how many of each.

    Args:
        kind (ListCustomPowersKindType0 | None | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CustomPage | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        kind=kind,
        q=q,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    kind: ListCustomPowersKindType0 | None | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[CustomPage | HTTPValidationError]:
    """List Custom

     My skills, plugins, tasks and apps, newest change first, with how many of each.

    Args:
        kind (ListCustomPowersKindType0 | None | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CustomPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        kind=kind,
        q=q,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    kind: ListCustomPowersKindType0 | None | Unset = UNSET,
    q: str | Unset = "",
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> CustomPage | HTTPValidationError | None:
    """List Custom

     My skills, plugins, tasks and apps, newest change first, with how many of each.

    Args:
        kind (ListCustomPowersKindType0 | None | Unset):
        q (str | Unset):  Default: ''.
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CustomPage | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            kind=kind,
            q=q,
            page=page,
            size=size,
        )
    ).parsed
