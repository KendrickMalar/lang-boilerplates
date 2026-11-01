import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./helpers.mjs";

const dir = join(ROOT, "typescript/web-game");
test("web-game preset is independently copyable without product sources", () => {
  assert.ok(existsSync(dir), "missing standalone web-game preset");
  for (const file of [
    "package.json",
    "tsconfig.e2e.json",
    "playwright.config.ts",
    "playwright.preview.config.ts",
    "README.md",
  ]) {
    assert.ok(existsSync(join(dir, file)), "missing " + file);
  }
  assert.ok(!existsSync(join(dir, "src")));
  assert.ok(!existsSync(join(dir, "index.html")));
  for (const file of readdirSync(dir).filter((name) =>
    /^tsconfig.*\.json$/.test(name),
  )) {
    const config = JSON.parse(readFileSync(join(dir, file), "utf8"));
    if (config.extends)
      assert.ok(
        config.extends.startsWith("./") && !config.extends.includes(".."),
      );
    for (const ref of config.references ?? [])
      assert.ok(ref.path.startsWith("./") && !ref.path.includes(".."));
  }
});
