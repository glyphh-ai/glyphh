"""Tests for the MCP model-admin tools (list_models / deploy_model / seed_model)."""

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import domains.mcp.admin_tools as admin
from domains.mcp.admin_tools import (
    ADMIN_TOOL_NAMES,
    admin_tool_definitions,
    handle_admin_tool,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_loaded(model_id="m1", org_id="org"):
    return SimpleNamespace(
        model_id=model_id, org_id=org_id, meta_name=model_id.title(),
        short_description="desc", loaded_at=datetime(2026, 1, 1),
        model_path=f"/models/{model_id}",
    )


class StubManager:
    def __init__(self):
        self.deploys = []
        self.unloads = []
        self.deletes = []
        self._loaded = [make_loaded("firewall")]

    def list_models(self):
        return self._loaded

    async def load_model_from_directory(self, model_dir, org_id, model_id):
        self.deploys.append((Path(model_dir), org_id, model_id))
        return make_loaded(model_id, org_id)

    def unload_model(self, org_id, model_id):
        self.unloads.append((org_id, model_id))
        return model_id == "firewall"

    async def delete_model(self, org_id, model_id):
        self.deletes.append((org_id, model_id))
        return {"unloaded": True, "glyphs_deleted": 3, "edges_deleted": 1}


@pytest.fixture
def manager(monkeypatch, tmp_path):
    monkeypatch.setattr(admin, "MODELS_HOME", tmp_path / "models")
    monkeypatch.setattr(admin, "_default_org_id", lambda: "test-org")
    return StubManager()


def test_tool_definitions_match_names():
    assert {t.name for t in admin_tool_definitions()} == ADMIN_TOOL_NAMES


def test_no_manager_raises():
    with pytest.raises(ValueError):
        run(handle_admin_tool(None, "list_models", {}))


def test_list_models(manager):
    result = run(handle_admin_tool(manager, "list_models", {}))
    assert result["count"] == 1
    assert result["models"][0]["model_id"] == "firewall"
    assert result["models"][0]["loaded_at"] == "2026-01-01T00:00:00"


def test_deploy_model_defaults_id_to_dirname(manager):
    result = run(handle_admin_tool(
        manager, "deploy_model", {"model_dir": "/opt/models/router"}))
    assert manager.deploys == [(Path("/opt/models/router"), "test-org", "router")]
    assert result["deployed"]["model_id"] == "router"


def test_deploy_model_requires_dir(manager):
    with pytest.raises(ValueError):
        run(handle_admin_tool(manager, "deploy_model", {}))


def test_seed_model_materializes_and_deploys(manager, tmp_path):
    exemplars = [{"text": "hello", "label": "greet"},
                 {"text": "bye", "label": "farewell"}]
    result = run(handle_admin_tool(manager, "seed_model", {
        "model_id": "intents", "exemplars": exemplars,
        "dimension": 2048, "seed": 7,
    }))
    model_dir = tmp_path / "models" / "intents"
    assert (model_dir / "manifest.yaml").exists()
    assert "ENCODER_CONFIG = EncoderConfig(dimension=2048, seed=7)" in \
        (model_dir / "encoder.py").read_text()
    lines = (model_dir / "data" / "exemplars.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert manager.deploys[-1] == (model_dir, "test-org", "intents")
    assert result["seeded"]["exemplars_added"] == 2


def test_seed_model_appends_on_reseed(manager, tmp_path):
    for _ in range(2):
        run(handle_admin_tool(manager, "seed_model", {
            "model_id": "intents",
            "exemplars": [{"text": "hi", "label": "greet"}],
        }))
    lines = (tmp_path / "models" / "intents" / "data" /
             "exemplars.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert len(manager.deploys) == 2


def test_seed_model_requires_exemplars(manager):
    with pytest.raises(ValueError):
        run(handle_admin_tool(manager, "seed_model",
                              {"model_id": "x", "exemplars": []}))


def test_unload_model(manager):
    result = run(handle_admin_tool(manager, "unload_model",
                                   {"model_id": "firewall"}))
    assert result == {"model_id": "firewall", "unloaded": True}
    assert manager.unloads == [("test-org", "firewall")]


def test_delete_model_requires_confirm(manager):
    with pytest.raises(ValueError):
        run(handle_admin_tool(manager, "delete_model",
                              {"model_id": "firewall"}))
    assert manager.deletes == []


def test_delete_model_with_confirm(manager):
    result = run(handle_admin_tool(
        manager, "delete_model", {"model_id": "firewall", "confirm": True}))
    assert result["glyphs_deleted"] == 3
    assert manager.deletes == [("test-org", "firewall")]
