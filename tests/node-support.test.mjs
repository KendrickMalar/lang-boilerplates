import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { ROOT } from "./helpers.mjs";

const require = createRequire(import.meta.url);
const pluginRequire = createRequire(require.resolve("eslint-plugin-n"));
const semver = pluginRequire("semver");

test("all project manifests describe the actually supported Node release lines", () => {
  for (const relative of [
    "package.json",
    "typescript/node/package.json",
    "typescript/web/package.json",
    "typescript/web-game-3d/package.json",
    "typescript/library/package.json",
  ]) {
    const pkg = JSON.parse(readFileSync(join(ROOT, relative), "utf8"));
    for (const [version, supported] of [
      ["24.0.0", false],
      ["24.14.0", false],
      ["24.15.0", true],
      ["24.21.0", true],
      ["25.0.0", false],
      ["26.10.0", true],
    ]) {
      assert.equal(
        semver.satisfies(version, pkg.engines.node),
        supported,
        relative + " " + version,
      );
    }
  }
});
