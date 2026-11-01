// コア＋エンジンの殻。README「## アーキテクチャ」の規則を ESLint で強制する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const part = (type) => ({ element: { type } });
const external = { module: { origin: "external" } };
// ブラウザだけにあるグローバル（document・window・requestAnimationFrame など）。core では使わない。
const browserOnly = Object.keys(globals.browser).filter(
  (name) => !(name in globals.node) && !(name in globals.builtin),
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
      // tsconfig のパス解決どおりに import を辿る。無いと core と shell を判定できない。
      "import/resolver": {
        typescript: { alwaysTryTypes: true, project: "./tsconfig.app.json" },
        node: true,
      },
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
          // core からの依存は core の中だけ（既定で拒否）。エンジン（three・
          // @dimforge/* など）を含む外部パッケージと shell へ依存しない。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: part("shell"), allow: { to: [part("core"), external] } },
            {
              from: { file: { categories: "composition" } },
              allow: { to: [part("core"), part("shell"), external] },
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
      "no-restricted-globals": ["error", ...new Set([...browserOnly, ...io])],
    },
  },
];
