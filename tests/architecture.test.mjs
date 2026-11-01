import test from "node:test";
import assert from "node:assert/strict";
import { constants } from "node:fs";
import { copyFile, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  ROOT,
  DEFAULT_ARCHITECTURE,
  copyPreset,
  write,
  runAt,
  saveLog,
  expectResult,
} from "./helpers.mjs";
import { architectureCases } from "./architecture-fixtures.mjs";
import { architectureSection } from "./architecture-readme.mjs";

// Enables a choice exactly as its README section says: the cp commands in its sh block.
async function enableFromReadme(root, leaf, heading) {
  const readme = await readFile(
    join(ROOT, "typescript", leaf, "README.md"),
    "utf8",
  );
  const section = architectureSection(readme, heading);
  const block = /```sh\n([\s\S]*?)```/.exec(section);
  assert.ok(block, leaf + " " + heading + ": missing sh block");
  const copies = [...block[1].matchAll(/^cp (\S+) (\S+)$/gm)];
  assert.ok(copies.length > 0, leaf + " " + heading + ": no cp command");
  for (const [, from, to] of copies)
    await copyFile(join(root, from), join(root, to), constants.COPYFILE_EXCL);
}
async function writeAll(root, files) {
  for (const [path, source] of Object.entries(files))
    await write(root, path, source);
}
async function lintReport(root) {
  const result = runAt(root, "pnpm", [
    "exec",
    "eslint",
    "src",
    "--format",
    "json",
  ]);
  await saveLog("architecture-eslint-json", result);
  const reports = JSON.parse(result.output.slice(result.output.indexOf("[")));
  return new Map(
    reports.map((report) => [
      report.filePath.slice(root.length + 1),
      report.messages,
    ]),
  );
}
function assertReported(report, violation) {
  const messages = report.get(violation.path) ?? [];
  assert.ok(
    messages.some((message) => message.ruleId === violation.rule),
    violation.path +
      " should report " +
      violation.rule +
      ": " +
      JSON.stringify(messages),
  );
}

for (const item of architectureCases) {
  test(
    "architecture " +
      item.leaf +
      " " +
      item.option +
      " passes conforming code and rejects violations",
    { timeout: 600_000 },
    async (t) => {
      const root = await copyPreset(item.leaf, {
        sample: false,
        architecture: false,
      });
      await enableFromReadme(root, item.leaf, item.heading);
      await writeAll(root, item.files);
      await t.test("conforming layout passes lint", async () => {
        await expectResult(root, ["lint"], 0);
      });
      await t.test("each violation is reported by its rule", async () => {
        await writeAll(
          root,
          Object.fromEntries(
            item.violations.map((violation) => [
              violation.path,
              violation.source,
            ]),
          ),
        );
        const report = await lintReport(root);
        for (const violation of item.violations)
          assertReported(report, violation);
        for (const path of Object.keys(item.files).filter((path) =>
          /\.ts$/.test(path),
        ))
          assert.deepEqual(
            (report.get(path) ?? []).filter((message) =>
              /^boundaries\//.test(message.ruleId),
            ),
            [],
            path,
          );
        await expectResult(root, ["lint"], 1, /boundaries\/dependencies/);
      });
      if (item.entryViolation)
        await t.test(
          "entry file cannot reach past allowed elements",
          async () => {
            await write(
              root,
              item.entryViolation.path,
              item.entryViolation.source,
            );
            assertReported(await lintReport(root), item.entryViolation);
            await write(
              root,
              item.entryViolation.path,
              item.files[item.entryViolation.path],
            );
          },
        );
      if (item.cycle)
        await t.test("import cycles fail the lint script", async () => {
          for (const violation of item.violations)
            runAt(root, "rm", ["-f", violation.path]);
          await expectResult(root, ["lint"], 0);
          await writeAll(root, item.cycle);
          await expectResult(root, ["lint"], 1, /no-circular/);
        });
    },
  );
}

test("architecture rules fail closed when the TypeScript resolver is missing", async () => {
  const [item] = architectureCases;
  const root = await copyPreset(item.leaf, {
    sample: false,
    architecture: false,
  });
  await enableFromReadme(root, item.leaf, item.heading);
  await writeAll(root, item.files);
  const path = join(root, "architecture.mjs");
  const config = await readFile(path, "utf8");
  assert.match(config, /"import\/resolver"/);
  await writeFile(
    path,
    config.replace(/"import\/resolver": [\s\S]*?node: true \},\n/, ""),
  );
  await expectResult(root, ["lint"], 1, /boundaries\/dependencies/);
});

for (const [leaf, option] of Object.entries(DEFAULT_ARCHITECTURE)) {
  test(
    leaf + " lint stops when no architecture choice is installed",
    async () => {
      const root = await copyPreset(leaf, { architecture: false });
      const result = await expectResult(
        root,
        ["lint"],
        1,
        /Missing architecture\.mjs/,
      );
      assert.ok(
        result.output.includes(
          "cp architecture/" + option + ".mjs architecture.mjs",
        ),
        result.output,
      );
    },
  );
}
