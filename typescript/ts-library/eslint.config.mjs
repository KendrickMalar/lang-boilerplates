import { existsSync } from "node:fs";
import { createConfig } from "./eslint.base.mjs";

// 選んだアーキテクチャの強制設定（README「アーキテクチャ」）。無いときは検査を飛ばさず止める。
const selected = new URL("./architecture.mjs", import.meta.url);
if (!existsSync(selected))
  throw new Error(
    "Missing architecture.mjs. Copy the chosen option (README「アーキテクチャ」): " +
      "cp architecture/single-entry.mjs architecture.mjs (choices: single-entry, core-adapters, multi-entry)",
  );
const { default: architecture } = await import(selected.href);

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
  ...architecture,
];
