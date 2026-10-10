import { createConfig } from "./eslint.base.mjs";

export default [
  ...createConfig({
    environment: "node",
    testFiles: [
      "tests/**/*.{test,spec}.ts",
      "src/**/*.{test,spec}.ts",
      "src/**/__tests__/**/*.ts",
    ],
  }),
  {
    files: ["src/**/*.ts"],
    ignores: ["src/**/*.test.ts", "src/**/*.spec.ts", "src/**/__tests__/**"],
    rules: { "@typescript-eslint/explicit-module-boundary-types": "error" },
  },
];
