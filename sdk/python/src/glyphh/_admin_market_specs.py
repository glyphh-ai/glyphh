"""Glyphh admin's catalog and marketplace, as calls: providers and catalog models (added, changed, off and on,
removed, imported with a key never kept, a provider's logo), every listing, the featured shelf, the reviewer's
report, the categories, and Glyphh's audit log (in pages, or as CSV)."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.glyphh_admin import (
    admin_add_catalog_model,
    admin_add_category,
    admin_add_provider,
    admin_audit_log,
    admin_catalog_models,
    admin_categories,
    admin_change_catalog_model,
    admin_change_provider,
    admin_delete_category,
    admin_export_audit_log,
    admin_import_models,
    admin_listings,
    admin_order_categories,
    admin_providers,
    admin_remove_catalog_model,
    admin_remove_provider,
    admin_rename_category,
    admin_set_featured,
    admin_write_reviewer_report,
)
from glyphh._gen.models import (
    AdminAuditLogTypeType0,
    AdminCatalogModelsStateType0,
    AdminCatalogModelsTypeType0,
    AdminExportAuditLogTypeType0,
    AdminListingsStateType0,
    AdminProvidersStateType0,
    CategoryIn,
    CategoryOrder,
    Featured,
    Import,
    ModelChange,
    ModelIn,
    ProviderChange,
    ProviderIn,
    ReviewerReport,
    ReviewerReportReport,
)
from glyphh._gen.types import UNSET
from glyphh._upload import SET_PROVIDER_LOGO

Spec = tuple[Any, dict[str, Any]]


def _p(provider_id: str, **more: Any) -> dict[str, Any]:
    return {"provider_id": UUID(provider_id), **more}


def _models(provider=None, q="", state=None, type=None, no_description=False, page=1, size=25) -> Spec:  # type: ignore[no-untyped-def]
    return _call(admin_catalog_models), {
        "provider": provider or UNSET,
        "q": q,
        "state": AdminCatalogModelsStateType0(state) if state else UNSET,
        "type_": AdminCatalogModelsTypeType0(type) if type else UNSET,
        "no_description": no_description,
        "page": page,
        "size": size,
    }


def _audit(
    type_enum: Any,
    since: datetime | None,
    until: datetime | None,
    who: str | None,
    type: str | None,
    target: str | None,
    org: str | None,
) -> dict[str, Any]:
    return {
        "since": since or UNSET,
        "until": until or UNSET,
        "who": UUID(who) if who else UNSET,
        "type_": type_enum(type) if type else UNSET,
        "target": target or UNSET,
        "org": UUID(org) if org else UNSET,
    }


CATALOG_SPECS: dict[str, Callable[..., Spec]] = {
    "providers": lambda q="", state=None: (
        _call(admin_providers),
        {"q": q, "state": AdminProvidersStateType0(state) if state else UNSET},
    ),
    "add_provider": lambda **body: (_call(admin_add_provider), {"body": ProviderIn.from_dict(body)}),
    "change_provider": lambda provider_id, **body: (
        _call(admin_change_provider),
        _p(provider_id, body=ProviderChange.from_dict(body)),
    ),
    "remove_provider": lambda provider_id: (_call(admin_remove_provider), _p(provider_id)),
    "import_models": lambda provider_id, api_key: (
        _call(admin_import_models),
        _p(provider_id, body=Import(api_key=api_key)),
    ),
    "set_logo": lambda provider_id, data, content_type="image/png", name="logo.png", dark=False: (
        _call(SET_PROVIDER_LOGO),
        {"provider_id": provider_id, "data": data, "content_type": content_type, "name": name, "dark": dark},
    ),
    "models": _models,
    "add_model": lambda **body: (_call(admin_add_catalog_model), {"body": ModelIn.from_dict(body)}),
    "change_model": lambda model_id, **body: (
        _call(admin_change_catalog_model),
        {"model_id": UUID(model_id), "body": ModelChange.from_dict(body)},
    ),
    "remove_model": lambda model_id: (_call(admin_remove_catalog_model), {"model_id": UUID(model_id)}),
}

MARKET_SPECS: dict[str, Callable[..., Spec]] = {
    "listings": lambda q="", state=None, page=1, size=25: (
        _call(admin_listings),
        {"q": q, "state": AdminListingsStateType0(state) if state else UNSET, "page": page, "size": size},
    ),
    "set_featured": lambda listing_ids: (
        _call(admin_set_featured),
        {"body": Featured(listing_ids=[UUID(i) for i in listing_ids])},
    ),
    "report": lambda listing_version_id, report: (
        _call(admin_write_reviewer_report),
        {
            "listing_version_id": UUID(listing_version_id),
            "body": ReviewerReport(report=ReviewerReportReport.from_dict(report)),
        },
    ),
    "categories": lambda: (_call(admin_categories), {}),
    "add_category": lambda name: (_call(admin_add_category), {"body": CategoryIn(name=name)}),
    "rename_category": lambda category_id, name: (
        _call(admin_rename_category),
        {"category_id": UUID(category_id), "body": CategoryIn(name=name)},
    ),
    "delete_category": lambda category_id: (_call(admin_delete_category), {"category_id": UUID(category_id)}),
    "order_categories": lambda category_ids: (
        _call(admin_order_categories),
        {"body": CategoryOrder(category_ids=[UUID(i) for i in category_ids])},
    ),
    "audit": lambda since=None, until=None, who=None, type=None, target=None, org=None, page=1, size=25: (
        _call(admin_audit_log),
        {**_audit(AdminAuditLogTypeType0, since, until, who, type, target, org), "page": page, "size": size},
    ),
    "export_audit": lambda since=None, until=None, who=None, type=None, target=None, org=None: (
        _call(admin_export_audit_log),
        _audit(AdminExportAuditLogTypeType0, since, until, who, type, target, org),
    ),
}
