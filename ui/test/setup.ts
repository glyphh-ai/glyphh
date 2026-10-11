import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Any React warning (an unknown prop on an element, a missing key, an act() slip) fails the test.
beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    throw new Error(`console.error during a test: ${args.map(String).join(" ")}`);
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
