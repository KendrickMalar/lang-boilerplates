import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { copyPreset, write, expectResult } from "./helpers.mjs";
test("web preset checks browser code and builds HTML entry", async () => {
  const root = await copyPreset("web");
  await write(root, "src/browser.ts", "export const title = document.title;\n");
  await expectResult(root, ["check"], 0);
  assert.ok(existsSync(join(root, "dist/index.html")));
});
test("web product rejects Node globals in both typecheck and lint", async () => {
  const root = await copyPreset("web");
  await write(
    root,
    "src/server.ts",
    "export const platform = process.platform;\n",
  );
  await expectResult(root, ["typecheck"], 1, /process/);
  await expectResult(
    root,
    ["lint"],
    1,
    /no-unsafe-assignment|no-unsafe-member-access/,
  );
});

test("web supports Vite assets and import.meta.env in product sources", async () => {
  const root = await copyPreset("web");
  await write(
    root,
    "src/logo.svg",
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>\n',
  );
  await write(
    root,
    "src/vite-features.ts",
    'import logo from "./logo.svg";\nexport const logoUrl: string = logo;\nexport const development: boolean = import.meta.env.DEV;\n',
  );
  await expectResult(root, ["check"], 0);
});
test("Node-executed Vite config rejects DOM usage in typecheck", async () => {
  const root = await copyPreset("web");
  await write(
    root,
    "vite.config.ts",
    'import { defineConfig } from "vite";\nexport const bad = document.title;\nexport default defineConfig({});\n',
  );
  await expectResult(root, ["typecheck"], 1, /document/);
});
test("Node-executed Vite config rejects DOM usage in lint", async () => {
  const root = await copyPreset("web");
  await write(
    root,
    "vite.config.ts",
    'import { defineConfig } from "vite";\nexport const bad = document.title;\nexport default defineConfig({});\n',
  );
  await expectResult(
    root,
    ["lint"],
    1,
    /document|no-restricted-globals|no-unsafe/,
  );
});
