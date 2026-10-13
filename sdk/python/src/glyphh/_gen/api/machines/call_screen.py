from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.screen_call import ScreenCall
from ...models.screen_offer import ScreenOffer
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    profile: str,
    *,
    body: ScreenOffer,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/machines/{machine_id}/screens/{profile}/calls".format(
            machine_id=quote(str(machine_id), safe=""),
            profile=quote(str(profile), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ScreenCall | None:
    if response.status_code == 200:
        response_200 = ScreenCall.from_dict(response.json())

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
) -> Response[HTTPValidationError | ScreenCall]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenOffer,
) -> Response[HTTPValidationError | ScreenCall]:
    """Called

     Watches a profile's screen: the view's offer (every candidate gathered) answered by the machine's,
    with the
    TURN servers both use. The screen goes end to end; the server only passes this.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenOffer):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScreenCall]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        profile=profile,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenOffer,
) -> HTTPValidationError | ScreenCall | None:
    """Called

     Watches a profile's screen: the view's offer (every candidate gathered) answered by the machine's,
    with the
    TURN servers both use. The screen goes end to end; the server only passes this.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenOffer):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScreenCall
    """

    return sync_detailed(
        machine_id=machine_id,
        profile=profile,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenOffer,
) -> Response[HTTPValidationError | ScreenCall]:
    """Called

     Watches a profile's screen: the view's offer (every candidate gathered) answered by the machine's,
    with the
    TURN servers both use. The screen goes end to end; the server only passes this.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenOffer):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ScreenCall]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        profile=profile,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    profile: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScreenOffer,
) -> HTTPValidationError | ScreenCall | None:
    """Called

     Watches a profile's screen: the view's offer (every candidate gathered) answered by the machine's,
    with the
    TURN servers both use. The screen goes end to end; the server only passes this.

    Args:
        machine_id (UUID):
        profile (str):
        body (ScreenOffer):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ScreenCall
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            profile=profile,
            client=client,
            body=body,
        )
    ).parsed
