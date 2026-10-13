from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.host_template_host import HostTemplateHost
from ...models.host_template_response_hosttemplate import HostTemplateResponseHosttemplate
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    host: HostTemplateHost,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/hosts/{host}/template.json".format(
            host=quote(str(host), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | HostTemplateResponseHosttemplate | None:
    if response.status_code == 200:
        response_200 = HostTemplateResponseHosttemplate.from_dict(response.json())

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
) -> Response[HTTPValidationError | HostTemplateResponseHosttemplate]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    host: HostTemplateHost,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostTemplateResponseHosttemplate]:
    """Template

     The template AWS's quick-create link or Deploy to Azure makes the VM from.

    Args:
        host (HostTemplateHost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostTemplateResponseHosttemplate]
    """

    kwargs = _get_kwargs(
        host=host,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    host: HostTemplateHost,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostTemplateResponseHosttemplate | None:
    """Template

     The template AWS's quick-create link or Deploy to Azure makes the VM from.

    Args:
        host (HostTemplateHost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostTemplateResponseHosttemplate
    """

    return sync_detailed(
        host=host,
        client=client,
    ).parsed


async def asyncio_detailed(
    host: HostTemplateHost,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | HostTemplateResponseHosttemplate]:
    """Template

     The template AWS's quick-create link or Deploy to Azure makes the VM from.

    Args:
        host (HostTemplateHost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | HostTemplateResponseHosttemplate]
    """

    kwargs = _get_kwargs(
        host=host,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    host: HostTemplateHost,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | HostTemplateResponseHosttemplate | None:
    """Template

     The template AWS's quick-create link or Deploy to Azure makes the VM from.

    Args:
        host (HostTemplateHost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | HostTemplateResponseHosttemplate
    """

    return (
        await asyncio_detailed(
            host=host,
            client=client,
        )
    ).parsed
