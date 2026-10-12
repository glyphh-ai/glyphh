import datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.audit_page import AuditPage
from ...models.http_validation_error import HTTPValidationError
from ...models.list_audit_log_type_type_0 import ListAuditLogTypeType0
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    page: int | Unset = 1,
    size: int | Unset = 25,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    who: None | Unset | UUID = UNSET,
    type_: ListAuditLogTypeType0 | None | Unset = UNSET,
    target: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page"] = page

    params["size"] = size

    json_since: str | Unset | None
    if isinstance(since, Unset):
        json_since = UNSET
    elif isinstance(since, datetime.datetime):
        json_since = since.isoformat()
    else:
        json_since = since
    params["since"] = json_since

    json_until: str | Unset | None
    if isinstance(until, Unset):
        json_until = UNSET
    elif isinstance(until, datetime.datetime):
        json_until = until.isoformat()
    else:
        json_until = until
    params["until"] = json_until

    json_who: str | Unset | None
    if isinstance(who, Unset):
        json_who = UNSET
    elif isinstance(who, UUID):
        json_who = str(who)
    else:
        json_who = who
    params["who"] = json_who

    json_type_: str | Unset | None
    if isinstance(type_, Unset):
        json_type_ = UNSET
    elif isinstance(type_, ListAuditLogTypeType0):
        json_type_ = type_.value
    else:
        json_type_ = type_
    params["type"] = json_type_

    json_target: str | Unset | None
    if isinstance(target, Unset):
        json_target = UNSET
    else:
        json_target = target
    params["target"] = json_target

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/org/audit",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AuditPage | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AuditPage.from_dict(response.json())

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
) -> Response[AuditPage | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    who: None | Unset | UUID = UNSET,
    type_: ListAuditLogTypeType0 | None | Unset = UNSET,
    target: None | str | Unset = UNSET,
) -> Response[AuditPage | HTTPValidationError]:
    """List Audit Log

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        who (None | Unset | UUID):
        type_ (ListAuditLogTypeType0 | None | Unset):
        target (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuditPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        page=page,
        size=size,
        since=since,
        until=until,
        who=who,
        type_=type_,
        target=target,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    who: None | Unset | UUID = UNSET,
    type_: ListAuditLogTypeType0 | None | Unset = UNSET,
    target: None | str | Unset = UNSET,
) -> AuditPage | HTTPValidationError | None:
    """List Audit Log

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        who (None | Unset | UUID):
        type_ (ListAuditLogTypeType0 | None | Unset):
        target (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuditPage | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        page=page,
        size=size,
        since=since,
        until=until,
        who=who,
        type_=type_,
        target=target,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    who: None | Unset | UUID = UNSET,
    type_: ListAuditLogTypeType0 | None | Unset = UNSET,
    target: None | str | Unset = UNSET,
) -> Response[AuditPage | HTTPValidationError]:
    """List Audit Log

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        who (None | Unset | UUID):
        type_ (ListAuditLogTypeType0 | None | Unset):
        target (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuditPage | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        page=page,
        size=size,
        since=since,
        until=until,
        who=who,
        type_=type_,
        target=target,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = 1,
    size: int | Unset = 25,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    who: None | Unset | UUID = UNSET,
    type_: ListAuditLogTypeType0 | None | Unset = UNSET,
    target: None | str | Unset = UNSET,
) -> AuditPage | HTTPValidationError | None:
    """List Audit Log

    Args:
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        who (None | Unset | UUID):
        type_ (ListAuditLogTypeType0 | None | Unset):
        target (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuditPage | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
            size=size,
            since=since,
            until=until,
            who=who,
            type_=type_,
            target=target,
        )
    ).parsed
