"""Registering an MCP client (RFC 7591) and knowing it again at the token endpoint. A redirect URI is https, or http
on this machine's own names (a native client's loopback); each is kept exactly and matched exactly. A confidential
client's secret is shown once and kept only as a hash."""

import hmac
import time
import uuid
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Row, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import OAuthClient
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.connector.errors import OAuthError, invalid_client

LOOPBACK: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
GRANT_TYPES: tuple[str, ...] = ("authorization_code", "refresh_token")

AuthMethod = Literal["none", "client_secret_post", "client_secret_basic"]
GrantType = Literal["authorization_code", "refresh_token"]


class Registration(BaseModel):
    """The client metadata Glyphh reads; any other metadata is accepted and ignored."""

    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    client_name: str | None = Field(default=None, max_length=100)
    token_endpoint_auth_method: AuthMethod = "client_secret_basic"
    grant_types: list[GrantType] = Field(default=list(GRANT_TYPES), min_length=1)
    response_types: list[Literal["code"]] = Field(default=["code"], min_length=1)


class Registered(BaseModel):
    client_id: str
    client_id_issued_at: int
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str
    client_secret: str | None = None
    client_secret_expires_at: int | None = None


def check_redirect_uri(uri: str) -> None:
    parts = urlsplit(uri)
    loopback = parts.scheme == "http" and parts.hostname in LOOPBACK
    if len(uri) > 2000 or parts.fragment or not parts.hostname or not (parts.scheme == "https" or loopback):
        raise OAuthError("invalid_redirect_uri", f"Not an allowed redirect URI (https, or http on localhost): {uri}")


def read_registration(body: object) -> Registration:
    try:
        found = Registration.model_validate(body)
    except ValidationError as err:
        raise OAuthError(
            "invalid_client_metadata", f"The client metadata is not valid: {err.errors()[0]['msg']}."
        ) from err
    for uri in found.redirect_uris:
        check_redirect_uri(uri)
    return found


async def register(conn: AsyncConnection, body: object) -> Registered:
    meta = read_registration(body)
    secret = None if meta.token_endpoint_auth_method == "none" else make_secret()
    name = (meta.client_name or "").strip() or str(urlsplit(meta.redirect_uris[0]).hostname)
    values = {
        "name": name,
        "redirect_uris": meta.redirect_uris,
        "auth_method": meta.token_endpoint_auth_method,
        "secret_hash": hash_secret(secret) if secret else None,
        "grant_types": sorted(set(meta.grant_types)),
    }
    client_id = (await conn.execute(insert(OAuthClient).values(values).returning(OAuthClient.id))).scalar_one()
    return Registered(
        client_id=str(client_id),
        client_id_issued_at=int(time.time()),
        client_name=name,
        redirect_uris=meta.redirect_uris,
        grant_types=values["grant_types"],
        response_types=["code"],
        token_endpoint_auth_method=meta.token_endpoint_auth_method,
        client_secret=secret,
        client_secret_expires_at=0 if secret else None,
    )


async def find(conn: AsyncConnection, client_id: str | None) -> Row | None:
    try:
        key = uuid.UUID(client_id or "")
    except ValueError:
        return None
    columns = (OAuthClient.id, OAuthClient.name, OAuthClient.redirect_uris, OAuthClient.grant_types)
    found = select(*columns, OAuthClient.auth_method, OAuthClient.secret_hash).where(OAuthClient.id == key)
    return (await conn.execute(found)).first()


async def authenticate(conn: AsyncConnection, client_id: str | None, secret: str | None) -> Row:
    """The client calling the token or revocation endpoint: a public one by its id, a confidential one by its id and
    secret (compared in constant time)."""
    client = await find(conn, client_id)
    if client is None:
        raise invalid_client()
    if client.secret_hash is not None and not hmac.compare_digest(client.secret_hash, hash_secret(secret or "")):
        raise invalid_client()
    return client
