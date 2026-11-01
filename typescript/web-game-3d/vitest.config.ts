import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.{ts,mts,cts}"],
    coverage: {
      // Every src file counts, even ones no test imports. Exclude untestable code
      // explicitly with /* v8 ignore start */ ... /* v8 ignore stop */ comments.
      enabled: true,
      provider: "v8",
      include: ["src/**/*.{ts,mts,cts,tsx,js,mjs,cjs}"],
      reporter: ["text"],
      thresholds: { lines: 90, branches: 90, functions: 90, statements: 90 },
    },
  },
});
