"""
MCP admin tools — the model cockpit.

Everything an operator (human or agent) needs to stand up glyphh models
through any MCP client: list what's loaded, deploy a model directory,
or seed a brand-new model from inline exemplars. The CLI stays minimal
(repl + serve + offline bootstrap); administration lives here, where it
is self-describing, authenticated, and metered with everything else.

seed_model materializes a standard model directory
(~/.glyphh/models/<model_id>: manifest.yaml, encoder.py, data/*.jsonl)
and delegates to ModelManager.load_model_from_directory, which stages
and encodes the exemplars exactly as any other deploy.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.types import Tool

logger = logging.getLogger(__name__)

# Decoded .glyphh package size cap for inline (base64) deploys
MAX_PACKAGE_BYTES = 64 * 1024 * 1024


def models_home() -> Path:
    """Where deployed/seeded model directories live on this runtime."""
    return Path(os.environ.get(
        "GLYPHH_MODELS_HOME",
        str(Path.home() / ".glyphh" / "models"),
    ))


def admin_tool_definitions() -> List[Tool]:
    return [
        Tool(
            name="list_models",
            description=(
                "List the glyphh models currently loaded in this runtime, "
                "with name, version, description, and exemplar counts."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="deploy_model",
            description=(
                "Deploy (or redeploy) a glyphh model. Provide exactly one "
                "source: package_b64 (a .glyphh package — zip with "
                "manifest.yaml — base64-encoded, so remote clients can ship "
                "a model inline), package_path (a .glyphh file already on "
                "the server), or model_dir (an unpacked model directory on "
                "the server). Exemplars in data/*.jsonl are staged and "
                "encoded automatically; model_id defaults to the package "
                "manifest's model_id."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "package_b64": {
                        "type": "string",
                        "description": "Base64-encoded .glyphh package",
                    },
                    "package_path": {
                        "type": "string",
                        "description": "Path to a .glyphh file on the server",
                    },
                    "model_dir": {
                        "type": "string",
                        "description": "Absolute path to an unpacked model directory",
                    },
                    "model_id": {
                        "type": "string",
                        "description": ("Override the model ID (defaults to the "
                                        "manifest's model_id or directory name)"),
                    },
                },
            },
        ),
        Tool(
            name="seed_model",
            description=(
                "Create and deploy a new glyphh model from inline exemplars "
                "— no files needed. Writes a standard model directory under "
                "~/.glyphh/models/<model_id> and deploys it. Calling again "
                "with the same model_id appends exemplars and redeploys."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string"},
                    "exemplars": {
                        "type": "array",
                        "description": (
                            "Exemplar objects, one per training entry "
                            "(e.g. {\"text\": ..., \"label\": ...})"
                        ),
                        "items": {"type": "object"},
                    },
                    "name": {"type": "string", "description": "Display name"},
                    "description": {"type": "string"},
                    "dimension": {
                        "type": "integer",
                        "description": "Vector dimension (default 4096)",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Deterministic seed (default 42)",
                    },
                },
                "required": ["model_id", "exemplars"],
            },
        ),
        Tool(
            name="unload_model",
            description=(
                "Remove a model from memory. Its stored glyphs are kept and "
                "the model can be redeployed or lazily restored later."
            ),
            inputSchema={
                "type": "object",
                "properties": {"model_id": {"type": "string"}},
                "required": ["model_id"],
            },
        ),
        Tool(
            name="delete_model",
            description=(
                "Permanently delete a model: unload it AND remove its "
                "stored glyphs, vectors, edges, and config. Irreversible — "
                "requires confirm=true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string"},
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to actually delete",
                    },
                },
                "required": ["model_id", "confirm"],
            },
        ),
    ]


ADMIN_TOOL_NAMES = {
    "list_models", "deploy_model", "seed_model",
    "unload_model", "delete_model",
}


def _default_org_id() -> str:
    from glyphh.licensing import get_current_license
    return get_current_license().org_id


def _model_summary(model: Any) -> Dict[str, Any]:
    return {
        "model_id": model.model_id,
        "org_id": model.org_id,
        "name": model.meta_name,
        "description": model.short_description,
        "loaded_at": model.loaded_at.isoformat()
        if isinstance(model.loaded_at, datetime) else str(model.loaded_at),
        "path": model.model_path,
    }


def _unpack_package(glyphh_file: Path, model_id: Optional[str]) -> tuple:
    """Unpack a .glyphh package into models_home; return (dir, model_id)."""
    from glyphh.cli.packaging import read_manifest, unpack_model

    staging = Path(tempfile.mkdtemp(prefix="glyphh_deploy_"))
    unpack_model(glyphh_file, dest=staging)
    manifest = read_manifest(staging)
    resolved_id = model_id or manifest.get("model_id") or glyphh_file.stem
    model_dir = models_home() / resolved_id
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    if model_dir.exists():
        import shutil
        shutil.rmtree(model_dir)
    staging.rename(model_dir)
    return model_dir, resolved_id


def _resolve_deploy_source(args: Dict[str, Any]) -> tuple:
    """(model_dir, model_id) from exactly one of the three deploy sources."""
    sources = [k for k in ("package_b64", "package_path", "model_dir")
               if args.get(k)]
    if len(sources) != 1:
        raise ValueError(
            "Provide exactly one of 'package_b64', 'package_path', "
            f"or 'model_dir' (got {sources or 'none'})")

    if args.get("model_dir"):
        model_dir = Path(str(args["model_dir"])).expanduser()
        return model_dir, args.get("model_id") or model_dir.name

    if args.get("package_path"):
        package = Path(str(args["package_path"])).expanduser()
        if not package.is_file():
            raise ValueError(f"Package not found: {package}")
        return _unpack_package(package, args.get("model_id"))

    try:
        raw = base64.b64decode(args["package_b64"], validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 package: {e}")
    if len(raw) > MAX_PACKAGE_BYTES:
        raise ValueError(
            f"Package too large ({len(raw)} bytes; "
            f"limit {MAX_PACKAGE_BYTES})")
    with tempfile.NamedTemporaryFile(suffix=".glyphh", delete=False) as f:
        f.write(raw)
        tmp = Path(f.name)
    try:
        return _unpack_package(tmp, args.get("model_id"))
    finally:
        tmp.unlink(missing_ok=True)


def _materialize_seed_dir(
    model_id: str,
    exemplars: List[Dict[str, Any]],
    name: str,
    description: str,
    dimension: int,
    seed: int,
) -> Path:
    """Write/extend a standard model directory for a seeded model."""
    model_dir = models_home() / model_id
    data_dir = model_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    manifest = model_dir / "manifest.yaml"
    if not manifest.exists():
        manifest.write_text(
            f"model_id: {model_id}\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"version: 0.1.0\n"
            f"author: mcp-seed\n"
        )

    encoder = model_dir / "encoder.py"
    if not encoder.exists():
        encoder.write_text(
            '"""Auto-generated by the seed_model MCP tool."""\n'
            "from glyphh.core.config import EncoderConfig\n\n"
            f"ENCODER_CONFIG = EncoderConfig(dimension={dimension}, seed={seed})\n"
        )

    with (data_dir / "exemplars.jsonl").open("a") as f:
        for entry in exemplars:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return model_dir


async def handle_admin_tool(
    model_manager: Any,
    name: str,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute one admin tool. Raises ValueError on bad input."""
    if model_manager is None:
        raise ValueError("Model administration is not available on this runtime")

    if name == "list_models":
        models = model_manager.list_models()
        return {"models": [_model_summary(m) for m in models],
                "count": len(models)}

    if name == "deploy_model":
        model_dir, model_id = _resolve_deploy_source(args)
        loaded = await model_manager.load_model_from_directory(
            model_dir=model_dir,
            org_id=_default_org_id(),
            model_id=model_id,
        )
        return {"deployed": _model_summary(loaded)}

    if name == "seed_model":
        model_id = (args.get("model_id") or "").strip()
        exemplars = args.get("exemplars") or []
        if not model_id:
            raise ValueError("Missing 'model_id'")
        if not isinstance(exemplars, list) or not exemplars:
            raise ValueError("'exemplars' must be a non-empty list of objects")
        model_dir = _materialize_seed_dir(
            model_id=model_id,
            exemplars=exemplars,
            name=args.get("name") or model_id,
            description=args.get("description") or "Seeded via MCP",
            dimension=int(args.get("dimension") or 4096),
            seed=int(args.get("seed") or 42),
        )
        loaded = await model_manager.load_model_from_directory(
            model_dir=model_dir,
            org_id=_default_org_id(),
            model_id=model_id,
        )
        summary = _model_summary(loaded)
        summary["exemplars_added"] = len(exemplars)
        return {"seeded": summary}

    if name == "unload_model":
        model_id = (args.get("model_id") or "").strip()
        if not model_id:
            raise ValueError("Missing 'model_id'")
        unloaded = model_manager.unload_model(_default_org_id(), model_id)
        return {"model_id": model_id, "unloaded": unloaded}

    if name == "delete_model":
        model_id = (args.get("model_id") or "").strip()
        if not model_id:
            raise ValueError("Missing 'model_id'")
        if args.get("confirm") is not True:
            raise ValueError(
                "delete_model is irreversible; pass confirm=true to proceed")
        result = await model_manager.delete_model(_default_org_id(), model_id)
        result["model_id"] = model_id
        return result

    raise ValueError(f"Unknown admin tool: {name}")
