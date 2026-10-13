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
  const url = new URL((seen[0] as Request).url);
  return [(seen[0] as Request).method, url.pathname + url.search];
}

describe("super powers, custom powers and schedules", () => {
  it("sends each call where the server expects it", async () => {
    const flow = { nodes: [{ id: "t", kind: "trigger" as const, label: "8am" }], edges: [] };
    const schedule = { power_id: "p", machine_id: "m", name: "W", cron: "0 8 * * 1-5" };
    expect(await Promise.all([
      call((g) => g.superPowers.list({ status: "working" })), call((g) => g.superPowers.list()),
      call((g) => g.superPowers.create({ name: "Scout", instructions: "Find leads." })), call((g) => g.superPowers.glyphh()),
      call((g) => g.superPowers.get("s")), call((g) => g.superPowers.change("s", { personality: 5 })),
      call((g) => g.superPowers.delete("s")), call((g) => g.superPowers.grant("s", { machine_id: "m" })),
      call((g) => g.superPowers.setLoop("s", { engine: "glyphh", model_id: "m" })),
      call((g) => g.custom.list({ kind: "skill" })), call((g) => g.custom.list()),
      call((g) => g.custom.create({ kind: "task", name: "B" })), call((g) => g.custom.get("p")),
      call((g) => g.custom.change("p", { description: "x" })), call((g) => g.custom.delete("p")),
      call((g) => g.custom.readFile("p", "SKILL.md")), call((g) => g.custom.writeFile("p", { path: "SKILL.md", content: "#" })),
      call((g) => g.custom.deleteFile("p", "a.md")), call((g) => g.custom.saveFlow("p", flow)),
      call((g) => g.custom.slots("p")), call((g) => g.custom.setSlots("p", { slots: [{ name: "main" }] })),
      call((g) => g.schedules.list("p")), call((g) => g.schedules.list()), call((g) => g.schedules.add(schedule)),
      call((g) => g.schedules.change("x", schedule)), call((g) => g.schedules.delete("x")),
      call((g) => g.schedules.runNow("x")), call((g) => g.schedules.runs({ status: "failed" })), call((g) => g.schedules.runs()),
      call((g) => g.schedules.run("r")), call((g) => g.schedules.run("r", "org")), call((g) => g.schedules.cancelRun("r")),
    ])).toEqual([
      ["GET", "/v1/super-powers?status=working"], ["GET", "/v1/super-powers"], ["POST", "/v1/super-powers"],
      ["GET", "/v1/super-powers/glyphh"], ["GET", "/v1/super-powers/s"], ["PATCH", "/v1/super-powers/s"],
      ["DELETE", "/v1/super-powers/s"], ["PUT", "/v1/super-powers/s/grants"], ["PUT", "/v1/super-powers/s/loop"],
      ["GET", "/v1/powers/custom?kind=skill"], ["GET", "/v1/powers/custom"], ["POST", "/v1/powers/custom"],
      ["GET", "/v1/powers/custom/p"], ["PATCH", "/v1/powers/custom/p"], ["DELETE", "/v1/powers/custom/p"],
      ["GET", "/v1/powers/custom/p/file?path=SKILL.md"], ["PUT", "/v1/powers/custom/p/file"],
      ["DELETE", "/v1/powers/custom/p/file?path=a.md"], ["PUT", "/v1/powers/custom/p/flow"],
      ["GET", "/v1/powers/custom/p/slots"], ["PUT", "/v1/powers/custom/p/slots"],
      ["GET", "/v1/schedules?target=p"], ["GET", "/v1/schedules"], ["POST", "/v1/schedules"],
      ["PUT", "/v1/schedules/x"], ["DELETE", "/v1/schedules/x"],
      ["POST", "/v1/schedules/x/run"], ["GET", "/v1/runs?status=failed"], ["GET", "/v1/runs"],
      ["GET", "/v1/runs/r?scope=me"], ["GET", "/v1/runs/r?scope=org"], ["POST", "/v1/runs/r/cancel"],
    ]);
  });
});
