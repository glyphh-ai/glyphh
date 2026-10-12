from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.funds_in import FundsIn
from ...models.http_validation_error import HTTPValidationError
from ...models.payment_start import PaymentStart
from ...types import Response


def _get_kwargs(
    *,
    body: FundsIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/org/billing/top-ups",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | PaymentStart | None:
    if response.status_code == 201:
        response_201 = PaymentStart.from_dict(response.json())

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
) -> Response[HTTPValidationError | PaymentStart]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: FundsIn,
) -> Response[HTTPValidationError | PaymentStart]:
    """Add Funds

     Start adding credit ($5 to $10,000): the page pays it in Stripe's Payment Element; credit lands when
    Stripe
    confirms.

    Args:
        body (FundsIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PaymentStart]
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
    body: FundsIn,
) -> HTTPValidationError | PaymentStart | None:
    """Add Funds

     Start adding credit ($5 to $10,000): the page pays it in Stripe's Payment Element; credit lands when
    Stripe
    confirms.

    Args:
        body (FundsIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PaymentStart
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: FundsIn,
) -> Response[HTTPValidationError | PaymentStart]:
    """Add Funds

     Start adding credit ($5 to $10,000): the page pays it in Stripe's Payment Element; credit lands when
    Stripe
    confirms.

    Args:
        body (FundsIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PaymentStart]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: FundsIn,
) -> HTTPValidationError | PaymentStart | None:
    """Add Funds

     Start adding credit ($5 to $10,000): the page pays it in Stripe's Payment Element; credit lands when
    Stripe
    confirms.

    Args:
        body (FundsIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PaymentStart
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
