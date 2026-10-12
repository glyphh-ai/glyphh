"""Usage, as calls: a usage page's top, its breakdowns, a super power's runs, the billing periods, the audit log's
connector calls and power uses (by cursor, a row's detail, CSV), and a listing's stats. Answers are the server's
JSON as plain dicts (a CSV as text). Filters are keyword arguments: scope ("me" or "org"), since and until (dates,
or datetimes for the log), users and teams (ids), super_power, power, machine, run (ids), service, tool, kind,
status and error."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.usage import (
    export_usage_calls,
    export_usage_uses,
    listing_stats,
    usage_by,
    usage_call,
    usage_calls,
    usage_page,
    usage_periods,
    usage_runs,
    usage_use,
    usage_uses,
)
from glyphh._gen.models import (
    ExportUsageCallsScope,
    ExportUsageCallsStatusType0,
    ExportUsageUsesScope,
    ExportUsageUsesStatusType0,
    UsageByBy,
    UsageByScope,
    UsageCallScope,
    UsageCallsScope,
    UsageCallsStatusType0,
    UsagePageScope,
    UsageRunsScope,
    UsageUseScope,
    UsageUsesScope,
    UsageUsesStatusType0,
)
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]
IDS: tuple[str, ...] = ("super_power", "power", "machine", "run")


def _q(scope_type: Any, status_type: Any = None, *, scope: str = "me", **given: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"scope": scope_type(scope)}
    for key, value in given.items():
        if value is None:
            continue
        if key in ("users", "teams"):
            out[key] = [UUID(v) for v in value]
        elif key in IDS:
            out[key] = UUID(value)
        elif key == "status":
            out[key] = status_type(value)
        else:
            out[key] = value
    return out


USAGE_SPECS: dict[str, Callable[..., Spec]] = {
    "page": lambda **q: (_call(usage_page), _q(UsagePageScope, **q)),
    "by": lambda by, page=1, size=25, **q: (
        _call(usage_by),
        {"by": UsageByBy(by), "page": page, "size": size, **_q(UsageByScope, **q)},
    ),
    "runs": lambda page=1, size=25, **q: (_call(usage_runs), {"page": page, "size": size, **_q(UsageRunsScope, **q)}),
    "periods": lambda: (_call(usage_periods), {}),
    "calls": lambda after=None, size=50, **q: (
        _call(usage_calls),
        {"after": after or UNSET, "size": size, **_q(UsageCallsScope, UsageCallsStatusType0, **q)},
    ),
    "call": lambda call_id, scope="me": (_call(usage_call), {"call_id": UUID(call_id), "scope": UsageCallScope(scope)}),
    "export_calls": lambda **q: (
        _call(export_usage_calls),
        _q(ExportUsageCallsScope, ExportUsageCallsStatusType0, **q),
    ),
    "uses": lambda after=None, size=50, **q: (
        _call(usage_uses),
        {"after": after or UNSET, "size": size, **_q(UsageUsesScope, UsageUsesStatusType0, **q)},
    ),
    "use": lambda use_id, scope="me": (_call(usage_use), {"use_id": UUID(use_id), "scope": UsageUseScope(scope)}),
    "export_uses": lambda **q: (_call(export_usage_uses), _q(ExportUsageUsesScope, ExportUsageUsesStatusType0, **q)),
    "listing_stats": lambda listing_id, days=30: (_call(listing_stats), {"listing_id": UUID(listing_id), "days": days}),
}
