from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.invoice_page import InvoicePage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_after: str | Unset | None
    if isinstance(after, Unset):
        json_after = UNSET
    else:
        json_after = after
    params["after"] = json_after

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/billing/invoices",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | InvoicePage | None:
    if response.status_code == 200:
        response_200 = InvoicePage.from_dict(response.json())

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
) -> Response[HTTPValidationError | InvoicePage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> Response[HTTPValidationError | InvoicePage]:
    """List Invoices

     Stripe's invoices, newest first, a page at a time by cursor (`after`: the last invoice's id).

    Args:
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InvoicePage]
    """

    kwargs = _get_kwargs(
        after=after,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> HTTPValidationError | InvoicePage | None:
    """List Invoices

     Stripe's invoices, newest first, a page at a time by cursor (`after`: the last invoice's id).

    Args:
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InvoicePage
    """

    return sync_detailed(
        client=client,
        after=after,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> Response[HTTPValidationError | InvoicePage]:
    """List Invoices

     Stripe's invoices, newest first, a page at a time by cursor (`after`: the last invoice's id).

    Args:
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InvoicePage]
    """

    kwargs = _get_kwargs(
        after=after,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> HTTPValidationError | InvoicePage | None:
    """List Invoices

     Stripe's invoices, newest first, a page at a time by cursor (`after`: the last invoice's id).

    Args:
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InvoicePage
    """

    return (
        await asyncio_detailed(
            client=client,
            after=after,
            limit=limit,
        )
    ).parsed
