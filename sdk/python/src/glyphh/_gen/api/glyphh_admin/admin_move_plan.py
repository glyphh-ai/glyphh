from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.org_overview import OrgOverview
from ...models.plan_pick import PlanPick
from ...types import Response


def _get_kwargs(
    org_id: UUID,
    *,
    body: PlanPick,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/admin/orgs/{org_id}/move".format(
            org_id=quote(str(org_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | OrgOverview | None:
    if response.status_code == 200:
        response_200 = OrgOverview.from_dict(response.json())

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
) -> Response[HTTPValidationError | OrgOverview]:
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
    body: PlanPick,
) -> Response[HTTPValidationError | OrgOverview]:
    """Admin Move

     To its family's version on sale, in 30 days (Billing shows it waiting).

    Args:
        org_id (UUID):
        body (PlanPick):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgOverview]
    """

    kwargs = _get_kwargs(
        org_id=org_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanPick,
) -> HTTPValidationError | OrgOverview | None:
    """Admin Move

     To its family's version on sale, in 30 days (Billing shows it waiting).

    Args:
        org_id (UUID):
        body (PlanPick):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgOverview
    """

    return sync_detailed(
        org_id=org_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanPick,
) -> Response[HTTPValidationError | OrgOverview]:
    """Admin Move

     To its family's version on sale, in 30 days (Billing shows it waiting).

    Args:
        org_id (UUID):
        body (PlanPick):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgOverview]
    """

    kwargs = _get_kwargs(
        org_id=org_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    org_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanPick,
) -> HTTPValidationError | OrgOverview | None:
    """Admin Move

     To its family's version on sale, in 30 days (Billing shows it waiting).

    Args:
        org_id (UUID):
        body (PlanPick):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgOverview
    """

    return (
        await asyncio_detailed(
            org_id=org_id,
            client=client,
            body=body,
        )
    ).parsed
