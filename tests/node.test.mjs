import test from "node:test";
import assert from "node:assert/strict";
import { copyPreset, write, runAt, expectResult } from "./helpers.mjs";

test("Node preset checks, builds and executes copied output", async () => {
  const root = await copyPreset("node");
  await expectResult(root, ["check"], 0);
  const result = runAt(root, "node", [
    "--input-type=module",
    "-e",
    'import { add } from "./dist/index.js"; console.log(add(1, 2));',
  ]);
  assert.equal(result.status, 0, result.output);
  assert.equal(result.output.trim(), "3");
});
for (const [name, source, diagnostic] of [
  ["type mismatch", 'export const value: number = "bad";\n', /TS2322/],
  [
    "unchecked array access",
    "export function first(values: number[]): number { return values[0]; }\n",
    /undefined/,
  ],
  [
    "exact optional properties",
    "export const value: { name?: string } = { name: undefined };\n",
    /exactOptionalPropertyTypes/,
  ],
  ["DOM API in Node", "export const element = document.body;\n", /document/],
]) {
  test("Node typecheck rejects " + name, async () => {
    const root = await copyPreset("node");
    await write(root, "src/bad.ts", source);
    await expectResult(root, ["typecheck"], 1, diagnostic);
  });
}
for (const [name, source, diagnostic] of [
  [
    "explicit any",
    "export function echo(value: any) { return value; }\n",
    /no-explicit-any/,
  ],
  [
    "floating promise",
    "Promise.resolve(1);\nexport {};\n",
    /no-floating-promises/,
  ],
]) {
  test("typed lint rejects " + name, async () => {
    const root = await copyPreset("node");
    await write(root, "src/bad.ts", source);
    await expectResult(root, ["lint"], 1, diagnostic);
  });
}
test("format check rejects unformatted product code", async () => {
  const root = await copyPreset("node");
  await write(root, "src/bad.ts", "export const x=1");
  await expectResult(root, ["format:check"], 1, /Code style issues/);
});
test("test command rejects wrong assertions", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "tests/index.test.ts",
    'import { expect, test } from "vitest";\nimport { add } from "../src/index.js";\ntest("rejects wrong sum", () => { expect(add(1, 2)).toBe(4); });\n',
  );
  await expectResult(root, ["test"], 1, /AssertionError|expected/);
});
test("test command rejects missing tests", async () => {
  const root = await copyPreset("node", { tests: false });
  await expectResult(root, ["test"], 1, /No test files found/);
});
test("check stops after type failure before build", async () => {
  const root = await copyPreset("node");
  await write(root, "src/bad.ts", 'export const value: number = "bad";\n');
  const result = await expectResult(root, ["check"], 1, /TS2322/);
  assert.doesNotMatch(result.output, /> tsc -p tsconfig.build.json/);
});

for (const preset of ["node", "web", "library"]) {
  test(
    preset + " config-only copy is not accepted as a verified product",
    async () => {
      const root = await copyPreset(preset, { sample: false });
      await expectResult(
        root,
        ["check"],
        1,
        /No test files found|No inputs were found|path does not exist: src|No product source directory/,
      );
    },
  );
}
