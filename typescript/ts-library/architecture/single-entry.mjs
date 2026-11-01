// 入口1つ＋internal（既定）。README「## アーキテクチャ」の規則を ESLint で強制する。
// 循環の禁止は single-entry.depcruise.mjs（dependency-cruiser）で検査する。
// eslint.config.mjs で createConfig() の後ろに足して使う。
import boundaries from "eslint-plugin-boundaries";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const internal = { element: { type: "internal" } };
const external = { module: { origin: "external" } };
const builtin = { module: { origin: "core" } };

export default [
  {
    files: sources,
    ignores: tests,
    plugins: { boundaries },
    settings: {
      // .js 付きの import を .ts へ解決する。無いと internal を判定できない。
      "import/resolver": { typescript: { alwaysTryTypes: true }, node: true },
      "boundaries/ignore": tests,
      "boundaries/elements": [
        { type: "internal", pattern: "src/internal", partialMatch: false },
      ],
      // 公開 API は src/index.ts だけ。
      "boundaries/files": [{ category: "entry", pattern: "src/index.ts" }],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // internal から index.ts への依存は書いていないので拒否される。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: internal, allow: { to: [external, builtin] } },
            {
              from: { file: { categories: "entry" } },
              allow: { to: [internal, external, builtin] },
            },
          ],
        },
      ],
    },
  },
];
