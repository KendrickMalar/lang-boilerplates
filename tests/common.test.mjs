import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./helpers.mjs";

test("each leaf includes its own complete safe TypeScript configuration", () => {
  for (const name of ["node", "web", "library", "web-game-3d"]) {
    const dir = join(ROOT, "typescript", name);
    assert.ok(existsSync(dir), "missing standalone template: " + name);
    for (const file of [
      "README.md",
      "LICENSE",
      "package.json",
      "tsconfig.base.json",
      "tsconfig.json",
      "eslint.base.mjs",
      "eslint.config.mjs",
      ".prettierrc.json",
      ".prettierignore",
      ".editorconfig",
      ".gitignore",
      ".node-version",
      "lint-staged.config.mjs",
      "pnpm-workspace.yaml",
      ".husky/pre-commit",
      ".husky/pre-push",
    ]) {
      assert.ok(existsSync(join(dir, file)), name + " missing " + file);
    }
    const options = JSON.parse(
      readFileSync(join(dir, "tsconfig.base.json"), "utf8"),
    ).compilerOptions;
    for (const flag of [
      "strict",
      "noUncheckedIndexedAccess",
      "exactOptionalPropertyTypes",
      "verbatimModuleSyntax",
      "forceConsistentCasingInFileNames",
    ])
      assert.equal(options[flag], true, name + ":" + flag);
    const manifest = JSON.parse(
      readFileSync(join(dir, "package.json"), "utf8"),
    );
    assert.equal(manifest.packageManager, "pnpm@12.6.0");
    assert.equal(manifest.private, true);
    assert.equal(
      manifest.scripts.check,
      name === "web-game-3d"
        ? "pnpm typecheck && pnpm lint && pnpm format:check && pnpm test && pnpm test:e2e:preview"
        : "pnpm typecheck && pnpm lint && pnpm format:check && pnpm test && pnpm build",
    );
    assert.equal(manifest.scripts.prepare, undefined);
    assert.equal(manifest.scripts.postinstall, undefined);
    assert.equal(manifest.devDependencies.typescript, "6.0.3");
    for (const file of readdirSync(dir).filter((name) =>
      /^tsconfig.*\.json$/.test(name),
    )) {
      const config = JSON.parse(readFileSync(join(dir, file), "utf8"));
      if (config.extends)
        assert.ok(
          config.extends.startsWith("./") && !config.extends.includes(".."),
          file,
        );
      for (const ref of config.references ?? [])
        assert.ok(ref.path.startsWith("./") && !ref.path.includes(".."), file);
    }
  }
});
test("TypeScript root contains only the language entry and standalone directories", () => {
  assert.deepEqual(readdirSync(join(ROOT, "typescript")).sort(), [
    "README.md",
    "library",
    "node",
    "web",
    "web-game-3d",
  ]);
});
