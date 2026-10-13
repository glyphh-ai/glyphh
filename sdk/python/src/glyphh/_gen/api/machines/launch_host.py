from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.host_launch import HostLaunch
from ...models.http_validation_error import HTTPValidationError
from ...models.launch_host_host import LaunchHostHost
from ...models.launch_in import LaunchIn
from ...types import Response


def _get_kwargs(
    host: LaunchHostHost,
    *,
    body: LaunchIn,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/hosts/{host}/launch".format(
            host=quote(str(host), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | HostLaunch | None:
    if response.status_code == 201:
        response_201 = HostLaunch.from_dict(response.json())

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
) -> Response[HTTPValidationError | HostLaunch]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    host: LaunchHostHost,
    *,
    client: AuthenticatedClient | Client,
    body: LaunchIn,
) -> Response[HTTPValidationError | HostLaunch]:
    """Launched

     A new machine at a host whose own console makes the VM: the one-click code, and AWS's quick-create
    link, Deploy
    to Azure, the first boot to paste (GCP, DigitalOcean, Hetzner) or the one line for any VPS.

    Args:
        host (LaunchHostHost):
        body (LaunchIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostLaunch]
    """

    kwargs = _get_kwargs(
        host=host,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    host: LaunchHostHost,
    *,
    client: AuthenticatedClient | Client,
    body: LaunchIn,
) -> HTTPValidationError | HostLaunch | None:
    """Launched

     A new machine at a host whose own console makes the VM: the one-click code, and AWS's quick-create
    link, Deploy
    to Azure, the first boot to paste (GCP, DigitalOcean, Hetzner) or the one line for any VPS.

    Args:
        host (LaunchHostHost):
        body (LaunchIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostLaunch
    """

    return sync_detailed(
        host=host,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    host: LaunchHostHost,
    *,
    client: AuthenticatedClient | Client,
    body: LaunchIn,
) -> Response[HTTPValidationError | HostLaunch]:
    """Launched

     A new machine at a host whose own console makes the VM: the one-click code, and AWS's quick-create
    link, Deploy
    to Azure, the first boot to paste (GCP, DigitalOcean, Hetzner) or the one line for any VPS.

    Args:
        host (LaunchHostHost):
        body (LaunchIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostLaunch]
    """

    kwargs = _get_kwargs(
        host=host,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    host: LaunchHostHost,
    *,
    client: AuthenticatedClient | Client,
    body: LaunchIn,
) -> HTTPValidationError | HostLaunch | None:
    """Launched

     A new machine at a host whose own console makes the VM: the one-click code, and AWS's quick-create
    link, Deploy
    to Azure, the first boot to paste (GCP, DigitalOcean, Hetzner) or the one line for any VPS.

    Args:
        host (LaunchHostHost):
        body (LaunchIn):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostLaunch
    """

    return (
        await asyncio_detailed(
            host=host,
            client=client,
            body=body,
        )
    ).parsed
