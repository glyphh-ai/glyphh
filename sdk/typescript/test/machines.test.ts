import { describe, expect, it } from "vitest";
import { Glyphh } from "../src/index.js";

const SERVER = "http://localhost:8080";
const FACE = { id: "s-1", name: "Inbox Zero", description: "Sorts your email", avatar_variant: 3, avatar_color: "#B49CFF", status: "working", last_active_at: null };
const PAGE = { machines: [{ id: "m-1", name: "studio-mac", host: "fly", platform: "macos", version: "1.0.0", online: true, last_seen_at: null,
  super_powers: [FACE], installed: 1, working: 1, needs_you: 0 }], total: 1, online: 1 };

function answering(body: unknown, seen: Request[]): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  };
}

const glyphh = (body: unknown, seen: Request[]) => new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(body, seen) });

describe("machines", () => {
  it("lists my machines a page at a time", async () => {
    const seen: Request[] = [];
    expect(await glyphh(PAGE, seen).machines.list()).toEqual(PAGE);
    await glyphh(PAGE, seen).machines.list(2, 6);
    expect(seen.map((r) => new URL(r.url).search)).toEqual(["?page=1&size=12", "?page=2&size=6"]);
  });

  it("lists, searches and filters a machine's super powers", async () => {
    const seen: Request[] = [];
    const page = { machine: "studio-mac", super_powers: [FACE], total: 1, counts: { all: 1 } };
    expect(await glyphh(page, seen).machines.superPowers("m-1")).toEqual(page);
    await glyphh(page, seen).machines.superPowers("m-1", { q: "rev", status: "needs_you", page: 2, size: 24 });
    const [all, filtered] = seen.map((r) => new URL(r.url));
    expect([all?.pathname, all?.search, filtered?.search]).toEqual(["/v1/machines/m-1/super-powers", "", "?q=rev&status=needs_you&page=2&size=24"]);
  });

  it("opens a machine on its home or one of its super powers", async () => {
    const seen: Request[] = [];
    const launch = { url: "http://platform.test/machines/m-1", ticket: "x", page: "machine", expires_at: "2026-10-12T12:01:00Z" };
    expect(await glyphh(launch, seen).machines.open("m-1")).toEqual(launch);
    await glyphh(launch, seen).machines.open("m-1", "s-1");
    expect(await Promise.all(seen.map((r) => r.json()))).toEqual([{ super_power: null }, { super_power: "s-1" }]);
  });

  it("turns a machine's shell on and removes a machine", async () => {
    const seen: Request[] = [];
    await glyphh(PAGE.machines[0], seen).machines.setShell("m-1", true);
    await glyphh(null, seen).machines.remove("m-1");
    expect(seen.map((r) => [r.method, new URL(r.url).pathname])).toEqual([["PATCH", "/v1/machines/m-1"], ["DELETE", "/v1/machines/m-1"]]);
  });
});

describe("settings", () => {
  it("reads and changes what the platform remembers for me", async () => {
    const seen: Request[] = [];
    const settings = { theme: "light", rail_collapsed: true, page_sizes: { members: 25 } };
    expect(await glyphh(settings, seen).settings()).toEqual(settings);
    expect(await glyphh(settings, seen).changeSettings({ theme: "light" })).toEqual(settings);
    expect([seen[1]?.method, await seen[1]?.json()]).toEqual(["PATCH", { theme: "light" }]);
  });
});

describe("hosting", () => {
  it("keeps my Fly account and deploys, reads, wakes, moves and destroys a machine there", async () => {
    const seen: Request[] = [];
    const hosted = { id: "h-1", host: "fly", name: "attic", region: "iad", app: "glyphh-attic-a1b2c3", image: "rrotor:latest", state: "waiting",
      host_state: "created", machine_id: null, created_at: "2026-10-12T12:00:00Z" };
    const g = (body: unknown) => glyphh(body, seen).hosting;
    await g({ id: "a-1", host: "fly", account: "personal", token_last4: "abcd", checked_at: null, updated_at: "x" }).saveAccount("FlyV1 fm2_x");
    await g({}).account();
    await g(null).removeAccount();
    expect(await g(hosted).deploy("attic")).toEqual(hosted);
    await g([hosted]).list();
    await g(hosted).get("h-1");
    await g(hosted).start("h-1");
    await g(hosted).update("h-1");
    await g(hosted).update("h-1", "rrotor:1.2");
    await g(null).destroy("h-1");
    expect(seen.map((r) => `${r.method} ${new URL(r.url).pathname}`)).toEqual([
      "PUT /v1/hosts/fly/account", "GET /v1/hosts/fly/account", "DELETE /v1/hosts/fly/account", "POST /v1/hosted-machines",
      "GET /v1/hosted-machines", "GET /v1/hosted-machines/h-1", "POST /v1/hosted-machines/h-1/start",
      "POST /v1/hosted-machines/h-1/update", "POST /v1/hosted-machines/h-1/update", "DELETE /v1/hosted-machines/h-1",
    ]);
    const bodies = await Promise.all([seen[0], seen[3], seen[7], seen[8]].map((r) => r?.json()));
    expect(bodies).toEqual([{ token: "FlyV1 fm2_x", account: "personal" }, { name: "attic", region: "iad" }, { image: null }, { image: "rrotor:1.2" }]);
  });
});
