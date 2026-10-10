import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./helpers.mjs";

test("common config and Node manifest exist with safe verification contract", () => {
  const basePath = join(ROOT, "typescript/tsconfig.base.json");
  assert.ok(existsSync(basePath), "missing shared TypeScript configuration");
  const options = JSON.parse(readFileSync(basePath, "utf8")).compilerOptions;
  for (const flag of [
    "strict",
    "noUncheckedIndexedAccess",
    "exactOptionalPropertyTypes",
    "verbatimModuleSyntax",
    "forceConsistentCasingInFileNames",
  ])
    assert.equal(options[flag], true);
  const manifest = JSON.parse(
    readFileSync(join(ROOT, "typescript/presets/node/package.json"), "utf8"),
  );
  assert.equal(manifest.packageManager, "pnpm@12.6.0");
  assert.equal(manifest.private, true);
  assert.equal(
    manifest.scripts.check,
    "pnpm typecheck && pnpm lint && pnpm format:check && pnpm test && pnpm build",
  );
  assert.equal(manifest.scripts.prepare, undefined);
  assert.equal(manifest.scripts.postinstall, undefined);
  assert.equal(manifest.devDependencies.typescript, "6.0.3");
});
