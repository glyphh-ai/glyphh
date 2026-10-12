from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.sign_in_cli_cli import SignInCliCli
from ...models.step import Step
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    cli: SignInCliCli,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/machines/{machine_id}/clis/{cli}/sign-in".format(
            machine_id=quote(str(machine_id), safe=""),
            cli=quote(str(cli), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | Step | None:
    if response.status_code == 200:
        response_200 = Step.from_dict(response.json())

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
) -> Response[HTTPValidationError | Step]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    cli: SignInCliCli,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | Step]:
    """Started

     Starts the CLI's own login on the machine; answers with what to show: the link, and Codex's code.

    Args:
        machine_id (UUID):
        cli (SignInCliCli):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Step]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        cli=cli,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    cli: SignInCliCli,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | Step | None:
    """Started

     Starts the CLI's own login on the machine; answers with what to show: the link, and Codex's code.

    Args:
        machine_id (UUID):
        cli (SignInCliCli):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Step
    """

    return sync_detailed(
        machine_id=machine_id,
        cli=cli,
        client=client,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    cli: SignInCliCli,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | Step]:
    """Started

     Starts the CLI's own login on the machine; answers with what to show: the link, and Codex's code.

    Args:
        machine_id (UUID):
        cli (SignInCliCli):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | Step]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        cli=cli,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    cli: SignInCliCli,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | Step | None:
    """Started

     Starts the CLI's own login on the machine; answers with what to show: the link, and Codex's code.

    Args:
        machine_id (UUID):
        cli (SignInCliCli):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | Step
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            cli=cli,
            client=client,
        )
    ).parsed
