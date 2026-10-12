from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.answer_in import AnswerIn
from ...models.answered import Answered
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    question_id: UUID,
    *,
    body: AnswerIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/needs-you/{question_id}/answer".format(
            question_id=quote(str(question_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Answered | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = Answered.from_dict(response.json())

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
) -> Response[Answered | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    question_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AnswerIn,
) -> Response[Answered | HTTPValidationError]:
    """Answer One

     Allow or deny, once: answered anywhere, it is closed everywhere, and the machine is told.

    Args:
        question_id (UUID):
        body (AnswerIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Answered | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        question_id=question_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    question_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AnswerIn,
) -> Answered | HTTPValidationError | None:
    """Answer One

     Allow or deny, once: answered anywhere, it is closed everywhere, and the machine is told.

    Args:
        question_id (UUID):
        body (AnswerIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Answered | HTTPValidationError
    """

    return sync_detailed(
        question_id=question_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    question_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AnswerIn,
) -> Response[Answered | HTTPValidationError]:
    """Answer One

     Allow or deny, once: answered anywhere, it is closed everywhere, and the machine is told.

    Args:
        question_id (UUID):
        body (AnswerIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Answered | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        question_id=question_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    question_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AnswerIn,
) -> Answered | HTTPValidationError | None:
    """Answer One

     Allow or deny, once: answered anywhere, it is closed everywhere, and the machine is told.

    Args:
        question_id (UUID):
        body (AnswerIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Answered | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            question_id=question_id,
            client=client,
            body=body,
        )
    ).parsed
