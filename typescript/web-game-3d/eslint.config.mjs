import { defineConfig } from "eslint/config";
import playwright from "eslint-plugin-playwright";
import { createConfig } from "./eslint.base.mjs";

export default defineConfig(createConfig({ environment: "browser" }), {
  files: ["tests/e2e/**/*.ts"],
  plugins: playwright.configs["flat/recommended"].plugins,
  rules: {
    ...playwright.configs["flat/recommended"].rules,
    "playwright/no-focused-test": "error",
    "playwright/no-skipped-test": "error",
  },
});
