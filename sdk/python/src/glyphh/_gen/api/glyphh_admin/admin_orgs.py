from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.admin_orgs_family_type_0 import AdminOrgsFamilyType0
from ...models.admin_orgs_kind_type_0 import AdminOrgsKindType0
from ...models.admin_orgs_state_type_0 import AdminOrgsStateType0
from ...models.http_validation_error import HTTPValidationError
from ...models.org_page import OrgPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: str | Unset = "",
    family: AdminOrgsFamilyType0 | None | Unset = UNSET,
    state: AdminOrgsStateType0 | None | Unset = UNSET,
    kind: AdminOrgsKindType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    json_family: str | Unset | None
    if isinstance(family, Unset):
        json_family = UNSET
    elif isinstance(family, AdminOrgsFamilyType0):
        json_family = family.value
    else:
        json_family = family
    params["family"] = json_family

    json_state: str | Unset | None
    if isinstance(state, Unset):
        json_state = UNSET
    elif isinstance(state, AdminOrgsStateType0):
        json_state = state.value
    else:
        json_state = state
    params["state"] = json_state

    json_kind: str | Unset | None
    if isinstance(kind, Unset):
        json_kind = UNSET
    elif isinstance(kind, AdminOrgsKindType0):
        json_kind = kind.value
    else:
        json_kind = kind
    params["kind"] = json_kind

    params["page"] = page

    params["size"] = size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/orgs",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | OrgPage | None:
    if response.status_code == 200:
        response_200 = OrgPage.from_dict(response.json())

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
) -> Response[HTTPValidationError | OrgPage]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    family: AdminOrgsFamilyType0 | None | Unset = UNSET,
    state: AdminOrgsStateType0 | None | Unset = UNSET,
    kind: AdminOrgsKindType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | OrgPage]:
    """Admin Orgs

    Args:
        q (str | Unset):  Default: ''.
        family (AdminOrgsFamilyType0 | None | Unset):
        state (AdminOrgsStateType0 | None | Unset):
        kind (AdminOrgsKindType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgPage]
    """

    kwargs = _get_kwargs(
        q=q,
        family=family,
        state=state,
        kind=kind,
        page=page,
        size=size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    family: AdminOrgsFamilyType0 | None | Unset = UNSET,
    state: AdminOrgsStateType0 | None | Unset = UNSET,
    kind: AdminOrgsKindType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | OrgPage | None:
    """Admin Orgs

    Args:
        q (str | Unset):  Default: ''.
        family (AdminOrgsFamilyType0 | None | Unset):
        state (AdminOrgsStateType0 | None | Unset):
        kind (AdminOrgsKindType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgPage
    """

    return sync_detailed(
        client=client,
        q=q,
        family=family,
        state=state,
        kind=kind,
        page=page,
        size=size,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    family: AdminOrgsFamilyType0 | None | Unset = UNSET,
    state: AdminOrgsStateType0 | None | Unset = UNSET,
    kind: AdminOrgsKindType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> Response[HTTPValidationError | OrgPage]:
    """Admin Orgs

    Args:
        q (str | Unset):  Default: ''.
        family (AdminOrgsFamilyType0 | None | Unset):
        state (AdminOrgsStateType0 | None | Unset):
        kind (AdminOrgsKindType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OrgPage]
    """

    kwargs = _get_kwargs(
        q=q,
        family=family,
        state=state,
        kind=kind,
        page=page,
        size=size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    family: AdminOrgsFamilyType0 | None | Unset = UNSET,
    state: AdminOrgsStateType0 | None | Unset = UNSET,
    kind: AdminOrgsKindType0 | None | Unset = UNSET,
    page: int | Unset = 1,
    size: int | Unset = 25,
) -> HTTPValidationError | OrgPage | None:
    """Admin Orgs

    Args:
        q (str | Unset):  Default: ''.
        family (AdminOrgsFamilyType0 | None | Unset):
        state (AdminOrgsStateType0 | None | Unset):
        kind (AdminOrgsKindType0 | None | Unset):
        page (int | Unset):  Default: 1.
        size (int | Unset):  Default: 25.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OrgPage
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            family=family,
            state=state,
            kind=kind,
            page=page,
            size=size,
        )
    ).parsed
