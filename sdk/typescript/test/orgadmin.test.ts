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

describe("org admin and API keys", () => {
  it("sends each call where the server expects it", async () => {
    expect(await Promise.all([
      call((g) => g.orgAdmin.people({ q: "bo", team: ["t", "none"] })), call((g) => g.orgAdmin.inviteMany({ emails: ["a@x.test"] })),
      call((g) => g.orgAdmin.teams()), call((g) => g.orgAdmin.team("t")), call((g) => g.orgAdmin.createTeam("Design")),
      call((g) => g.orgAdmin.changeTeam("t", { limit_models: true })), call((g) => g.orgAdmin.deleteTeam("t")),
      call((g) => g.orgAdmin.addToTeam("t", ["u"])), call((g) => g.orgAdmin.removeFromTeam("t", "u")),
      call((g) => g.orgAdmin.memberTeams("u")), call((g) => g.orgAdmin.setMemberTeams("u", ["t"])),
      call((g) => g.orgAdmin.limits("models", { team: "t" })), call((g) => g.orgAdmin.limitImpact("connections")),
      call((g) => g.orgAdmin.setLimit("models", true, "t")), call((g) => g.orgAdmin.addLimitEntries("connections", ["gmail"])),
      call((g) => g.orgAdmin.removeLimitEntries("connections", ["gmail"], "t")),
      call((g) => g.orgAdmin.auditLog({ type: "glyphh", page: 2 })), call((g) => g.orgAdmin.exportAuditLog({ type: "keys" })),
      call((g) => g.apiKeys.mine()), call((g) => g.apiKeys.make({ name: "CI", expires: "never" })), call((g) => g.apiKeys.revoke("k")),
      call((g) => g.apiKeys.org({ owner: "u" })), call((g) => g.apiKeys.makers("bo")), call((g) => g.apiKeys.memberKeys()),
      call((g) => g.apiKeys.setMemberKeys(false)),
    ])).toEqual([
      ["GET", "/v1/org/people?q=bo&team=t&team=none"], ["POST", "/v1/org/invites/many"],
      ["GET", "/v1/org/teams"], ["GET", "/v1/org/teams/t"], ["POST", "/v1/org/teams"],
      ["PATCH", "/v1/org/teams/t"], ["DELETE", "/v1/org/teams/t"],
      ["POST", "/v1/org/teams/t/members"], ["DELETE", "/v1/org/teams/t/members/u"],
      ["GET", "/v1/org/members/u/teams"], ["PUT", "/v1/org/members/u/teams"],
      ["GET", "/v1/org/limits/models?team=t"], ["GET", "/v1/org/limits/connections/impact"],
      ["PUT", "/v1/org/limits/models/switch?team=t"], ["POST", "/v1/org/limits/connections/entries"],
      ["POST", "/v1/org/limits/connections/entries/remove?team=t"],
      ["GET", "/v1/org/audit?type=glyphh&page=2"], ["GET", "/v1/org/audit.csv?type=keys"],
      ["GET", "/v1/me/api-keys"], ["POST", "/v1/me/api-keys"], ["POST", "/v1/api-keys/k/revoke"],
      ["GET", "/v1/org/api-keys?owner=u"], ["GET", "/v1/org/api-keys/makers?q=bo"], ["GET", "/v1/org/api-keys/member-keys"],
      ["PUT", "/v1/org/api-keys/member-keys"],
    ]);
  });
});
