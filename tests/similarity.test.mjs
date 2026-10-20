import test from "node:test";
import assert from "node:assert/strict";
import { rename, chmod, mkdir, symlink } from "node:fs/promises";
import { join } from "node:path";
import { copyPreset, write, runAt } from "./helpers.mjs";

const first =
  "export function first(input: number): number {\n  let result = input;\n" +
  Array.from(
    { length: 30 },
    (_, index) => `  result = Math.max(result + ${index + 1}, ${index + 2});`,
  ).join("\n") +
  "\n  return result;\n}\n";
const second = first
  .replaceAll("first", "second")
  .replaceAll("input", "value")
  .replaceAll("result", "output");

for (const preset of ["node", "web", "library", "web-game-3d"]) {
  test(
    preset + " detects renamed structural clones beyond token duplication",
    async () => {
      const root = await copyPreset(preset);
      await write(root, "src/first.ts", first);
      await write(root, "src/first.test.ts", first);
      let result = runAt(root, "pnpm", ["lint:similarity"]);
      assert.equal(result.status, 0, result.output);
      await write(root, "src/second.ts", second);
      result = runAt(root, "pnpm", ["lint:duplicates"]);
      assert.equal(result.status, 0, result.output);
      result = runAt(root, "pnpm", ["lint:similarity"]);
      assert.notEqual(result.status, 0, result.output);
      assert.match(
        result.output,
        /Similarity|similarity.*found|similar functions/i,
      );
    },
  );
}

test("similarity refuses missing binary, wrong version, no sources and parser errors", async () => {
  const root = await copyPreset("node");
  const binary = join(root, ".tools/similarity/similarity-ts");
  await rename(binary, binary + ".saved");
  let result = runAt(root, "pnpm", ["lint:similarity"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(
    result.output,
    /similarity-ts.*not installed|ENOENT|missing.*similarity/i,
  );
  await write(
    root,
    ".tools/similarity/similarity-ts",
    "#!/bin/sh\nprintf 'similarity-ts 0.4.0\\n'\n",
  );
  await chmod(binary, 0o755);
  result = runAt(root, "pnpm", ["lint:similarity"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /Expected similarity-ts 0.5.0/);
  await rename(binary, binary + ".wrong");
  await rename(binary + ".saved", binary);
  await rename(join(root, "src"), join(root, "source.saved"));
  result = runAt(root, "pnpm", ["lint:similarity"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /source|src/i);
  await mkdir(join(root, "src"));
  await write(root, "src/only.test.ts", first);
  result = runAt(root, "pnpm", ["lint:similarity"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /No product source files/);
  await rename(join(root, "src"), join(root, "test-only.saved"));
  await rename(join(root, "source.saved"), join(root, "src"));
  await write(root, "src/invalid.ts", "export function broken( {\n");
  result = runAt(root, "pnpm", ["lint:similarity"]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /pars|syntax/i);
});

test("quality scanners reject a symlinked src directory rather than scanning outside it", async () => {
  const root = await copyPreset("node");
  await rename(join(root, "src"), join(root, "original-src"));
  await symlink("original-src", join(root, "src"), "dir");
  for (const command of ["lint:duplicates", "lint:similarity"]) {
    const result = runAt(root, "pnpm", [command]);
    assert.notEqual(result.status, 0, result.output);
    assert.match(result.output, /symlink|source directory/i);
  }
});
