import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { copyPreset, expectResult, runAt } from "./helpers.mjs";
test("library emits only product JavaScript and type declarations with valid exports", async () => {
  const root = await copyPreset("library");
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
