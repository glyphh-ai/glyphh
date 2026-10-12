import { describe, expect, it } from "vitest";
import { Glyphh } from "../src/index.js";

const SERVER = "http://localhost:8080";
const FACE = { id: "s-1", name: "Clip Studio", avatar_variant: 7, avatar_color: "#FF8AD8" };
const ROW = { id: "t-1", machine_id: "m-1", goal: "YouTube to Instagram", status: "working", last_seq: 41,
  last_event_at: "2026-10-12T12:00:00Z", pinned_at: null, archived_at: null, created_at: "2026-10-12T11:00:00Z",
  super_power: FACE, crew: [], needs_you: 0 };
const QUESTION = { id: "q-1", thread_id: "t-1", thread_goal: "Launch note", machine_id: "m-1", machine_name: "studio-mac",
  super_power: null, kind: "permission", tool: "slack.post", detail: "Post in #launch", asked_at: "2026-10-12T12:00:00Z" };

function answering(body: unknown, seen: Request[], status = 200): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(new Request(input, init));
    return status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  };
}

const glyphh = (body: unknown, seen: Request[], status = 200) => new Glyphh({ baseUrl: SERVER, token: "t", fetch: answering(body, seen, status) });

describe("threads", () => {
  it("lists a machine's threads, searched, by a super power, archived, in pages", async () => {
    const seen: Request[] = [];
    const page = { machine: "studio-mac", threads: [ROW], total: 1, crew: [{ super_power: FACE, threads: 1 }] };
    expect(await glyphh(page, seen).threads.list("m-1")).toEqual(page);
    await glyphh(page, seen).threads.list("m-1", { q: "reels", superPower: "s-1", archived: true, page: 2, size: 10 });
    const [all, narrowed] = seen.map((r) => new URL(r.url));
    expect([all?.pathname, all?.search]).toEqual(["/v1/machines/m-1/threads", ""]);
    expect(narrowed?.search).toBe("?q=reels&archived=true&page=2&size=10&super_power=s-1");
  });

  it("opens, changes and deletes a thread", async () => {
    const seen: Request[] = [];
    const detail = { thread: ROW, machine: { id: "m-1", name: "studio-mac", online: false, last_seen_at: null }, questions: [QUESTION] };
    expect(await glyphh(detail, seen).threads.get("t-1")).toEqual(detail);
    expect(await glyphh(ROW, seen).threads.change("t-1", { pinned: true, goal: "Reels" })).toEqual(ROW);
    expect(await glyphh(null, seen, 204).threads.delete("t-1")).toBeUndefined();
    expect(seen.map((r) => `${r.method} ${new URL(r.url).pathname}`)).toEqual(["GET /v1/threads/t-1", "PATCH /v1/threads/t-1", "DELETE /v1/threads/t-1"]);
    expect(await seen[1]?.json()).toEqual({ pinned: true, goal: "Reels" });
  });
});

describe("needs you", () => {
  it("lists my open questions and answers one", async () => {
    const seen: Request[] = [];
    const page = { questions: [QUESTION], total: 1 };
    expect(await glyphh(page, seen).needsYou.list()).toEqual(page);
    await glyphh(page, seen).needsYou.list(2, 5);
    const answered = { id: "q-1", answer: "deny", answered_at: "2026-10-12T12:01:00Z" };
    expect(await glyphh(answered, seen).needsYou.answer("q-1", false)).toEqual(answered);
    expect(seen.map((r) => new URL(r.url).search).slice(0, 2)).toEqual(["?page=1&size=25", "?page=2&size=5"]);
    expect([seen[2]?.method, new URL(seen[2]!.url).pathname, await seen[2]?.json()]).toEqual(["POST", "/v1/needs-you/q-1/answer", { allow: false }]);
  });
});
