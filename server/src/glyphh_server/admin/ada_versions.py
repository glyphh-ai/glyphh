"""Models by Ada version (docs/specs/ada-cloud.md, 12), for staff: each live model's active version names the Ada
version and kernel it runs (admin/adascan.py reads them where an org's schema has them); grouped, with how many orgs
and precedents each carries. Until Ada versions reach an org's schema its models count under `null`."""

from pydantic import BaseModel, Field

from glyphh_server.admin import adascan


class AdaVersionRow(BaseModel):
    ada: str | None = Field(description="The Ada version; null: made before Ada versions")
    kernels: list[str]
    models: int
    orgs: int
    precedents: int


class AdaVersions(BaseModel):
    versioned: bool = Field(description="Some model names its Ada version: Ada versions have reached the cloud")
    versions: list[AdaVersionRow]


def by_version(found: list[adascan.OrgAda]) -> AdaVersions:
    groups: dict[str | None, list[tuple[adascan.OrgAda, adascan.AdaModel]]] = {}
    for org in found:
        for model in org.live:
            groups.setdefault(model.ada, []).append((org, model))
    rows = [
        AdaVersionRow(
            ada=name,
            kernels=sorted({m.kernel for _, m in held if m.kernel}),
            models=len(held),
            orgs=len({o.org_id for o, _ in held}),
            precedents=sum(m.precedents for _, m in held),
        )
        for name, held in groups.items()
    ]
    rows.sort(key=lambda r: (r.ada is None, r.ada or ""), reverse=False)
    return AdaVersions(versioned=any(r.ada is not None for r in rows), versions=rows)
