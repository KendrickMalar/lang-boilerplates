import test from "node:test";
import assert from "node:assert/strict";
import { copyPreset, expectResult, runAt, write } from "./helpers.mjs";

const THRESHOLD_MISS =
  /Coverage for (lines|functions|statements|branches) \([\d.]+%\) does not meet global threshold \(90%\)/;
const UNTESTED =
  "export function untested(value: number): number {\n  return value > 0 ? value * 2 : -value;\n}\n";

for (const name of ["library", "node", "web", "web-game-3d"]) {
  test(name + " rejects src files that tests never import", async () => {
    const root = await copyPreset(name);
    await expectResult(root, ["test"], 0);
    await write(root, "src/extra.ts", UNTESTED);
    await expectResult(root, ["test"], 1, THRESHOLD_MISS);
  });
}

test("untested JavaScript files under src also count", async () => {
  const root = await copyPreset("node");
  await write(
    root,
    "src/util.js",
    "export function untested(value) {\n  return value > 0 ? value * 2 : -value;\n}\n",
  );
  await expectResult(root, ["test"], 1, THRESHOLD_MISS);
});

test("colocated tests under src are not counted as product code", async () => {
  const root = await copyPreset("library");
  await write(
    root,
    "src/index.test.ts",
    'import { expect, test } from "vitest";\nimport { add } from "./index.js";\ntest("colocated", () => {\n  expect(add(2, 2)).toBe(4);\n});\n',
  );
  const result = await expectResult(root, ["test"], 0);
  // Only src/index.ts is product code; counting the colocated test would make it 2 files.
  assert.match(result.output, /\b1 file fully covered/);
});

test("commit gate rejects a staged change that drops coverage below 90%", async () => {
  const root = await copyPreset("library");
  const git = (...args) => {
    const result = runAt(root, "git", args);
    assert.equal(result.status, 0, result.output);
    return result.output.trim();
  };
  git("init", "-b", "main");
  const husky = runAt(root, "pnpm", ["exec", "husky"]);
  assert.equal(husky.status, 0, husky.output);
  git("add", ".");
  git("commit", "-m", "valid baseline");
  const before = git("rev-parse", "HEAD");
  await write(root, "src/extra.ts", UNTESTED);
  git("add", "src/extra.ts");
  const result = runAt(root, "git", ["commit", "-m", "untested code"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, THRESHOLD_MISS);
  assert.equal(git("rev-parse", "HEAD"), before);
});
