from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.can_add import CanAdd
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/powers/can-add",
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> CanAdd | None:
    if response.status_code == 200:
        response_200 = CanAdd.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[CanAdd]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[CanAdd]:
    """What I Can Add

     The models and connections my teams allow, inside my org's list, with the teams that allow each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CanAdd]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> CanAdd | None:
    """What I Can Add

     The models and connections my teams allow, inside my org's list, with the teams that allow each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CanAdd
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[CanAdd]:
    """What I Can Add

     The models and connections my teams allow, inside my org's list, with the teams that allow each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CanAdd]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> CanAdd | None:
    """What I Can Add

     The models and connections my teams allow, inside my org's list, with the teams that allow each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CanAdd
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
