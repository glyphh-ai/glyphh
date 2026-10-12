from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_next_plan_version_family import AdminNextPlanVersionFamily
from ...models.http_validation_error import HTTPValidationError
from ...models.next_version import NextVersion
from ...models.plan_version import PlanVersion
from ...types import Response


def _get_kwargs(
    family: AdminNextPlanVersionFamily,
    *,
    body: NextVersion,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/admin/plans/{family}".format(
            family=quote(str(family), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | PlanVersion | None:
    if response.status_code == 201:
        response_201 = PlanVersion.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | PlanVersion]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    family: AdminNextPlanVersionFamily,
    *,
    client: AuthenticatedClient | Client,
    body: NextVersion,
) -> Response[HTTPValidationError | PlanVersion]:
    """Admin Next Version

     The family's next version, sold from now; orgs on the one before keep it until they change or are
    moved.

    Args:
        family (AdminNextPlanVersionFamily):
        body (NextVersion):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlanVersion]
    """

    kwargs = _get_kwargs(
        family=family,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    family: AdminNextPlanVersionFamily,
    *,
    client: AuthenticatedClient | Client,
    body: NextVersion,
) -> HTTPValidationError | PlanVersion | None:
    """Admin Next Version

     The family's next version, sold from now; orgs on the one before keep it until they change or are
    moved.

    Args:
        family (AdminNextPlanVersionFamily):
        body (NextVersion):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlanVersion
    """

    return sync_detailed(
        family=family,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    family: AdminNextPlanVersionFamily,
    *,
    client: AuthenticatedClient | Client,
    body: NextVersion,
) -> Response[HTTPValidationError | PlanVersion]:
    """Admin Next Version

     The family's next version, sold from now; orgs on the one before keep it until they change or are
    moved.

    Args:
        family (AdminNextPlanVersionFamily):
        body (NextVersion):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlanVersion]
    """

    kwargs = _get_kwargs(
        family=family,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    family: AdminNextPlanVersionFamily,
    *,
    client: AuthenticatedClient | Client,
    body: NextVersion,
) -> HTTPValidationError | PlanVersion | None:
    """Admin Next Version

     The family's next version, sold from now; orgs on the one before keep it until they change or are
    moved.

    Args:
        family (AdminNextPlanVersionFamily):
        body (NextVersion):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlanVersion
    """

    return (
        await asyncio_detailed(
            family=family,
            client=client,
            body=body,
        )
    ).parsed
