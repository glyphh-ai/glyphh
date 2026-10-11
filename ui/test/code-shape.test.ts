import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// Small, compartmentalized code: no file over 200 lines, and no index files gathering exports.
const SRC = join(import.meta.dirname, "..", "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

it("keeps every file under 200 lines", () => {
  const big = files(SRC).filter((f) => readFileSync(f, "utf8").split("\n").length > 200);
  expect(big).toEqual([]);
});

it("has no index files: every component is imported by its own path", () => {
  expect(files(SRC).filter((f) => /\/index\.(ts|tsx)$/.test(f))).toEqual([]);
});

it("gives every component its folder, its own file and its own styles", () => {
  const folders = readdirSync(SRC).filter((name) => /^[A-Z]/.test(name));
  const missing = folders.filter((name) => !["tsx", "module.css"].every((ext) => {
    const path = join(SRC, name, `${name}.${ext}`);
    return files(join(SRC, name)).includes(path);
  }));
  expect(missing).toEqual([]);
});
