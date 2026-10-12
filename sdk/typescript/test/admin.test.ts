import { describe, expect, it } from "vitest";
import { Glyphh } from "../src/index.js";

const SERVER = "http://localhost:8080";

async function call(run: (g: Glyphh) => Promise<unknown>) {
  const seen: Request[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    seen.push(new Request(input, init));
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  };
  await run(new Glyphh({ baseUrl: SERVER, token: "t", fetch: fetcher }));
  const sent = seen[0] as Request;
  const url = new URL(sent.url);
  return [sent.method, url.pathname + url.search];
}

const ORG = "/v1/admin/orgs/o";

describe("admin", () => {
  it("sends each org and plan call where the server expects it", async () => {
    expect(await Promise.all([
      call((g) => g.admin.orgs({ q: "acme", state: "disabled" })), call((g) => g.admin.org("o")), call((g) => g.admin.members("o", { q: "a" })),
      call((g) => g.admin.machines("o")), call((g) => g.admin.powers("o", { kind: "skill" })), call((g) => g.admin.superPowers("o")),
      call((g) => g.admin.ledger("o", { page: 2 })), call((g) => g.admin.gift("o", 500, "hi")), call((g) => g.admin.comp("o", "p")),
      call((g) => g.admin.endComp("o")), call((g) => g.admin.move("o", "p")), call((g) => g.admin.disable("o", "why")),
      call((g) => g.admin.enable("o")), call((g) => g.admin.plans()),
      call((g) => g.admin.nextVersion("Solo", { price_cents: 0, monthly_credit_cents: 0 })), call((g) => g.admin.moveOrgs("p")),
      call((g) => g.admin.billingSettings()),
      call((g) => g.admin.setBillingSettings({ call_cents: 2, seconds_per_charge: 30, top_up_min_cents: 500, top_up_max_cents: 1000 })),
      call((g) => g.admin.orgs()),
    ])).toEqual([
      ["GET", "/v1/admin/orgs?q=acme&state=disabled"], ["GET", ORG], ["GET", `${ORG}/members?q=a`], ["GET", `${ORG}/machines`],
      ["GET", `${ORG}/powers?kind=skill`], ["GET", `${ORG}/super-powers`], ["GET", `${ORG}/ledger?page=2`], ["POST", `${ORG}/gift`],
      ["POST", `${ORG}/comp`], ["DELETE", `${ORG}/comp`], ["POST", `${ORG}/move`], ["POST", `${ORG}/disable`], ["POST", `${ORG}/enable`],
      ["GET", "/v1/admin/plans"], ["POST", "/v1/admin/plans/Solo"], ["POST", "/v1/admin/plans/p/move"], ["GET", "/v1/admin/billing-settings"],
      ["POST", "/v1/admin/billing-settings"], ["GET", "/v1/admin/orgs"],
    ]);
  });

  it("sends each catalog, marketplace and audit call where the server expects it", async () => {
    const logo = { data: new Blob(["x"]), type: "image/png" as const };
    expect(await Promise.all([
      call((g) => g.admin.catalog.providers({ state: "off" })), call((g) => g.admin.catalog.addProvider({ slug: "a", name: "A" })),
      call((g) => g.admin.catalog.changeProvider("p", { active: false })), call((g) => g.admin.catalog.removeProvider("p")),
      call((g) => g.admin.catalog.importModels("p", "sk")), call((g) => g.admin.catalog.setLogo("p", logo, true)),
      call((g) => g.admin.catalog.setLogo("p", { ...logo, name: "a.png" })),
      call((g) => g.admin.catalog.models({ no_description: true })), call((g) => g.admin.catalog.addModel({ provider_id: "p", model: "m", name: "M" })),
      call((g) => g.admin.catalog.changeModel("m", { active: true })), call((g) => g.admin.catalog.removeModel("m")),
      call((g) => g.admin.market.listings({ state: "featured" })), call((g) => g.admin.market.setFeatured(["l"])),
      call((g) => g.admin.market.report("v", { ok: true })), call((g) => g.admin.market.categories()), call((g) => g.admin.market.addCategory("A")),
      call((g) => g.admin.market.renameCategory("c", "B")), call((g) => g.admin.market.deleteCategory("c")),
      call((g) => g.admin.market.orderCategories(["c"])), call((g) => g.admin.market.audit({ org: "o" })),
      call((g) => g.admin.market.exportAudit({ type: "plans" })), call((g) => g.admin.catalog.providers()), call((g) => g.admin.catalog.models()),
      call((g) => g.admin.market.listings()), call((g) => g.admin.market.audit()), call((g) => g.admin.market.exportAudit()),
    ])).toEqual([
      ["GET", "/v1/admin/providers?state=off"], ["POST", "/v1/admin/providers"], ["PATCH", "/v1/admin/providers/p"],
      ["DELETE", "/v1/admin/providers/p"], ["POST", "/v1/admin/providers/p/import"], ["PUT", "/v1/admin/providers/p/logo?dark=true"],
      ["PUT", "/v1/admin/providers/p/logo?dark=false"],
      ["GET", "/v1/admin/catalog-models?no_description=true"], ["POST", "/v1/admin/catalog-models"], ["PATCH", "/v1/admin/catalog-models/m"],
      ["DELETE", "/v1/admin/catalog-models/m"], ["GET", "/v1/admin/listings?state=featured"], ["PUT", "/v1/admin/featured"],
      ["PUT", "/v1/admin/reviews/v/report"], ["GET", "/v1/admin/categories"], ["POST", "/v1/admin/categories"],
      ["PATCH", "/v1/admin/categories/c"], ["DELETE", "/v1/admin/categories/c"], ["PUT", "/v1/admin/categories"],
      ["GET", "/v1/admin/audit?org=o"], ["GET", "/v1/admin/audit.csv?type=plans"], ["GET", "/v1/admin/providers"],
      ["GET", "/v1/admin/catalog-models"], ["GET", "/v1/admin/listings"], ["GET", "/v1/admin/audit"], ["GET", "/v1/admin/audit.csv"],
    ]);
  });
});
