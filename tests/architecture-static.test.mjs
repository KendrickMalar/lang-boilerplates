import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./helpers.mjs";
import { architectureSection } from "./architecture-readme.mjs";

const choices = {
  web: [["onion", "オニオン（既定）"]],
  cli: [
    ["onion", "オニオン（既定）"],
    ["functional-core", "機能コア＋命令的シェル"],
    ["vertical-slices", "機能別の縦割り"],
  ],
  "web-game": [
    ["pure-core", "ルールの純粋コア（既定）"],
    ["ecs", "ECS"],
    ["engine-shell", "コア＋エンジンの殻"],
  ],
  "ts-library": [
    ["single-entry", "入口1つ＋internal（既定）"],
    ["core-adapters", "コア＋実行環境アダプター"],
    ["multi-entry", "機能別の複数入口"],
  ],
};

for (const [leaf, options] of Object.entries(choices)) {
  const dir = join(ROOT, "typescript", leaf);
  const readme = readFileSync(join(dir, "README.md"), "utf8");
  test(leaf + " README has the fixed architecture section in order", () => {
    const section = architectureSection(readme);
    const headings = [...section.matchAll(/^### (.+)$/gm)].map(
      (match) => match[1],
    );
    assert.deepEqual(headings, [
      "選び方",
      ...options.map(([, heading]) => heading),
    ]);
    assert.equal(
      headings.filter((heading) => heading.endsWith("（既定）")).length,
      1,
    );
    assert.match(section.split("\n### ")[0], /scaffold/);
  });
  for (const [option, heading] of options)
    test(
      leaf + " " + option + " documents layers, rules and enforcement",
      () => {
        const section = architectureSection(readme, heading);
        assert.match(section, /```mermaid\nflowchart/);
        assert.match(section, /MUST NOT/);
        assert.match(section, /向く/);
        assert.match(section, /向かない/);
        assert.ok(
          section.includes("](./architecture/" + option + ".mjs)"),
          "link",
        );
        const config = /```js\n([\s\S]*?)```/.exec(section);
        assert.ok(config, "eslint.config.mjs block");
        assert.ok(
          config[1].includes('from "./architecture/' + option + '.mjs"'),
        );
      },
    );
  test(
    leaf + " pins the architecture tools without enabling a choice by default",
    () => {
      const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
      assert.equal(pkg.devDependencies["eslint-plugin-boundaries"], "7.4.0");
      assert.equal(
        pkg.devDependencies["eslint-import-resolver-typescript"],
        "4.4.5",
      );
      if (leaf === "ts-library")
        assert.equal(pkg.devDependencies["dependency-cruiser"], "18.7.0");
      assert.equal(pkg.scripts.lint, "eslint . --max-warnings 0");
      assert.doesNotMatch(
        readFileSync(join(dir, "eslint.config.mjs"), "utf8"),
        /architecture/,
      );
      const expected = options.map(([option]) => option + ".mjs");
      if (leaf === "ts-library") expected.push("single-entry.depcruise.mjs");
      assert.deepEqual(
        readdirSync(join(dir, "architecture")).sort(),
        expected.sort(),
      );
    },
  );
}
test("root README lists architecture choices per TypeScript use case", () => {
  const readme = readFileSync(join(ROOT, "README.md"), "utf8");
  const start = readme.indexOf("\n## 用途ごとのアーキテクチャ\n");
  assert.ok(start >= 0);
  const section = readme.slice(start, readme.indexOf("\n## ", start + 1));
  for (const [leaf, options] of Object.entries(choices)) {
    const row = section
      .split("\n")
      .find((line) => line.includes("typescript/" + leaf + "/README.md"));
    assert.ok(row, leaf);
    for (const [, heading] of options)
      assert.ok(
        row.includes(heading.replace("（既定）", "")),
        leaf + " " + heading,
      );
  }
});
