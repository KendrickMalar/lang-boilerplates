// オニオン（既定）。README「## アーキテクチャ」の規則を ESLint で強制する。
// 製品 root の architecture.mjs へコピーすると、eslint.config.mjs が読み込む。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const layers = ["domain", "application", "infrastructure", "presentation"];
const layer = (type) => ({ element: { type } });
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };
// Node だけにあるグローバル（process・Buffer など）。domain では使わない。
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
      // .js 付きの import を .ts へ解決する。無いと層を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      "boundaries/elements": layers.map((type) => ({
        type,
        pattern: "src/" + type,
        partialMatch: false,
      })),
      "boundaries/files": [
        { category: "composition", pattern: "src/{index,main}.ts" },
      ],
    },
    rules: {
      // 層にも組み立て役にも当たらない src のファイルは置かない。
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: layer("application"), allow: { to: [layer("domain")] } },
            {
              from: layer("infrastructure"),
              allow: {
                to: [layer("domain"), layer("application"), external, builtin],
              },
            },
            {
              from: layer("presentation"),
              allow: {
                to: [layer("domain"), layer("application"), external, builtin],
              },
            },
            {
              from: { file: { categories: "composition" } },
              allow: {
                to: [...layers.map(layer), external, builtin],
              },
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
      "no-restricted-globals": ["error", ...new Set([...nodeOnly, ...io])],
    },
  },
];
