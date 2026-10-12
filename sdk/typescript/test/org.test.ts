import { describe, expect, it } from "vitest";
import { Glyphh, GlyphhError } from "../src/index.js";

const SERVER = process.env.GLYPHH_URL ?? "http://localhost:8080";
const ORG = { id: "o-1", name: "Acme", plan: "Pro", seats_taken: 3, max_seats: 100 };
const MEMBER = { id: "m-1", email: "ada@acme.test", first_name: "Ada", last_name: null, role: "user", disabled: false,
  joined_at: "2026-10-11T12:00:00Z" };
const INVITE = { id: "i-1", email: "new@acme.test", role: "user", expires_at: "2026-10-18T12:00:00Z" };

function answering(status: number, body?: unknown, seen: Request[] = []): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return body === undefined ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  };
}

async function sent(seen: Request[]): Promise<{ method: string; path: string; body: unknown }> {
  const r = seen[0] as Request;
  const text = await r.text();
  return { method: r.method, path: new URL(r.url).pathname, body: text ? JSON.parse(text) : undefined };
}

describe("org", () => {
  it("refuses without a token, from the real server", async () => {
    const error = await new Glyphh({ baseUrl: SERVER }).org.get().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(GlyphhError);
    expect(error).toMatchObject({ status: 401, code: "E_UNAUTHORIZED" });
  });

  it("reads and renames the org", async () => {
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, ORG) }).org.get()).toEqual(ORG);
    const seen: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, ORG, seen) }).org.rename("Acme Inc");
    expect(await sent(seen)).toEqual({ method: "PATCH", path: "/v1/org", body: { name: "Acme Inc" } });
  });

  it("lists, changes and removes members", async () => {
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, [MEMBER]) }).org.listMembers()).toEqual([MEMBER]);
    const changed: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, MEMBER, changed) }).org.updateMember("m-1", { disabled: true });
    expect(await sent(changed)).toEqual({ method: "PATCH", path: "/v1/org/members/m-1", body: { disabled: true } });
    const removed: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(204, undefined, removed) }).org.removeMember("m-1");
    expect((await sent(removed)).method).toBe("DELETE");
  });

  it("invites, lists and withdraws", async () => {
    const made: Request[] = [];
    const created = { invite: INVITE, link: "https://app.glyphh.ai/join?invite=x" };
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(201, created, made) }).org.invite("new@acme.test"))
      .toEqual(created);
    expect(await sent(made)).toEqual({ method: "POST", path: "/v1/org/invites", body: { email: "new@acme.test", role: "user" } });
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, [INVITE]) }).org.listInvites()).toEqual([INVITE]);
    const gone: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(204, undefined, gone) }).org.revokeInvite("i-1");
    expect(await sent(gone)).toEqual({ method: "DELETE", path: "/v1/org/invites/i-1", body: undefined });
  });

  it("an over-the-seats invite is an E_LIMIT error", async () => {
    const limit = { error: { code: "E_LIMIT", message: "Your plan's seats are all taken.", trace_id: "t-1", limit: "seats" } };
    const error = await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(403, limit) }).org.invite("x@y.test", "org_admin")
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 403, code: "E_LIMIT", traceId: "t-1" });
  });
});
