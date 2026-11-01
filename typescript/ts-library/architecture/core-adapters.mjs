// コア＋実行環境アダプター。README「## アーキテクチャ」の規則を ESLint で強制する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const core = { element: { type: "core" } };
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };
// 実行環境ごとのグローバル（process・Buffer・document・window など）。core では使わない。
const environmentOnly = [
  ...Object.keys(globals.node).filter(
    (name) => !(name in globals.browser) && !(name in globals.builtin),
  ),
  ...Object.keys(globals.browser).filter(
    (name) => !(name in globals.node) && !(name in globals.builtin),
  ),
];

// 入出力のグローバル（Node とブラウザの両方にあるものを含む）。純粋な層では使わない。
const io = [
  "fetch",
  "WebSocket",
  "XMLHttpRequest",
  "localStorage",
  "sessionStorage",
  "indexedDB",
  "caches",
  "navigator",
];

export default [
  {
    files: sources,
    ignores: tests,
    plugins: { boundaries },
    settings: {
      // .js 付きの import を .ts へ解決する。無いと core と adapters を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      "boundaries/elements": [
        { type: "core", pattern: "src/core", partialMatch: false },
        {
          type: "adapter",
          pattern: "src/adapters/*",
          capture: ["name"],
          partialMatch: false,
        },
      ],
      // 実行環境に依らない入口。各アダプターの入口は src/adapters/<名前>/index.ts。
      "boundaries/files": [{ category: "entry", pattern: "src/index.ts" }],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // アダプター同士・core から adapters・node:* への依存は書いていないので拒否される。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: core, allow: { to: [external] } },
            {
              from: { element: { type: "adapter" } },
              allow: { to: [core, external, builtin] },
            },
            {
              from: { file: { categories: "entry" } },
              allow: { to: [core, external] },
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/core/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"],
    ignores: tests,
    rules: {
      "no-restricted-globals": [
        "error",
        ...new Set([...environmentOnly, ...io]),
      ],
    },
  },
];
