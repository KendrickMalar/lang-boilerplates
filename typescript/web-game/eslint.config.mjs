import { existsSync } from "node:fs";
import { defineConfig } from "eslint/config";
import playwright from "eslint-plugin-playwright";
import { createConfig } from "./eslint.base.mjs";

// 選んだアーキテクチャの強制設定（README「アーキテクチャ」）。無いときは検査を飛ばさず止める。
const selected = new URL("./architecture.mjs", import.meta.url);
if (!existsSync(selected))
  throw new Error(
    "Missing architecture.mjs. Copy the chosen option (README「アーキテクチャ」): " +
      "cp architecture/pure-core.mjs architecture.mjs (choices: pure-core, ecs, engine-shell)",
  );
const { default: architecture } = await import(selected.href);

export default defineConfig(
  createConfig({ environment: "browser" }),
  {
    files: ["tests/e2e/**/*.ts"],
    plugins: playwright.configs["flat/recommended"].plugins,
    rules: {
      ...playwright.configs["flat/recommended"].rules,
      "playwright/no-focused-test": "error",
      "playwright/no-skipped-test": "error",
    },
  },
  architecture,
);
