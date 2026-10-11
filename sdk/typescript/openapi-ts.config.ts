import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "../../openapi/glyphh.json",
  output: { path: "src/gen", importFileExtension: ".js" },
  plugins: ["@hey-api/client-fetch", "@hey-api/sdk", "@hey-api/typescript"],
});
