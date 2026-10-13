from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.relay_tools import RelayTools
from ...models.relay_tools_mode import RelayToolsMode
from ...types import UNSET, Response, Unset


def _get_kwargs(
    connection_id: UUID,
    *,
    super_power_id: None | Unset | UUID = UNSET,
    mode: RelayToolsMode | Unset = RelayToolsMode.DRIVEN,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_super_power_id: str | Unset | None
    if isinstance(super_power_id, Unset):
        json_super_power_id = UNSET
    elif isinstance(super_power_id, UUID):
        json_super_power_id = str(super_power_id)
    else:
        json_super_power_id = super_power_id
    params["super_power_id"] = json_super_power_id

    json_mode: str | Unset = UNSET
    if not isinstance(mode, Unset):
        json_mode = mode.value

    params["mode"] = json_mode

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/relay/connections/{connection_id}/tools".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | RelayTools | None:
    if response.status_code == 200:
        response_200 = RelayTools.from_dict(response.json())

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
) -> Response[HTTPValidationError | RelayTools]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    super_power_id: None | Unset | UUID = UNSET,
    mode: RelayToolsMode | Unset = RelayToolsMode.DRIVEN,
) -> Response[HTTPValidationError | RelayTools]:
    """Relay Tools

     Its tools, each with the permission it runs under here (a loop is handed only what may run).

    Args:
        connection_id (UUID):
        super_power_id (None | Unset | UUID):
        mode (RelayToolsMode | Unset):  Default: RelayToolsMode.DRIVEN.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RelayTools]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        super_power_id=super_power_id,
        mode=mode,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    super_power_id: None | Unset | UUID = UNSET,
    mode: RelayToolsMode | Unset = RelayToolsMode.DRIVEN,
) -> HTTPValidationError | RelayTools | None:
    """Relay Tools

     Its tools, each with the permission it runs under here (a loop is handed only what may run).

    Args:
        connection_id (UUID):
        super_power_id (None | Unset | UUID):
        mode (RelayToolsMode | Unset):  Default: RelayToolsMode.DRIVEN.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RelayTools
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
        super_power_id=super_power_id,
        mode=mode,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    super_power_id: None | Unset | UUID = UNSET,
    mode: RelayToolsMode | Unset = RelayToolsMode.DRIVEN,
) -> Response[HTTPValidationError | RelayTools]:
    """Relay Tools

     Its tools, each with the permission it runs under here (a loop is handed only what may run).

    Args:
        connection_id (UUID):
        super_power_id (None | Unset | UUID):
        mode (RelayToolsMode | Unset):  Default: RelayToolsMode.DRIVEN.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RelayTools]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        super_power_id=super_power_id,
        mode=mode,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    super_power_id: None | Unset | UUID = UNSET,
    mode: RelayToolsMode | Unset = RelayToolsMode.DRIVEN,
) -> HTTPValidationError | RelayTools | None:
    """Relay Tools

     Its tools, each with the permission it runs under here (a loop is handed only what may run).

    Args:
        connection_id (UUID):
        super_power_id (None | Unset | UUID):
        mode (RelayToolsMode | Unset):  Default: RelayToolsMode.DRIVEN.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RelayTools
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
            super_power_id=super_power_id,
            mode=mode,
        )
    ).parsed
