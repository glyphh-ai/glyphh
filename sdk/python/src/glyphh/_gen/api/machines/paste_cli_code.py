from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.ended import Ended
from ...models.http_validation_error import HTTPValidationError
from ...models.paste_cli_code_cli import PasteCliCodeCli
from ...models.pasted import Pasted
from ...types import Response


def _get_kwargs(
    machine_id: UUID,
    cli: PasteCliCodeCli,
    *,
    body: Pasted,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/machines/{machine_id}/clis/{cli}/sign-in/code".format(
            machine_id=quote(str(machine_id), safe=""),
            cli=quote(str(cli), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Ended | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = Ended.from_dict(response.json())

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
) -> Response[Ended | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    machine_id: UUID,
    cli: PasteCliCodeCli,
    *,
    client: AuthenticatedClient | Client,
    body: Pasted,
) -> Response[Ended | HTTPValidationError]:
    """Pasted

     The code claude.ai showed the member, passed to Claude Code (never kept); answers when it has
    finished.

    Args:
        machine_id (UUID):
        cli (PasteCliCodeCli):
        body (Pasted):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Ended | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        cli=cli,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    machine_id: UUID,
    cli: PasteCliCodeCli,
    *,
    client: AuthenticatedClient | Client,
    body: Pasted,
) -> Ended | HTTPValidationError | None:
    """Pasted

     The code claude.ai showed the member, passed to Claude Code (never kept); answers when it has
    finished.

    Args:
        machine_id (UUID):
        cli (PasteCliCodeCli):
        body (Pasted):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Ended | HTTPValidationError
    """

    return sync_detailed(
        machine_id=machine_id,
        cli=cli,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    machine_id: UUID,
    cli: PasteCliCodeCli,
    *,
    client: AuthenticatedClient | Client,
    body: Pasted,
) -> Response[Ended | HTTPValidationError]:
    """Pasted

     The code claude.ai showed the member, passed to Claude Code (never kept); answers when it has
    finished.

    Args:
        machine_id (UUID):
        cli (PasteCliCodeCli):
        body (Pasted):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Ended | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        machine_id=machine_id,
        cli=cli,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    machine_id: UUID,
    cli: PasteCliCodeCli,
    *,
    client: AuthenticatedClient | Client,
    body: Pasted,
) -> Ended | HTTPValidationError | None:
    """Pasted

     The code claude.ai showed the member, passed to Claude Code (never kept); answers when it has
    finished.

    Args:
        machine_id (UUID):
        cli (PasteCliCodeCli):
        body (Pasted):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Ended | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            machine_id=machine_id,
            cli=cli,
            client=client,
            body=body,
        )
    ).parsed
