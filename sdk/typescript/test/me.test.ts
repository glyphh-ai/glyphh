import { describe, expect, it } from "vitest";
import { Glyphh, GlyphhError } from "../src/index.js";

const SERVER = process.env.GLYPHH_URL ?? "http://localhost:8080";

const ME = {
  id: "7f0c7b1e-0000-4000-8000-000000000001", email: "ada@acme.test", first_name: "Ada", last_name: "Lovelace",
  image_url: null, role: "org_admin", org: { id: "7f0c7b1e-0000-4000-8000-000000000002", name: "Acme", plan: "Free", personal: false, role: "org_admin" },
};
const HOST = { id: "7f0c7b1e-0000-4000-8000-000000000003", name: "Claude Code", connected_at: "2026-10-11T12:00:00Z" };

function answering(status: number, body?: unknown, seen: Request[] = []): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return body === undefined
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  };
}

describe("me and hosts", () => {
  it("refuses without a token, with the server's code and trace id", async () => {
    const error = await new Glyphh({ baseUrl: SERVER }).me().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(GlyphhError);
    expect(error).toMatchObject({ status: 401, code: "E_UNAUTHORIZED", traceId: expect.any(String) });
    expect((error as GlyphhError).message).toContain("Sign in");
  });

  it("sends the token and reads me", async () => {
    const seen: Request[] = [];
    const glyphh = new Glyphh({ baseUrl: SERVER, token: "tok-1", fetch: answering(200, ME, seen) });
    expect(await glyphh.me()).toEqual(ME);
    expect(seen[0]?.headers.get("authorization")).toBe("Bearer tok-1");
  });

  it("takes the token from GLYPHH_TOKEN", async () => {
    const seen: Request[] = [];
    process.env.GLYPHH_TOKEN = "tok-env";
    try {
      await new Glyphh({ baseUrl: SERVER, fetch: answering(200, [HOST], seen) }).listHosts();
    } finally {
      delete process.env.GLYPHH_TOKEN;
    }
    expect(seen[0]?.headers.get("authorization")).toBe("Bearer tok-env");
  });

  it("lists and disconnects hosts", async () => {
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, [HOST]) }).listHosts()).toEqual([HOST]);
    const seen: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(204, undefined, seen) }).disconnectHost(HOST.id);
    expect(seen[0]?.method).toBe("DELETE");
    expect(new URL(seen[0]?.url ?? "").pathname).toBe(`/v1/me/hosts/${HOST.id}`);
  });

  it("keeps a refusal that is not the server's shape as its body", async () => {
    const error = await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(502, { error: "gateway" }) })
      .me()
      .catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 502, code: undefined, traceId: undefined, body: { error: "gateway" } });
  });

  it("lists my orgs, and accepts or declines an invite sent to me", async () => {
    const orgs = [{ ...ME.org, name: "Personal", personal: true }, ME.org];
    expect(await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, orgs) }).listMyOrgs()).toEqual(orgs);
    const accepted: Request[] = [];
    const joined = await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(200, { org: "Acme" }, accepted) }).acceptInvite("I1");
    expect(joined).toBe("Acme");
    expect([accepted[0]?.method, new URL(accepted[0]?.url ?? "").pathname, await accepted[0]?.text()]).toEqual(["POST", "/v1/invites/accept", '{"invite":"I1"}']);
    const declined: Request[] = [];
    await new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(204, undefined, declined) }).declineInvite("I2");
    expect(new URL(declined[0]?.url ?? "").pathname).toBe("/v1/invites/decline");
  });
});
