"""The staff view's API, /v1/admin: staff only, every request audited (deps.py)."""

from fastapi import APIRouter

from glyphh_server.api.admin import events, orgs, overview, people, traffic

router = APIRouter(prefix="/v1/admin", tags=["staff"])
for part in (overview, orgs, people, events, traffic):
    router.include_router(part.router)
