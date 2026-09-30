// Copy the compiled kernel + plugin code (dist/) into plugin/lib, and the
// shared skill from the Python plugin, so js/plugin is a self-contained
// Claude Code plugin root. Run by `npm run build`; a test checks the sync.
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const js = join(dirname(fileURLToPath(import.meta.url)), "..");
rmSync(join(js, "plugin", "lib"), { recursive: true, force: true });
cpSync(join(js, "dist"), join(js, "plugin", "lib"), {
  recursive: true,
  filter: (src) => !src.endsWith(".d.ts"),
});
mkdirSync(join(js, "plugin", "skills"), { recursive: true });
cpSync(join(js, "..", "plugin", "skills", "glyphh-think"), join(js, "plugin", "skills", "glyphh-think"), { recursive: true });
console.log("plugin/lib and plugin/skills synced");
