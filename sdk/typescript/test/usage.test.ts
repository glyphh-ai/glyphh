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

describe("usage", () => {
  it("sends each call where the server expects it", async () => {
    expect(await Promise.all([
      call((g) => g.usage.page({ scope: "org", teams: ["t"] })), call((g) => g.usage.by("models")), call((g) => g.usage.runs({ super_power: "s" })),
      call((g) => g.usage.periods()), call((g) => g.usage.calls({ status: "error", after: "c" })), call((g) => g.usage.call("c1", "org")),
      call((g) => g.usage.exportCalls({ tool: "x" })), call((g) => g.usage.uses({ kind: "model_call" })), call((g) => g.usage.use("u1")),
      call((g) => g.usage.exportUses()), call((g) => g.usage.listingStats("l", 7)),
    ])).toEqual([
      ["GET", "/v1/usage?scope=org&teams=t"], ["GET", "/v1/usage/by/models"], ["GET", "/v1/usage/runs?super_power=s"],
      ["GET", "/v1/usage/periods"], ["GET", "/v1/usage/calls?status=error&after=c"], ["GET", "/v1/usage/calls/c1?scope=org"],
      ["GET", "/v1/usage/calls.csv?tool=x"], ["GET", "/v1/usage/uses?kind=model_call"], ["GET", "/v1/usage/uses/u1?scope=me"],
      ["GET", "/v1/usage/uses.csv"], ["GET", "/v1/listings/l/stats?days=7"],
    ]);
  });
});
