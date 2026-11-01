// 機能別の複数入口。README「## アーキテクチャ」の規則を ESLint で強制する。
// 製品 root の architecture.mjs へコピーすると、eslint.config.mjs が読み込む。
import boundaries from "eslint-plugin-boundaries";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const shared = { element: { type: "shared" } };
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };
const featureEntry = {
  element: { type: "feature", fileInternalPath: "index.ts" },
};

export default [
  {
    files: sources,
    ignores: tests,
    plugins: { boundaries },
    settings: {
      // .js 付きの import を .ts へ解決する。無いと機能を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      "boundaries/elements": [
        {
          type: "feature",
          pattern: "src/features/*",
          capture: ["name"],
          partialMatch: false,
        },
        { type: "shared", pattern: "src/shared", partialMatch: false },
      ],
      // 任意の集約入口。機能の index.ts を再公開するだけにする。
      "boundaries/files": [{ category: "entry", pattern: "src/index.ts" }],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // 機能同士の依存・shared から機能への依存は書いていないので拒否される。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            {
              from: { element: { type: "feature" } },
              allow: { to: [shared, external, builtin] },
            },
            { from: shared, allow: { to: [external, builtin] } },
            {
              from: { file: { categories: "entry" } },
              allow: { to: [featureEntry] },
            },
          ],
        },
      ],
    },
  },
];
