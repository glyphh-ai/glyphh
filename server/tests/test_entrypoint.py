from fastapi import FastAPI

from glyphh_server.config import Settings, get_settings


def test_the_entrypoint_builds_the_app_from_the_environment() -> None:
    from glyphh_server import main

    assert isinstance(main.app, FastAPI)
    assert isinstance(get_settings(), Settings)
