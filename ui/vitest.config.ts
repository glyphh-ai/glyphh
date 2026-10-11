import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    // Real class names in tests, so a test can say "has class block" and mean it.
    css: { include: [/.+/], modules: { classNameStrategy: "non-scoped" } },
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts"],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
