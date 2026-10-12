from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.service_page import ServicePage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = "",
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

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
        "url": "/v1/catalog/services",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ServicePage | None:
    if response.status_code == 200:
        response_200 = ServicePage.from_dict(response.json())

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
) -> Response[HTTPValidationError | ServicePage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> Response[HTTPValidationError | ServicePage]:
    """List Services

     Services to connect (Pipedream's apps), by cursor: pass the page's `after` for the next.

    Args:
        q (str | Unset):  Default: ''.
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ServicePage]
    """

    kwargs = _get_kwargs(
        q=q,
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
    q: str | Unset = "",
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> HTTPValidationError | ServicePage | None:
    """List Services

     Services to connect (Pipedream's apps), by cursor: pass the page's `after` for the next.

    Args:
        q (str | Unset):  Default: ''.
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ServicePage
    """

    return sync_detailed(
        client=client,
        q=q,
        after=after,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> Response[HTTPValidationError | ServicePage]:
    """List Services

     Services to connect (Pipedream's apps), by cursor: pass the page's `after` for the next.

    Args:
        q (str | Unset):  Default: ''.
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ServicePage]
    """

    kwargs = _get_kwargs(
        q=q,
        after=after,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    after: None | str | Unset = UNSET,
    limit: int | Unset = 25,
) -> HTTPValidationError | ServicePage | None:
    """List Services

     Services to connect (Pipedream's apps), by cursor: pass the page's `after` for the next.

    Args:
        q (str | Unset):  Default: ''.
        after (None | str | Unset):
        limit (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ServicePage
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            after=after,
            limit=limit,
        )
    ).parsed
