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

it("keeps every function and component under 40 lines (tests excepted)", async () => {
  const ts = await import("typescript");
  const big: string[] = [];
  for (const file of files(SRC).filter((f) => /\.tsx?$/.test(f) && !/\.test\.tsx?$/.test(f) && !f.endsWith(".d.ts"))) {
    const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
    const visit = (node: import("typescript").Node): void => {
      if (ts.isFunctionLike(node) && "body" in node && node.body) {
        const start = source.getLineAndCharacterOfPosition(node.getStart()).line;
        const end = source.getLineAndCharacterOfPosition(node.getEnd()).line;
        if (end - start + 1 > 40) big.push(`${file.replace(SRC, "")}:${start + 1}`);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  expect(big).toEqual([]);
});
