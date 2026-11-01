import { existsSync } from "node:fs";
import { defineConfig } from "eslint/config";
import { createConfig } from "./eslint.base.mjs";

// 選んだアーキテクチャの強制設定（README「アーキテクチャ」）。無いときは検査を飛ばさず止める。
const selected = new URL("./architecture.mjs", import.meta.url);
if (!existsSync(selected))
  throw new Error(
    "Missing architecture.mjs. Copy the chosen option (README「アーキテクチャ」): " +
      "cp architecture/onion.mjs architecture.mjs (choices: onion, functional-core, vertical-slices)",
  );
const { default: architecture } = await import(selected.href);

export default defineConfig(
  createConfig({ environment: "node" }),
  architecture,
);
