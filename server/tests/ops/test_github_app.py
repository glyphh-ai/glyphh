"""The Glyphh GitHub App as the App: its key checked at start, its JWT, GitHub's answers failing closed, and a token
minted for one of the person's repos only."""

import json
import time
import uuid

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Forbidden, NotFound, Unavailable
from glyphh_server.models import GitHubInstallation
from glyphh_server.ops import github_app, github_installations
from glyphh_server.ops.github_app import GitHubApp, app_jwt
from tests.conftest import GITHUB_APP_ID, GITHUB_APP_KEY, GITHUB_APP_PEM, SETTINGS
from tests.db.helpers import person
from tests.fakes import FakeGitHubApp, _unb64, fake_http


def _app(fake: FakeGitHubApp) -> GitHubApp:
    return GitHubApp(fake_http(github_app=fake), SETTINGS, github_app.load_key(SETTINGS))


def _fake() -> FakeGitHubApp:
    return FakeGitHubApp(GITHUB_APP_KEY.public_key(), GITHUB_APP_ID)


def test_the_private_key_is_checked_at_start() -> None:
    assert github_app.load_key(SETTINGS.model_copy(update={"github_app_private_key": ""})) is None
    one_line = GITHUB_APP_PEM.replace("\n", "\\n")
    assert github_app.load_key(SETTINGS.model_copy(update={"github_app_private_key": one_line})) is not None
    ed = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    for bad in ("not a key", ed.decode()):
        with pytest.raises(RuntimeError, match="GLYPHH_GITHUB_APP_PRIVATE_KEY"):
            github_app.load_key(SETTINGS.model_copy(update={"github_app_private_key": bad}))


def test_the_jwt_is_rs256_issued_by_the_app_for_under_ten_minutes() -> None:
    head, body, _ = app_jwt(GITHUB_APP_ID, GITHUB_APP_KEY, now=1_000_000).split(".")
    assert json.loads(_unb64(head)) == {"alg": "RS256", "typ": "JWT"}
    assert json.loads(_unb64(body)) == {"iat": 999_940, "exp": 1_000_540, "iss": GITHUB_APP_ID}
    assert json.loads(_unb64(app_jwt(GITHUB_APP_ID, GITHUB_APP_KEY).split(".")[1]))["exp"] > time.time()


async def test_github_answers_fail_closed() -> None:
    for settings in (SETTINGS.model_copy(update={"github_app_slug": ""}), SETTINGS):
        with pytest.raises(Unavailable, match="GitHub isn't set up"):
            GitHubApp(fake_http(), settings, None if settings is SETTINGS else github_app.load_key(SETTINGS))
    fake = _fake()
    with pytest.raises(NotFound):
        await _app(fake).installation(5)
    fake.fail = True
    with pytest.raises(Unavailable, match="GitHub didn't answer"):
        await _app(fake).installation(5)
    fake.fail = False
    garbled = GitHubApp(
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))),
        SETTINGS,
        github_app.load_key(SETTINGS),
    )
    with pytest.raises(Unavailable):
        await garbled.installation(5)


async def test_a_repo_token_is_minted_only_for_the_installed_account(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    fake = _fake()
    installation_id = uuid.uuid4().int % 10**12
    fake.install(installation_id, 1, "Octo")
    with pytest.raises(NotFound, match="Install Glyphh's GitHub App"):
        async with engine.connect() as conn:
            await github_installations.repo_token(conn, _app(fake), ada.user_id, "octo/leads")
    async with engine.begin() as conn:
        values = {"user_id": ada.user_id, "installation_id": installation_id, "account_login": "Octo"}
        await conn.execute(insert(GitHubInstallation).values(values))
    async with engine.connect() as conn:
        minted = await github_installations.repo_token(conn, _app(fake), ada.user_id, "octo/leads")
        for repo in ("someone/leads", "octo", "octo/", "octo/a/b"):
            with pytest.raises(Forbidden):
                await github_installations.repo_token(conn, _app(fake), ada.user_id, repo)
    assert minted.token == "ghs_fake_repo_token" and minted.expires_at.year == 2026
    path = f"/app/installations/{installation_id}/access_tokens"
    assert fake.calls == [("POST", path, {"repositories": ["leads"], "permissions": {"contents": "read"}})]
    async with engine.begin() as conn:
        removed = update(GitHubInstallation).where(GitHubInstallation.user_id == ada.user_id)
        await conn.execute(removed.values(removed_at=func.now()))
    with pytest.raises(NotFound):
        async with engine.connect() as conn:
            await github_installations.repo_token(conn, _app(fake), ada.user_id, "octo/leads")
