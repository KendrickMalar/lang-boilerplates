import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
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
        assert.ok(
          section.includes(
            "```sh\ncp architecture/" + option + ".mjs architecture.mjs\n```",
          ),
          "copy command",
        );
      },
    );
  test(leaf + " pins the tools and refuses to lint without a choice", () => {
    const pkg = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
    assert.equal(pkg.devDependencies["eslint-plugin-boundaries"], "7.4.0");
    assert.equal(
      pkg.devDependencies["eslint-import-resolver-typescript"],
      "4.4.5",
    );
    if (leaf === "ts-library")
      assert.equal(pkg.devDependencies["dependency-cruiser"], "18.7.0");
    assert.equal(
      pkg.scripts.lint,
      leaf === "ts-library"
        ? "eslint . --max-warnings 0 && depcruise src --config depcruise.config.mjs"
        : "eslint . --max-warnings 0",
    );
    const config = readFileSync(join(dir, "eslint.config.mjs"), "utf8");
    assert.ok(
      config.includes('new URL("./architecture.mjs", import.meta.url)'),
    );
    assert.ok(config.includes("Missing architecture.mjs"));
    assert.ok(
      config.includes(
        "cp architecture/" + options[0][0] + ".mjs architecture.mjs",
      ),
    );
    assert.ok(!existsSync(join(dir, "architecture.mjs")), "preinstalled");
    const expected = options.map(([option]) => option + ".mjs");
    assert.deepEqual(
      readdirSync(join(dir, "architecture")).sort(),
      expected.sort(),
    );
  });
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
test("every root architecture row matches the choices in its README", () => {
  const readme = readFileSync(join(ROOT, "README.md"), "utf8");
  const start = readme.indexOf("\n## 用途ごとのアーキテクチャ\n");
  const section = readme.slice(start, readme.indexOf("\n## ", start + 1));
  const rows = section
    .split("\n")
    .filter((line) => /^\| \[/.test(line))
    .map((line) => line.split("|").map((cell) => cell.trim()));
  assert.ok(rows.length >= 10);
  for (const [, link, list, fallback] of rows) {
    const path = /\]\(\.\/([^)]+)\)/.exec(link)[1];
    const headings = [
      ...architectureSection(readFileSync(join(ROOT, path), "utf8")).matchAll(
        /^### (.+)$/gm,
      ),
    ].map((match) => match[1]);
    assert.ok(headings.includes(fallback + "（既定）"), path + " default");
    for (const choice of list.replace("（選択肢なし）", "").split("／"))
      assert.ok(
        headings.includes(choice) || headings.includes(choice + "（既定）"),
        path + " " + choice,
      );
  }
});
