import { createConfig } from "./eslint.base.mjs";

export default [
  ...createConfig({
    environment: "node",
    testFiles: [
      "tests/**/*.{test,spec}.{ts,mts,cts}",
      "src/**/*.{test,spec}.{ts,mts,cts}",
      "src/**/__tests__/**/*.{ts,mts,cts}",
    ],
  }),
  {
    files: ["src/**/*.{ts,mts,cts}"],
    ignores: [
      "src/**/*.test.{ts,mts,cts}",
      "src/**/*.spec.{ts,mts,cts}",
      "src/**/__tests__/**",
    ],
    rules: { "@typescript-eslint/explicit-module-boundary-types": "error" },
  },
];
