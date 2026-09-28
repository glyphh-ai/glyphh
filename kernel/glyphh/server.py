"""
Glyphh Runtime Server — host models, ingest data, query fact trees.

Single FastAPI application: model hosting, ingest, query, decisions,
with auth, licensing, metering, and deployment infrastructure.

Importable as ``glyphh.server:app`` for both pip-installed CLI usage and
Docker/production deployments.  The repo-root ``main.py`` is a thin shim
that re-exports this app.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infrastructure.config import get_settings, validate_settings
from infrastructure.database import init_db, close_db, async_session_maker
from shared.exceptions import GlyphhRuntimeException
from glyphh.licensing import load_license, set_current_license
from shared.middleware import (
    CorrelationIDMiddleware,
    LoggingMiddleware,
)
from domains.models.manager import ModelManager
from domains.resources.manager import ResourceManager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

settings = get_settings()
_start_time = datetime.utcnow()

# ── Global state ────────────────────────────────────────────────────────────

model_manager: Optional[ModelManager] = None
resource_manager: Optional[ResourceManager] = None


def get_model_manager() -> ModelManager:
    """Dependency for getting model manager"""
    return model_manager


def get_resource_manager() -> ResourceManager:
    """Dependency for getting resource manager"""
    return resource_manager




# ── Capabilities directory ──────────────────────────────────────────────────



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Boot the glyphh runtime."""
    global model_manager, resource_manager

    logger.info("Waking up...")

    # ── Configuration ───────────────────────────────────────────────────
    try:
        validate_settings()
        logger.info("Configuration validated")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    # ── Licensing & metering ────────────────────────────────────────────
    license_info = load_license()
    app.state.license = license_info
    set_current_license(license_info)
    logger.info(
        f"License: tier={license_info.tier}, org={license_info.org_id}, "
        f"ops={license_info.format_limit()}/mo, runtimes={license_info.max_runtimes}"
    )

    from glyphh.metering import get_meter
    meter = get_meter()
    usage = meter.get_usage(license_info.org_id)
    if usage > 0:
        logger.info(f"Usage this month: {usage:,} ops")
        if not license_info.is_unlimited:
            if usage >= license_info.max_encodings_per_month:
                logger.warning(
                    f"Monthly operation limit exceeded ({usage:,}/{license_info.max_encodings_per_month:,})"
                )
            elif license_info.encoding_warning_threshold() and usage >= license_info.encoding_warning_threshold():
                logger.warning(
                    f"Approaching monthly limit ({usage:,}/{license_info.max_encodings_per_month:,})"
                )

    # ── Database ────────────────────────────────────────────────────────
    await init_db()
    logger.info("Memory banks online")

    # ── Model & resource managers ───────────────────────────────────────
    model_manager = ModelManager(async_session_maker)
    resource_manager = ResourceManager(async_session_maker)

    # ── Models ──────────────────────────────────────────────────────────
    # The runtime ships with ZERO models installed. Users deploy models
    # via the MCP deploy_model / seed_model tools or a .glyphh package;
    # previously deployed models lazy-restore from the database on use.

    # ── Initialize MCP ─────────────────────────────────────────────────
    from domains.auth.service import AuthService
    from domains.mcp.app import create_mcp_session_managers

    auth_service = AuthService()
    json_manager, sse_manager = create_mcp_session_managers(
        auth_service, model_manager=model_manager)
    app.state.mcp_session_managers = (json_manager, sse_manager)
    logger.info("MCP endpoint online at /mcp")

    # ── Resume any incomplete encoding from previous boot ──────────────
    try:
        await model_manager.resume_staged_encoding()
    except Exception as e:
        logger.warning(f"Staged encoding resume: {e}")

    # ── Wait for ALL encoding to finish before accepting requests ──────
    if model_manager._encoding_in_progress:
        logger.info(
            f"Waiting for exemplar encoding to finish: "
            f"{[k[1] for k in model_manager._encoding_in_progress]}"
        )
        while model_manager._encoding_in_progress:
            await asyncio.sleep(1.0)
        logger.info("All exemplars encoded")

    logger.info("Glyphh runtime online.")

    # Run MCP session managers
    async with json_manager.run():
        async with sse_manager.run():
            yield

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    meter.flush()
    await close_db()
    logger.info("Glyphh runtime stopped.")
    logging.shutdown()


# Create FastAPI application
app = FastAPI(
    title="Glyphh Runtime",
    description="Glyphh runtime: host models, ingest data, query fact trees.",
    version="2.6.7",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    lifespan=lifespan,
)

# CORS middleware
if settings.cors_allow_all:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = settings.cors_origins_production or settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

# Custom middleware
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(LoggingMiddleware)


# Global exception handlers
@app.exception_handler(GlyphhRuntimeException)
async def runtime_exception_handler(request: Request, exc: GlyphhRuntimeException) -> JSONResponse:
    """Handle custom runtime exceptions with CORS headers"""
    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )
    origin = request.headers.get("origin")
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with CORS headers"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    response = JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )
    origin = request.headers.get("origin")
    if origin and _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def _is_allowed_origin(origin: str) -> bool:
    """Check if origin is in allowed CORS origins list."""
    if settings.cors_allow_all:
        return True
    import fnmatch
    origins = settings.cors_origins_production or settings.cors_origins
    for allowed in origins:
        if allowed == "*" or allowed == origin:
            return True
        if fnmatch.fnmatch(origin, allowed):
            return True
    return False


# Import and include routers
from api.routes.decide import router as decide_router
from api.routes.health import router as health_router
from api.routes.strand import router as strand_router
from api.routes.tokens import router as tokens_router

app.include_router(decide_router)
app.include_router(health_router)
app.include_router(strand_router)
app.include_router(tokens_router)


# MCP routing middleware — intercepts /mcp requests and forwards to the
# MCP SDK's Streamable HTTP handler. Single endpoint, no org/model.
from domains.mcp.app import MCPRoutingMiddleware

app.add_middleware(MCPRoutingMiddleware, mcp_app_getter=lambda: getattr(app.state, "mcp_session_managers", None))
