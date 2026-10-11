from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.member import Member
from ...models.member_change import MemberChange
from ...types import Response


def _get_kwargs(
    member_id: UUID,
    *,
    body: MemberChange,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/org/members/{member_id}".format(
            member_id=quote(str(member_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Member | None:
    if response.status_code == 200:
        response_200 = Member.from_dict(response.json())

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
) -> Response[HTTPValidationError | Member]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    member_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemberChange,
) -> Response[HTTPValidationError | Member]:
    """Update Member

    Args:
        member_id (UUID):
        body (MemberChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Member]
    """

    kwargs = _get_kwargs(
        member_id=member_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    member_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemberChange,
) -> HTTPValidationError | Member | None:
    """Update Member

    Args:
        member_id (UUID):
        body (MemberChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Member
    """

    return sync_detailed(
        member_id=member_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    member_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemberChange,
) -> Response[HTTPValidationError | Member]:
    """Update Member

    Args:
        member_id (UUID):
        body (MemberChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Member]
    """

    kwargs = _get_kwargs(
        member_id=member_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    member_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemberChange,
) -> HTTPValidationError | Member | None:
    """Update Member

    Args:
        member_id (UUID):
        body (MemberChange):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Member
    """

    return (
        await asyncio_detailed(
            member_id=member_id,
            client=client,
            body=body,
        )
    ).parsed
