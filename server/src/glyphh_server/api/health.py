from fastapi import APIRouter, Request

from glyphh_server.ops.health import Health, health

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", operation_id="health")
async def get_health(request: Request) -> Health:
    return await health(request.app.state.engine, request.app.state.settings.version)
