import { describe, expect, it } from "vitest";
import { Glyphh } from "../src/index.js";

const SERVER = "http://localhost:8080";

function answering(seen: Request[]): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  };
}

async function call(run: (g: Glyphh) => Promise<unknown>) {
  const seen: Request[] = [];
  await run(new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(seen) }));
  const sent = seen[0] as Request;
  const url = new URL(sent.url);
  return [sent.method, url.pathname, url.search, sent.method === "GET" ? null : await sent.text()];
}

describe("powers", () => {
  it("sends each powers call where the server expects it", async () => {
    const P = "p-1";
    expect(await Promise.all([
      call((g) => g.powers.providers("open")),
      call((g) => g.powers.catalogModels({ provider: "openai", q: "gpt" })),
      call((g) => g.powers.models()),
      call((g) => g.powers.addModel({ catalog_model_id: "c-1", api_key: "sk-1" })),
      call((g) => g.powers.replaceKey(P, "sk-2")),
      call((g) => g.powers.checkKey(P)),
      call((g) => g.powers.deleteModel(P)),
      call((g) => g.powers.services("gmail", "c1")),
      call((g) => g.powers.connections()),
      call((g) => g.powers.connect("gmail")),
      call((g) => g.powers.reconnect(P)),
      call((g) => g.powers.checkConnection(P)),
      call((g) => g.powers.disconnect(P)),
      call((g) => g.powers.tools(P, { q: "send" })),
      call((g) => g.powers.setTools(P, [{ tool: "gmail-send-email", permission: "allow" }])),
      call((g) => g.powers.loops()),
      call((g) => g.powers.folders()),
      call((g) => g.powers.addFolder({ machine_id: "m-1", path: "~/Content" })),
      call((g) => g.powers.removeFolder(P)),
      call((g) => g.powers.browsers()),
      call((g) => g.powers.addBrowser({ name: "Scout's", machine_id: "m-1", super_power_id: "s-1" })),
      call((g) => g.powers.deleteBrowser(P)),
      call((g) => g.powers.canAdd()),
    ])).toEqual([
      ["GET", "/v1/catalog/providers", "?q=open", null],
      ["GET", "/v1/catalog/models", "?provider=openai&q=gpt", null],
      ["GET", "/v1/powers/models", "", null],
      ["POST", "/v1/powers/models", "", '{"catalog_model_id":"c-1","api_key":"sk-1"}'],
      ["PUT", `/v1/powers/models/${P}/key`, "", '{"api_key":"sk-2"}'],
      ["POST", `/v1/powers/models/${P}/check`, "", ""],
      ["DELETE", `/v1/powers/models/${P}`, "", ""],
      ["GET", "/v1/catalog/services", "?q=gmail&after=c1&limit=25", null],
      ["GET", "/v1/powers/connections", "", null],
      ["POST", "/v1/powers/connections", "", '{"service":"gmail"}'],
      ["POST", `/v1/powers/connections/${P}/link`, "", ""],
      ["POST", `/v1/powers/connections/${P}/check`, "", ""],
      ["DELETE", `/v1/powers/connections/${P}`, "", ""],
      ["GET", `/v1/powers/connections/${P}/tools`, "?q=send", null],
      ["PATCH", `/v1/powers/connections/${P}/tools`, "", '{"changes":[{"tool":"gmail-send-email","permission":"allow"}]}'],
      ["GET", "/v1/powers/loops", "", null],
      ["GET", "/v1/powers/folders", "", null],
      ["POST", "/v1/powers/folders", "", '{"machine_id":"m-1","path":"~/Content"}'],
      ["DELETE", `/v1/powers/folders/${P}`, "", ""],
      ["GET", "/v1/powers/browsers", "", null],
      ["POST", "/v1/powers/browsers", "", '{"name":"Scout\'s","machine_id":"m-1","super_power_id":"s-1"}'],
      ["DELETE", `/v1/powers/browsers/${P}`, "", ""],
      ["GET", "/v1/powers/can-add", "", null],
    ]);
  });

  it("uses the defaults when nothing is given", async () => {
    expect(await call((g) => g.powers.providers())).toEqual(["GET", "/v1/catalog/providers", "?q=", null]);
    expect(await call((g) => g.powers.catalogModels())).toEqual(["GET", "/v1/catalog/models", "", null]);
    expect(await call((g) => g.powers.services())).toEqual(["GET", "/v1/catalog/services", "?q=&limit=25", null]);
    expect(await call((g) => g.powers.tools("p-1"))).toEqual(["GET", "/v1/powers/connections/p-1/tools", "", null]);
  });
});
