import test from "node:test";
import assert from "node:assert/strict";
import { cp, mkdir, readFile, rm } from "node:fs/promises";
import { basename, join } from "node:path";
import { ROOT, write, expectResult } from "./helpers.mjs";
import { createWebGameFixture, browserEnv } from "./web-game-fixture.mjs";

// Removing WASM support, browser type boundaries or E2E from check must break this.
test(
  "web-game preset runs a 3D game from an isolated copy and fails closed",
  { timeout: 1_200_000 },
  async (t) => {
    const root = await createWebGameFixture();
    const run = (args, status = 0, diagnostic) =>
      expectResult(root, args, status, diagnostic, browserEnv);
    const product = await readFile(join(root, "src/index.ts"), "utf8");
    const unit = await readFile(join(root, "tests/physics.test.ts"), "utf8");
    const e2e = await readFile(join(root, "tests/e2e/game.spec.ts"), "utf8");
    const evidence = join(ROOT, ".verification/evidence", basename(root));
    const preserve = async (mode) => {
      await mkdir(evidence, { recursive: true });
      await cp(join(root, "test-results"), join(evidence, mode), {
        recursive: true,
      });
    };

    await t.test(
      "check includes real production-preview WebGL and WASM E2E",
      async () => {
        await run(["check"]);
        await preserve("preview");
      },
    );
    await t.test(
      "development server also supports rendering physics input and resize",
      async () => {
        await run(["test:e2e"]);
        await preserve("dev");
      },
    );
    await t.test("browser product rejects Node globals", async () => {
      await write(
        root,
        "src/invalid.ts",
        "export const invalid = process.pid;\n",
      );
      await run(["typecheck"], 1, /process/);
      await run(["lint"], 1, /no-unsafe|process/);
      // An untested product file would fail the 90% coverage gate in later checks.
      await rm(join(root, "src/invalid.ts"));
    });
    await t.test("E2E runner cannot access DOM directly", async () => {
      await write(
        root,
        "tests/e2e/invalid.ts",
        "export const invalid = document.title;\n",
      );
      await run(["typecheck"], 1, /document/);
      await run(["lint"], 1, /document|no-restricted-globals|no-unsafe/);
      await write(root, "tests/e2e/invalid.ts", "export const valid = 1;\n");
    });
    await t.test("E2E and unit runners do not overlap", async () => {
      const result = await run(["test", "--reporter=verbose"]);
      assert.match(result.output, /physics.test.ts/);
      assert.doesNotMatch(result.output, /game.spec.ts/);
    });
    await t.test("empty unit suite is not success", async () => {
      await write(root, "tests/physics.test.ts", "export {};\n");
      try {
        await run(["test"], 1, /No test suite found|No tests found/);
      } finally {
        await write(root, "tests/physics.test.ts", unit);
      }
    });
    await t.test("empty E2E suite is not success", async () => {
      await write(root, "tests/e2e/game.spec.ts", "export {};\n");
      try {
        await run(["test:e2e"], 1, /No tests found/);
      } finally {
        await write(root, "tests/e2e/game.spec.ts", e2e);
      }
    });
    await t.test(
      "focused and skipped browser tests are lint errors",
      async () => {
        for (const modifier of ["only", "skip"]) {
          await write(
            root,
            "tests/e2e/game.spec.ts",
            e2e.replace("test(", "test." + modifier + "("),
          );
          try {
            await run(
              ["lint"],
              1,
              /playwright\/no-focused-test|playwright\/no-skipped-test/,
            );
          } finally {
            await write(root, "tests/e2e/game.spec.ts", e2e);
          }
        }
      },
    );
    await t.test("runtime errors make browser verification fail", async () => {
      await write(
        root,
        "src/index.ts",
        product +
          '\nqueueMicrotask(() => { throw new Error("intentional-runtime-failure"); });\n',
      );
      try {
        await run(["test:e2e"], 1, /intentional-runtime-failure/);
      } finally {
        await write(root, "src/index.ts", product);
      }
    });
    await t.test(
      "missing resources make browser verification fail",
      async () => {
        await write(
          root,
          "src/index.ts",
          product +
            '\nvoid fetch("/missing-3d-verification.bin", { headers: { Accept: "application/octet-stream" } });\n',
        );
        try {
          await run(["test:e2e"], 1, /missing-3d-verification|404/);
        } finally {
          await write(root, "src/index.ts", product);
        }
      },
    );
    await t.test(
      "WASM initialization failure is not a browser pass",
      async () => {
        await write(
          root,
          "src/index.ts",
          product.replace(
            "await RAPIER.init();",
            'throw new Error("intentional-wasm-failure");',
          ),
        );
        try {
          await run(["test:e2e"], 1, /ready|intentional-wasm-failure/);
        } finally {
          await write(root, "src/index.ts", product);
        }
      },
    );
    await t.test("restored copy remains green", async () => {
      await run(["format"]);
      await run(["check"]);
    });
    await t.test("check cannot pass when production E2E fails", async () => {
      await write(
        root,
        "tests/e2e/game.spec.ts",
        e2e.replace('toHaveText("0.60")', 'toHaveText("999")'),
      );
      try {
        await run(["check"], 1, /999/);
      } finally {
        await write(root, "tests/e2e/game.spec.ts", e2e);
      }
    });
  },
);
