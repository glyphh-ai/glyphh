"""Cloudflare's API faked at the HTTP layer for the traffic pull: the zones list (paged) and the GraphQL datasets it
asks (each zone's settings, httpRequests1dGroups, httpRequestsAdaptiveGroups, the account's Web Analytics), each of
which can be refused with Cloudflare's own GraphQL error, and the whole of it with an HTTP status."""

import json
from datetime import date, datetime, timedelta
from typing import Any

import httpx

TOKEN: str = "cf-test-token"
FIELDS: list[str] = [  # as Cloudflare names them
    "count",
    "dimensions_clientRequestHTTPHost",
    "dimensions_clientRequestPath",
    "dimensions_clientRefererHost",
    "dimensions_edgeResponseContentTypeName",
    "dimensions_date",
    "sum_visits",
]
DAILY_DAY: dict[str, Any] = {
    "sum": {
        "requests": 100,
        "pageViews": 40,
        "bytes": 1000,
        "threats": 1,
        "cachedRequests": 25,
        "countryMap": [{"clientCountryName": "GB", "requests": 60}, {"clientCountryName": "US", "requests": 40}],
    },
    "uniq": {"uniques": 10},
}


def zone(zone_id: str, name: str, account: str | None = "acc-1") -> dict[str, Any]:
    return {
        "id": zone_id,
        "name": name,
        "plan": {"name": "Free Website"},
        "account": {"id": account} if account else None,
    }


class FakeCloudflare:
    def __init__(self) -> None:
        self.zones: list[dict[str, Any]] = [zone("z-ai", "glyphh.ai"), zone("z-app", "glyphh.app")]
        self.page_size: int = 50
        self.status: int | None = None  # every call answered with this status
        self.refuse: dict[str, str] = {}  # settings, rum, daily, pages, referrers, hosts -> the GraphQL error
        self.adaptive: dict[str, Any] | None = {
            "enabled": True,
            "notOlderThan": 3 * 86_400,
            "maxDuration": 86_400,
            "maxPageSize": 100,
            "availableFields": FIELDS,
        }
        self.daily_settings: dict[str, Any] | None = {"enabled": True, "notOlderThan": 365 * 86_400}
        self.scale: int = 1  # the adaptive datasets' counts are multiplied by this
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.page_loads: bool = True  # Web Analytics on and beaconing

    def _zones(self, request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", 1))
        at = (page - 1) * self.page_size
        pages = max(1, -(-len(self.zones) // self.page_size))
        result = self.zones[at : at + self.page_size]
        return httpx.Response(200, json={"success": True, "result": result, "result_info": {"total_pages": pages}})

    def _daily(self, v: dict[str, Any]) -> list[dict[str, Any]]:
        since, until = date.fromisoformat(v["since"]), date.fromisoformat(v["until"])
        days = [until - timedelta(days=i) for i in range(min(3, (until - since).days + 1))]
        return [{"dimensions": {"date": str(d)}, **DAILY_DAY} for d in sorted(days)]

    @staticmethod
    def _day(v: dict[str, Any]) -> str:
        """The window's last day, as the rows of a one-day window name it."""
        return str((datetime.fromisoformat(v["end"].replace("Z", "+00:00")) - timedelta(seconds=1)).date())

    def _adaptive(self, query: str, v: dict[str, Any]) -> list[dict[str, Any]]:
        n, day = self.scale, self._day(v)
        if "clientRequestPath" in query:
            return [
                {
                    "count": 30 * n,
                    "dimensions": {"date": day, "clientRequestHTTPHost": "glyphh.ai", "clientRequestPath": "/"},
                },
                # no date: the window's last day
                {"count": 5 * n, "dimensions": {"clientRequestHTTPHost": "docs.glyphh.ai", "clientRequestPath": ""}},
            ]
        if "clientRefererHost" in query or "clientRequestReferer" in query:
            field = "clientRefererHost" if "clientRefererHost" in query else "clientRequestReferer"
            google = "www.google.com" if field == "clientRefererHost" else "https://www.google.com/search?q=glyphh"
            on = {"date": day, "clientRequestHTTPHost": "glyphh.ai"}
            return [
                {"count": 9 * n, "dimensions": {**on, field: google}},
                {"count": 7 * n, "dimensions": {**on, field: "docs.glyphh.ai"}},
                {"count": 3 * n, "dimensions": {**on, field: ""}},
            ]
        return [
            {
                "count": 50 * n,
                "sum": {"visits": 20 * n},
                "dimensions": {"date": day, "clientRequestHTTPHost": "glyphh.ai"},
            },
            {
                "count": 8 * n,
                "sum": {"visits": 2 * n},
                "dimensions": {"date": day, "clientRequestHTTPHost": "docs.glyphh.ai"},
            },
            # a scanner's Host headers: a port, capitals, and another site altogether
            {"count": 2 * n, "dimensions": {"date": day, "clientRequestHTTPHost": "Docs.glyphh.ai:8443"}},
            {"count": 4 * n, "dimensions": {"date": day, "clientRequestHTTPHost": "evil.ngrok-free.dev"}},
        ]

    def _rum(self, query: str, v: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.page_loads:
            return []
        dim = "requestPath" if "requestPath" in query else "refererHost"
        key = "/pricing" if dim == "requestPath" else "news.ycombinator.com"
        loads = {"date": self._day(v), "requestHost": "glyphh.ai", dim: key}
        return [{"count": 4, "dimensions": loads}, {"count": 1, "dimensions": {}}]

    def _answer(self, query: str, v: dict[str, Any]) -> dict[str, Any]:
        if "settings" in query:
            found = {"httpRequests1dGroups": self.daily_settings, "httpRequestsAdaptiveGroups": self.adaptive}
            return {"viewer": {"zones": [{"settings": found}]}}
        if "rumPageloadEventsAdaptiveGroups" in query:
            return {"viewer": {"accounts": [{"rumPageloadEventsAdaptiveGroups": self._rum(query, v)}]}}
        if "httpRequests1dGroups" in query:
            return {"viewer": {"zones": [{"httpRequests1dGroups": self._daily(v)}]}}
        return {"viewer": {"zones": [{"httpRequestsAdaptiveGroups": self._adaptive(query, v)}]}}

    @staticmethod
    def _dataset(query: str) -> str:
        """settings, rum, daily, pages, referrers or hosts."""
        names = {"settings": "settings", "rumPageload": "rum", "httpRequests1dGroups": "daily"}
        names |= {"clientRequestPath": "pages", "clientRefererHost": "referrers", "clientRequestReferer": "referrers"}
        return next((part for name, part in names.items() if name in query), "hosts")

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if self.status is not None:
            return httpx.Response(self.status, json={"success": False, "errors": [{"message": "Unauthorized"}]})
        if request.url.path == "/client/v4/zones":
            return self._zones(request)
        body = json.loads(request.content)
        query, v = body["query"], body["variables"]
        self.queries.append((query, v))
        refused = self.refuse.get(self._dataset(query))
        if refused:
            return httpx.Response(200, json={"data": None, "errors": [{"message": refused}]})
        return httpx.Response(200, json={"data": self._answer(query, v), "errors": None})


def cloudflare_http(fake: FakeCloudflare) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(fake.handle))
