import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: [
      "tests/**/*.{test,spec}.{ts,mts,cts}",
      "src/**/*.{test,spec}.{ts,mts,cts}",
      "src/**/__tests__/**/*.{ts,mts,cts}",
    ],
  },
});
