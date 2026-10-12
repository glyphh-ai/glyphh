from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.in_review import InReview
from ...models.review_queue_step import ReviewQueueStep
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    step: ReviewQueueStep | Unset = ReviewQueueStep.ORG,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_step: str | Unset = UNSET
    if not isinstance(step, Unset):
        json_step = step.value

    params["step"] = json_step

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/reviews",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | list[InReview] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = InReview.from_dict(response_200_item_data)

            response_200.append(response_200_item)

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
) -> Response[HTTPValidationError | list[InReview]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    step: ReviewQueueStep | Unset = ReviewQueueStep.ORG,
) -> Response[HTTPValidationError | list[InReview]]:
    """Review Queue

     What waits for me to review: my org's (org admins) or the marketplace's (super admins).

    Args:
        step (ReviewQueueStep | Unset):  Default: ReviewQueueStep.ORG.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | list[InReview]]
    """

    kwargs = _get_kwargs(
        step=step,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    step: ReviewQueueStep | Unset = ReviewQueueStep.ORG,
) -> HTTPValidationError | list[InReview] | None:
    """Review Queue

     What waits for me to review: my org's (org admins) or the marketplace's (super admins).

    Args:
        step (ReviewQueueStep | Unset):  Default: ReviewQueueStep.ORG.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | list[InReview]
    """

    return sync_detailed(
        client=client,
        step=step,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    step: ReviewQueueStep | Unset = ReviewQueueStep.ORG,
) -> Response[HTTPValidationError | list[InReview]]:
    """Review Queue

     What waits for me to review: my org's (org admins) or the marketplace's (super admins).

    Args:
        step (ReviewQueueStep | Unset):  Default: ReviewQueueStep.ORG.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | list[InReview]]
    """

    kwargs = _get_kwargs(
        step=step,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    step: ReviewQueueStep | Unset = ReviewQueueStep.ORG,
) -> HTTPValidationError | list[InReview] | None:
    """Review Queue

     What waits for me to review: my org's (org admins) or the marketplace's (super admins).

    Args:
        step (ReviewQueueStep | Unset):  Default: ReviewQueueStep.ORG.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | list[InReview]
    """

    return (
        await asyncio_detailed(
            client=client,
            step=step,
        )
    ).parsed
