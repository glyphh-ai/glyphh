from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.plan_change import PlanChange
from ...models.plan_in import PlanIn
from ...types import Response


def _get_kwargs(
    *,
    body: PlanIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/org/billing/plan",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | PlanChange | None:
    if response.status_code == 200:
        response_200 = PlanChange.from_dict(response.json())

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
) -> Response[HTTPValidationError | PlanChange]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: PlanIn,
) -> Response[HTTPValidationError | PlanChange]:
    """Change Plan

     Switch plan: pay in the page (from Free), applying (an upgrade, once Stripe confirms) or scheduled
    (a
    downgrade, at the period's end).

    Args:
        body (PlanIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlanChange]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: PlanIn,
) -> HTTPValidationError | PlanChange | None:
    """Change Plan

     Switch plan: pay in the page (from Free), applying (an upgrade, once Stripe confirms) or scheduled
    (a
    downgrade, at the period's end).

    Args:
        body (PlanIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlanChange
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: PlanIn,
) -> Response[HTTPValidationError | PlanChange]:
    """Change Plan

     Switch plan: pay in the page (from Free), applying (an upgrade, once Stripe confirms) or scheduled
    (a
    downgrade, at the period's end).

    Args:
        body (PlanIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlanChange]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: PlanIn,
) -> HTTPValidationError | PlanChange | None:
    """Change Plan

     Switch plan: pay in the page (from Free), applying (an upgrade, once Stripe confirms) or scheduled
    (a
    downgrade, at the period's end).

    Args:
        body (PlanIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlanChange
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
