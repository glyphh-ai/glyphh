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
  return [sent.method, url.pathname + url.search, sent.headers.get("content-type")];
}

describe("listings and the marketplace", () => {
  it("sends each call where the server expects it", async () => {
    const png = { data: new Blob([new Uint8Array([137, 80])]), type: "image/png" as const, name: "icon.png" };
    expect(await Promise.all([
      call((g) => g.listings.mine()), call((g) => g.listings.create({ power_id: "p" })), call((g) => g.listings.get("l")),
      call((g) => g.listings.change("l", { summary: "s" })), call((g) => g.listings.changeVersion("l", { version: "1.1.0" })),
      call((g) => g.listings.setIcon("l", png)), call((g) => g.listings.addScreenshot("l", { ...png, type: "image/jpeg" })),
      call((g) => g.listings.orderScreenshots("l", ["a"])), call((g) => g.listings.removeScreenshot("l", "a")),
      call((g) => g.listings.submit("l")), call((g) => g.listings.withdraw("l")), call((g) => g.listings.unpublish("l")),
      call((g) => g.listings.comments("l")), call((g) => g.listings.comment("l", "hi")), call((g) => g.listings.queue()),
      call((g) => g.listings.decide("v", { decision: "approved" })),
      call((g) => g.marketplace.home("custom")), call((g) => g.marketplace.browse({ q: "rev" })), call((g) => g.marketplace.get("l")),
      call((g) => g.marketplace.add("l")), call((g) => g.marketplace.update("p")),
    ])).toEqual([
      ["GET", "/v1/listings", null], ["POST", "/v1/listings", "application/json"], ["GET", "/v1/listings/l", null],
      ["PATCH", "/v1/listings/l", "application/json"], ["PATCH", "/v1/listings/l/version", "application/json"],
      ["PUT", "/v1/listings/l/icon", "image/png"], ["POST", "/v1/listings/l/screenshots", "image/jpeg"],
      ["PUT", "/v1/listings/l/screenshots", "application/json"], ["DELETE", "/v1/listings/l/screenshots/a", null],
      ["POST", "/v1/listings/l/submit", null], ["POST", "/v1/listings/l/withdraw", null], ["POST", "/v1/listings/l/unpublish", null],
      ["GET", "/v1/listings/l/comments", null], ["POST", "/v1/listings/l/comments", "application/json"], ["GET", "/v1/reviews?step=org", null],
      ["POST", "/v1/reviews/v", "application/json"],
      ["GET", "/v1/marketplace/home?kind=custom", null], ["GET", "/v1/marketplace?q=rev", null], ["GET", "/v1/marketplace/l", null],
      ["POST", "/v1/marketplace/l/add", null], ["POST", "/v1/powers/custom/p/update", null],
    ]);
  });
});
