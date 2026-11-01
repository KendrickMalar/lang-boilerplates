// 機能コア＋命令的シェル。README「## アーキテクチャ」の規則を ESLint で強制する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const part = (type) => ({ element: { type } });
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };
// Node だけにあるグローバル（process・Buffer など）。core では使わない。
const nodeOnly = Object.keys(globals.node).filter(
  (name) => !(name in globals.browser) && !(name in globals.builtin),
);

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
      // .js 付きの import を .ts へ解決する。無いと core と shell を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      "boundaries/elements": ["core", "shell"].map((type) => ({
        type,
        pattern: "src/" + type,
        partialMatch: false,
      })),
      "boundaries/files": [{ category: "composition", pattern: "src/main.ts" }],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // core からの依存は core の中だけ（既定で拒否）。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            {
              from: part("shell"),
              allow: { to: [part("core"), external, builtin] },
            },
            {
              from: { file: { categories: "composition" } },
              allow: { to: [part("core"), part("shell"), external, builtin] },
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
      "no-restricted-globals": ["error", ...new Set([...nodeOnly, ...io])],
    },
  },
];
