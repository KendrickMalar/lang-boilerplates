// オニオン（この用途の唯一の型）。README「## アーキテクチャ」の規則を ESLint で強制する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const layers = ["domain", "application", "infrastructure", "presentation"];
const layer = (type) => ({ element: { type } });
const external = { module: { origin: "external" } };
// ブラウザだけにあるグローバル（document・window など）。domain では使わない。
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
      // tsconfig のパス解決どおりに import を辿る。無いと層を判定できない。
      "import/resolver": {
        typescript: { alwaysTryTypes: true, project: "./tsconfig.app.json" },
        node: true,
      },
      "boundaries/ignore": tests,
      "boundaries/elements": layers.map((type) => ({
        type,
        pattern: "src/" + type,
        partialMatch: false,
      })),
      "boundaries/files": [{ category: "composition", pattern: "src/main.ts" }],
    },
    rules: {
      // 層にも組み立て役にも当たらない src のファイルは置かない。
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // 書いていない向きはすべて拒否する。domain は外へ何も依存しない。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: layer("application"), allow: { to: [layer("domain")] } },
            {
              from: layer("infrastructure"),
              allow: { to: [layer("domain"), layer("application"), external] },
            },
            {
              from: layer("presentation"),
              allow: { to: [layer("domain"), layer("application"), external] },
            },
            {
              from: { file: { categories: "composition" } },
              allow: { to: [...layers.map(layer), external] },
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/domain/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"],
    ignores: tests,
    rules: {
      "no-restricted-globals": ["error", ...new Set([...browserOnly, ...io])],
    },
  },
];
