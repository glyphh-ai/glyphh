import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

// The hand-written SDK stays small enough for an agent to hold in view (the generated client is exempt).
it("keeps every hand-written file under 200 lines", () => {
  const src = join(import.meta.dirname, "..", "src");
  const big = readdirSync(src)
    .filter((name) => name.endsWith(".ts"))
    .map((name) => [name, readFileSync(join(src, name), "utf8").split("\n").length] as const)
    .filter(([, lines]) => lines > 200);
  expect(big).toEqual([]);
});
