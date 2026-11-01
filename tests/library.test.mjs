import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { rename, mkdir, symlink } from "node:fs/promises";
import { join } from "node:path";
import { ROOT, copyPreset, write, expectResult, runAt } from "./helpers.mjs";
test("library emits only product JavaScript and type declarations with valid exports", async () => {
  const root = await copyPreset("ts-library");
  await expectResult(root, ["check"], 0);
  const files = readdirSync(join(root, "dist"));
  assert.ok(files.includes("index.js"));
  assert.ok(files.includes("index.d.ts"));
  assert.ok(!files.some((name) => /test|config/.test(name)));
  const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  assert.equal(pkg.main, "./dist/index.js");
  assert.equal(pkg.types, "./dist/index.d.ts");
  assert.equal(pkg.exports["."].types, "./dist/index.d.ts");
  assert.equal(pkg.exports["."].import, "./dist/index.js");
  const result = runAt(root, "node", [
    "--input-type=module",
    "-e",
    'import { add } from "./dist/index.js"; console.log(add(2, 3));',
  ]);
  assert.equal(result.status, 0, result.output);
  assert.equal(result.output.trim(), "5");
});

test("library executes colocated tests instead of silently ignoring them", async () => {
  const root = await copyPreset("ts-library");
  await write(
    root,
    "src/internal.test.ts",
    'import { expect, test } from "vitest";\ntest("colocated failing assertion", () => { expect(1).toBe(2); });\n',
  );
  await expectResult(root, ["test"], 1, /colocated failing assertion/);
});
test("library recursively excludes colocated tests from emitted distribution", async () => {
  const root = await copyPreset("ts-library");
  const source =
    'import { expect, test } from "vitest";\ntest("colocated", () => { expect(1).toBe(1); });\n';
  await write(root, "src/internal.test.ts", source);
  await write(root, "src/sub/__tests__/nested.ts", source);
  await expectResult(root, ["build"], 0);
  function walk(dir) {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
      entry.isDirectory()
        ? walk(join(dir, entry.name))
        : [join(dir, entry.name)],
    );
  }
  const emitted = walk(join(root, "dist"));
  assert.ok(
    !emitted.some((path) => /\.test\.|\.spec\.|__tests__/.test(path)),
    emitted.join("\n"),
  );
});

test("library rebuild drops outputs for source moved out of the project", async () => {
  const root = await copyPreset("ts-library");
  await write(root, "src/obsolete.ts", "export const oldValue = 1;\n");
  await expectResult(root, ["build"], 0);
  assert.ok(readdirSync(join(root, "dist")).includes("obsolete.js"));
  await rename(
    join(root, "src/obsolete.ts"),
    join(root, "obsolete.source.txt"),
  );
  await expectResult(root, ["build"], 0);
  const files = readdirSync(join(root, "dist"));
  assert.ok(
    !files.includes("obsolete.js") && !files.includes("obsolete.d.ts"),
    files.join(", "),
  );
});

test("library build refuses symlink dist and preserves its target", async () => {
  const root = await copyPreset("ts-library");
  await mkdir(join(root, "protected"));
  await write(root, "protected/keep.txt", "preserve\n");
  await symlink(join(root, "protected"), join(root, "dist"), "dir");
  await expectResult(root, ["build"], 1, /symbolic link/);
  assert.equal(
    readFileSync(join(root, "protected/keep.txt"), "utf8"),
    "preserve\n",
  );
});
test("library build refuses a non-directory dist without removing it", async () => {
  const root = await copyPreset("ts-library");
  await write(root, "dist", "not generated output\n");
  await expectResult(root, ["build"], 1, /not a normal directory/);
  assert.equal(
    readFileSync(join(root, "dist"), "utf8"),
    "not generated output\n",
  );
});

test("library cleaner refuses invocation outside its project root", async () => {
  const root = await copyPreset("ts-library");
  await expectResult(root, ["build"], 0);
  const result = runAt(ROOT, "node", [join(root, "clean-dist.mjs")]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /outside this project root/);
  assert.ok(readdirSync(join(root, "dist")).includes("index.js"));
});
