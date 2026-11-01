// ECS（エンティティ・コンポーネント・システム）。README「## アーキテクチャ」の規則を ESLint で強制する。
// 製品 root の architecture.mjs へコピーすると、eslint.config.mjs が読み込む。
import boundaries from "eslint-plugin-boundaries";
import globals from "globals";

const sources = ["src/**/*.{js,mjs,cjs,ts,tsx,mts,cts}"];
const tests = ["src/**/*.{test,spec}.*", "src/**/__tests__/**"];
const part = (type) => ({ element: { type } });
const external = { module: { origin: "external" } };
// ECS ライブラリ（使うなら koota か bitecs）。components が使ってよい唯一の外部パッケージ。
const ecsLibrary = {
  module: { origin: "external", source: ["koota", "bitecs"] },
};
// 描画ライブラリ。render だけが import する。
const renderer = {
  module: { origin: "external", source: ["three", "@react-three/*"] },
};
// ブラウザだけにあるグローバル（document・window など）。components と systems では使わない。
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
      // tsconfig のパス解決どおりに import を辿る。無いと components などを判定できない。
      "import/resolver": {
        typescript: { alwaysTryTypes: true, project: "./tsconfig.app.json" },
        node: true,
      },
      "boundaries/ignore": tests,
      "boundaries/elements": ["components", "systems", "render"].map(
        (type) => ({ type, pattern: "src/ecs/" + type, partialMatch: false }),
      ),
      "boundaries/files": [
        { category: "composition", pattern: "src/{index,main}.ts" },
      ],
    },
    rules: {
      "boundaries/no-unknown-files": "error",
      "boundaries/dependencies": [
        "error",
        {
          // 後に書いた方針が勝つ。systems は外部を使えるが、描画ライブラリは拒否する。
          default: "disallow",
          checkAllOrigins: true,
          checkUnknownLocals: true,
          policies: [
            { from: part("components"), allow: { to: [ecsLibrary] } },
            {
              from: part("systems"),
              allow: { to: [part("components"), external] },
            },
            { from: part("systems"), disallow: { to: [renderer] } },
            {
              from: part("render"),
              allow: { to: [part("components"), external] },
            },
            {
              from: { file: { categories: "composition" } },
              allow: {
                to: [
                  part("components"),
                  part("systems"),
                  part("render"),
                  external,
                ],
              },
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/ecs/components/**/*.{js,mjs,cjs,ts,tsx,mts,cts}",
      "src/ecs/systems/**/*.{js,mjs,cjs,ts,tsx,mts,cts}",
    ],
    ignores: tests,
    rules: {
      "no-restricted-globals": ["error", ...new Set([...browserOnly, ...io])],
    },
  },
];
