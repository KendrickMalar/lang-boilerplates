// 機能別の縦割り。README「## アーキテクチャ」の規則を ESLint で強制する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };
const shared = { element: { type: "shared" } };
// 同じ機能の中の層。
const own = (type) => ({
  element: { type, captured: { name: "{{ from.element.captured.name }}" } },
});
// 他の機能へは、その機能の index.ts だけ。
const otherEntry = {
  element: {
    type: "feature",
    fileInternalPath: "index.ts",
    captured: { name: "!{{ from.element.captured.name }}" },
  },
};
const anyEntry = { element: { type: "feature", fileInternalPath: "index.ts" } };
// Node だけにあるグローバル（process・Buffer など）。domain と shared では使わない。
const nodeOnly = Object.keys(globals.node).filter(
  (name) => !(name in globals.browser) && !(name in globals.builtin),
);
const featureLayer = (type) => ({
  type: "feature-" + type,
  pattern: "src/features/*/" + type,
  capture: ["name"],
  partialMatch: false,
});

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
      // .js 付きの import を .ts へ解決する。無いと機能と層を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      // 先に書いたものが優先される。層 → 機能の入口（index.ts）の順。
      "boundaries/elements": [
        featureLayer("domain"),
        featureLayer("application"),
        featureLayer("infrastructure"),
        {
          type: "feature",
          pattern: "src/features/*",
          capture: ["name"],
          partialMatch: false,
        },
        { type: "shared", pattern: "src/shared", partialMatch: false },
      ],
      "boundaries/files": [{ category: "composition", pattern: "src/main.ts" }],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            {
              from: { element: { type: "feature-domain" } },
              allow: { to: [shared] },
            },
            {
              from: { element: { type: "feature-application" } },
              allow: { to: [own("feature-domain"), shared, otherEntry] },
            },
            {
              from: { element: { type: "feature-infrastructure" } },
              allow: {
                to: [
                  own("feature-domain"),
                  own("feature-application"),
                  shared,
                  otherEntry,
                  external,
                  builtin,
                ],
              },
            },
            {
              from: { element: { type: "feature" } },
              allow: {
                to: [
                  own("feature-domain"),
                  own("feature-application"),
                  own("feature-infrastructure"),
                  shared,
                  otherEntry,
                ],
              },
            },
            {
              from: { file: { categories: "composition" } },
              allow: { to: [anyEntry, shared, external, builtin] },
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/features/*/domain/**/*.{js,mjs,cjs,ts,tsx,mts,cts}",
      "src/shared/**/*.{js,mjs,cjs,ts,tsx,mts,cts}",
    ],
    ignores: tests,
    rules: {
      "no-restricted-globals": ["error", ...new Set([...nodeOnly, ...io])],
    },
  },
];
