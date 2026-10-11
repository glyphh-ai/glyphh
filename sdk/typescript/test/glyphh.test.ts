import { afterEach, describe, expect, it } from "vitest";
import { Glyphh, GlyphhError } from "../src/index.js";

const SERVER = process.env.GLYPHH_URL ?? "http://localhost:8080";

describe("health", () => {
  it("answers from the real server", async () => {
    const health = await new Glyphh({ baseUrl: SERVER }).health();
    expect(health).toEqual({ status: "ok", version: expect.any(String), database: true });
  });

  it("throws a GlyphhError with the status when the server refuses", async () => {
    const refusing = async () => new Response(JSON.stringify({ detail: "down" }), { status: 503, headers: { "content-type": "application/json" } });
    const error = await new Glyphh({ baseUrl: SERVER, fetch: refusing }).health().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(GlyphhError);
    expect(error).toMatchObject({ status: 503, body: { detail: "down" }, name: "GlyphhError" });
  });

  it("throws a GlyphhError with status 0 when the server can't be reached", async () => {
    const unreachable = async () => {
      throw new TypeError("fetch failed");
    };
    const error = await new Glyphh({ baseUrl: SERVER, fetch: unreachable }).health().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(GlyphhError);
    expect(error).toMatchObject({ status: 0 });
  });
});

describe("the server address", () => {
  const before = process.env.GLYPHH_URL;
  afterEach(() => {
    if (before === undefined) delete process.env.GLYPHH_URL;
    else process.env.GLYPHH_URL = before;
  });

  it("comes from GLYPHH_URL when not passed", async () => {
    process.env.GLYPHH_URL = SERVER;
    expect((await new Glyphh().health()).database).toBe(true);
  });

  it("is required", () => {
    delete process.env.GLYPHH_URL;
    expect(() => new Glyphh()).toThrow("Glyphh needs a server");
  });
});
