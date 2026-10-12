import { describe, expect, it } from "vitest";
import { Glyphh } from "../src/index.js";

const SERVER = "http://localhost:8080";

function answering(body: unknown, seen: Request[], status = 200): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  };
}

const glyphh = (body: unknown, seen: Request[], status = 200) =>
  new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(body, seen, status) });

async function call(name: string, run: (g: Glyphh) => Promise<unknown>, body: unknown = { ok: true }) {
  const seen: Request[] = [];
  const answer = await run(glyphh(body, seen));
  const sent = seen[0] as Request;
  const url = new URL(sent.url);
  return { name, answer, method: sent.method, path: url.pathname, search: url.search, body: sent.method === "GET" ? null : await sent.text() };
}

describe("billing", () => {
  it("sends each billing call where the server expects it", async () => {
    const calls = await Promise.all([
      call("plans", (g) => g.billing.plans()),
      call("credit", (g) => g.billing.credit()),
      call("get", (g) => g.billing.get()),
      call("addFunds", (g) => g.billing.addFunds(4500)),
      call("topUps", (g) => g.billing.topUps()),
      call("setAutoTopUp", (g) => g.billing.setAutoTopUp({ on: true, below_cents: 500, to_cents: 2500 })),
      call("checkAutoTopUp", (g) => g.billing.checkAutoTopUp()),
      call("setUpCard", (g) => g.billing.setUpCard()),
      call("previewPlan", (g) => g.billing.previewPlan("p-1")),
      call("changePlan", (g) => g.billing.changePlan("p-1")),
      call("sync", (g) => g.billing.sync()),
      call("ledger", (g) => g.billing.ledger(2, 10)),
      call("spendByDay", (g) => g.billing.spendByDay()),
      call("invoices", (g) => g.billing.invoices("in_1", 10)),
      call("nextInvoice", (g) => g.billing.nextInvoice()),
      call("portal", (g) => g.billing.portal()),
    ]);
    expect(calls.map((c) => [c.name, c.method, c.path, c.search, c.body])).toEqual([
      ["plans", "GET", "/v1/plans", "", null],
      ["credit", "GET", "/v1/org/credit", "", null],
      ["get", "GET", "/v1/org/billing", "", null],
      ["addFunds", "POST", "/v1/org/billing/top-ups", "", '{"amount_cents":4500}'],
      ["topUps", "GET", "/v1/org/billing/top-ups", "?page=1&size=25", null],
      ["setAutoTopUp", "PUT", "/v1/org/billing/auto-top-up", "", '{"on":true,"below_cents":500,"to_cents":2500}'],
      ["checkAutoTopUp", "POST", "/v1/org/billing/auto-top-up/check", "", ""],
      ["setUpCard", "POST", "/v1/org/billing/card", "", ""],
      ["previewPlan", "POST", "/v1/org/billing/plan/preview", "", '{"plan_id":"p-1"}'],
      ["changePlan", "POST", "/v1/org/billing/plan", "", '{"plan_id":"p-1"}'],
      ["sync", "POST", "/v1/org/billing/sync", "", ""],
      ["ledger", "GET", "/v1/org/billing/ledger", "?page=2&size=10", null],
      ["spendByDay", "GET", "/v1/org/billing/spend", "", null],
      ["invoices", "GET", "/v1/org/billing/invoices", "?after=in_1&limit=10", null],
      ["nextInvoice", "GET", "/v1/org/billing/next-invoice", "", null],
      ["portal", "POST", "/v1/org/billing/portal", "", ""],
    ]);
    expect(calls.every((c) => JSON.stringify(c.answer) === '{"ok":true}')).toBe(true);
  });

  it("answers null when there is no next invoice, and refuses with the server's code", async () => {
    expect(await glyphh(null, []).billing.nextInvoice()).toBeNull();
    const refused = await glyphh({ error: { code: "E_FORBIDDEN", message: "Only an org admin can do that.", trace_id: "t1" } }, [], 403)
      .billing.get()
      .catch((e: unknown) => e);
    expect(refused).toMatchObject({ status: 403, code: "E_FORBIDDEN", traceId: "t1" });
  });
});
