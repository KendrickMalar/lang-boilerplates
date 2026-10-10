import test from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { copyPreset, write, runAt, expectResult, saveLog } from "./helpers.mjs";

for (const preset of ["node", "web", "library"]) {
  test(preset + " rejects non-null assertions", async () => {
    const root = await copyPreset(preset);
    await write(root, "src/assertion.ts", "export const first = [1][0]!;\n");
    await expectResult(root, ["lint"], 1, /no-non-null-assertion/);
  });
  test(
    preset + " rejects duplicate regular-expression alternatives",
    async () => {
      const root = await copyPreset(preset);
      await write(root, "src/pattern.ts", "export const pattern = /a|a/;\n");
      await expectResult(root, ["lint"], 1, /regexp\/no-dupe-disjunctions/);
    },
  );
}
test("type-only imports must use import type", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/person.ts",
    "export interface Person { name: string; }\n",
  );
  await write(
    root,
    "src/consumer.ts",
    'import { Person } from "./person.js";\nexport function getName(person: Person): string { return person.name; }\n',
  );
  await expectResult(root, ["lint"], 1, /consistent-type-imports/);
});
test("unused disable directives are errors rather than warnings", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/unused-disable.ts",
    "// eslint-disable-next-line no-console\nexport const value = 1;\n",
  );
  const result = runAt(root, "pnpm", [
    "exec",
    "eslint",
    "src/unused-disable.ts",
    "--format=json",
  ]);
  await saveLog("unused-disable", result);
  const reports = JSON.parse(result.output.slice(result.output.indexOf("[")));
  const message = reports
    .flatMap((report) => report.messages)
    .find((message) => /Unused eslint-disable directive/.test(message.message));
  assert.ok(message, result.output);
  assert.equal(message.severity, 2, result.output);
});
for (const [modifier, rule] of [
  ["only", "no-focused-tests"],
  ["skip", "no-disabled-tests"],
]) {
  test("Vitest rejects " + modifier + " tests", async () => {
    const root = await copyPreset("node");
    await write(
      root,
      "tests/selection.test.ts",
      'import { expect, test } from "vitest";\ntest.' +
        modifier +
        '("selection", () => { expect(1).toBe(1); });\n',
    );
    await expectResult(root, ["lint"], 1, new RegExp("vitest/" + rule));
  });
}
test("library public functions require return types", async () => {
  const root = await copyPreset("library");
  await write(
    root,
    "src/public.ts",
    "export function increment(value: number) { return value + 1; }\n",
  );
  await expectResult(root, ["lint"], 1, /explicit-module-boundary-types/);
});
test("Node application functions can keep inferred return types", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/public.ts",
    "export function increment(value: number) { return value + 1; }\n",
  );
  await expectResult(root, ["lint"], 0);
});
test("Node API compatibility follows the consuming package engines", async () => {
  const root = await copyPreset("node");
  const path = join(root, "package.json");
  const pkg = JSON.parse(await readFile(path, "utf8"));
  pkg.engines.node = ">=10";
  await writeFile(path, JSON.stringify(pkg, null, 2) + "\n");
  await write(
    root,
    "src/node-api.ts",
    'import { readFile } from "node:fs/promises";\nexport const load = readFile;\n',
  );
  await expectResult(
    root,
    ["lint"],
    1,
    /n\/no-unsupported-features\/node-builtins/,
  );
});
test("Node static experimental APIs require an explicit policy decision", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/experimental.ts",
    'import { DatabaseSync } from "node:sqlite";\nexport const db = new DatabaseSync(":memory:");\n',
  );
  await expectResult(
    root,
    ["lint"],
    1,
    /n\/no-unsupported-features\/node-builtins/,
  );
});

test("stylistic typed rules reject inconsistent array syntax", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/array.ts",
    "export const values: Array<number> = [1];\n",
  );
  await expectResult(root, ["lint"], 1, /array-type/);
});
for (const preset of ["web", "library"]) {
  test(preset + " also rejects focused Vitest tests", async () => {
    const root = await copyPreset(preset);
    const path =
      preset === "library" ? "src/focused.test.ts" : "tests/focused.test.ts";
    await write(
      root,
      path,
      'import { expect, test } from "vitest";\ntest.only("focused", () => { expect(1).toBe(1); });\n',
    );
    await expectResult(root, ["lint"], 1, /vitest\/no-focused-tests/);
  });
}
test("Vitest rejects standalone expect assertions", async () => {
  const root = await copyPreset("web");
  await write(
    root,
    "tests/standalone.test.ts",
    'import { expect } from "vitest";\nexpect(1).toBe(1);\n',
  );
  await expectResult(root, ["lint"], 1, /vitest\/no-standalone-expect/);
});
test("library test helpers are not forced to declare public API return types", async () => {
  const root = await copyPreset("library");
  await write(
    root,
    "src/internal.test.ts",
    'import { expect, test } from "vitest";\nexport function localHelper(value: number) { return value + 1; }\ntest("helper", () => { expect(localHelper(1)).toBe(2); });\n',
  );
  await expectResult(root, ["lint"], 0);
});
test("browser sources are not classified as Node API targets", async () => {
  const root = await copyPreset("web");
  const result = runAt(root, "pnpm", [
    "exec",
    "eslint",
    "--print-config",
    "src/index.ts",
  ]);
  assert.equal(result.status, 0, result.output);
  const config = JSON.parse(result.output);
  assert.ok(
    !config.rules["n/no-unsupported-features/node-builtins"] ||
      config.rules["n/no-unsupported-features/node-builtins"][0] === 0,
  );
});

test("focused tests remain unchanged when lint is invoked with --fix", async () => {
  const root = await copyPreset("node");
  const source =
    'import { expect, test } from "vitest";\ntest.only("focused", () => { expect(1).toBe(1); });\n';
  await write(root, "tests/no-auto-fix.test.ts", source);
  const result = runAt(root, "pnpm", [
    "exec",
    "eslint",
    "tests/no-auto-fix.test.ts",
    "--fix",
  ]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /vitest\/no-focused-tests/);
  assert.equal(
    await readFile(join(root, "tests/no-auto-fix.test.ts"), "utf8"),
    source,
  );
});
