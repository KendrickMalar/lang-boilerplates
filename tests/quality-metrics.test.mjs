import test from "node:test";
import assert from "node:assert/strict";
import { ESLint } from "eslint";
import { copyPreset, write, runAt } from "./helpers.mjs";

const presets = ["cli", "web", "ts-library", "web-game"];
const complexity = (branches) =>
  "export function score(value: number): number {\nlet result = value;\n" +
  Array.from(
    { length: branches },
    (_, i) => `if (value > ${i}) result += ${i};`,
  ).join("\n") +
  "\nreturn result;\n}\n";
const lines = (count) =>
  "export function increment(value: number): number {\n" +
  "value += 1;\n".repeat(count - 3) +
  "return value;\n}\n";
const depth = (count) =>
  "export function nested(value: number): number {\n" +
  Array.from({ length: count }, (_, i) => `if (value > ${i}) {`).join("\n") +
  "\nvalue += 1;\n" +
  "}\n".repeat(count) +
  "return value;\n}\n";

for (const preset of presets) {
  test(preset + " enforces metric boundaries in source and tests", async () => {
    const root = await copyPreset(preset, { dependencies: false });
    await write(root, "src/metric.mts", "export {};\n");
    await write(root, "src/metric.cts", "export {};\n");
    await write(
      root,
      "src/index.ts",
      'import "./metric.mjs";\nimport "./metric.cjs";\nexport {};\n',
    );
    const eslint = new ESLint({ cwd: root });
    for (const file of [
      "src/metric.ts",
      "src/metric.mts",
      "src/metric.cts",
      "tests/metric.test.ts",
    ]) {
      for (const [rule, good, bad] of [
        ["complexity", complexity(9), complexity(10)],
        ["max-lines-per-function", lines(50), lines(51)],
        ["max-depth", depth(3), depth(4)],
      ]) {
        for (const [source, rejected] of [
          [good, false],
          [bad, true],
        ]) {
          await write(root, file, source);
          const reports = await eslint.lintFiles([file]);
          const messages = reports.flatMap((report) => report.messages);
          assert.ok(
            !messages.some((message) => message.fatal),
            JSON.stringify(messages),
          );
          assert.equal(
            messages.some(
              (message) => message.ruleId === rule && message.severity === 2,
            ),
            rejected,
            `${preset} ${file} ${rule}: ${JSON.stringify(messages)}`,
          );
        }
      }
    }
    await write(
      root,
      "src/metric.ts",
      lines(50).replace("value += 1;", "// ignored comment\n\nvalue += 1;"),
    );
    const reports = await eslint.lintFiles(["src/metric.ts"]);
    assert.ok(
      !reports
        .flatMap((report) => report.messages)
        .some((message) => message.ruleId === "max-lines-per-function"),
    );
  });

  test(
    preset + " rejects source duplication but excludes colocated tests",
    async () => {
      const root = await copyPreset(preset);
      const source =
        "export function calculate(value: number): number {\n" +
        Array.from(
          { length: 12 },
          (_, i) => `  value = Math.sqrt(value + ${i + 1});`,
        ).join("\n") +
        "\n  return value;\n}\n";
      await write(root, "src/calculate.ts", source);
      await write(root, "src/calculate.test.ts", source);
      let result = runAt(root, "pnpm", ["lint:duplicates"]);
      assert.equal(result.status, 0, result.output);
      await write(root, "src/clone.ts", source);
      result = runAt(root, "pnpm", ["lint:duplicates"]);
      assert.notEqual(result.status, 0, result.output);
      assert.match(result.output, /duplicat|clone|threshold/i);
    },
  );
}

test("duplication checks do not silently skip product files above one MiB", async () => {
  const root = await copyPreset("cli");
  const source =
    "/*" +
    "padding".repeat(160000) +
    "*/\n" +
    "export function calculate(value: number): number {\n" +
    Array.from(
      { length: 12 },
      (_, i) => `  value = Math.sqrt(value + ${i + 1});`,
    ).join("\n") +
    "\n  return value;\n}\n";
  await write(root, "src/large-one.ts", source);
  await write(root, "src/large-two.ts", source);
  const result = runAt(root, "pnpm", ["lint:duplicates"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /duplicat|clone|threshold/i);
});

for (const extension of ["mts", "cts"]) {
  test(
    "duplication checks include ." + extension + " product modules",
    async () => {
      const root = await copyPreset("cli");
      const source =
        "export function calculate(value: number): number {\n" +
        Array.from(
          { length: 12 },
          (_, i) => `  value = Math.sqrt(value + ${i + 1});`,
        ).join("\n") +
        "\n  return value;\n}\n";
      await write(root, "src/first." + extension, source);
      await write(root, "src/second." + extension, source);
      const result = runAt(root, "pnpm", ["lint:duplicates"]);
      assert.notEqual(result.status, 0, result.output);
      assert.match(result.output, /duplicat|clone|threshold/i);
    },
  );
}
