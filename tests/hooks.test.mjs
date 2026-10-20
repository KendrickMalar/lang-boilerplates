import test from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { ROOT, copyPreset, write, runAt, saveLog } from "./helpers.mjs";

async function snapshot() {
  const result = spawnSync(
    "git",
    ["config", "--global", "--path", "--get", "core.hooksPath"],
    { encoding: "utf8", env: process.env },
  );
  const path = result.stdout.trim();
  const files = {};
  if (path)
    for (const file of await readdir(path)) {
      const bytes = await readFile(join(path, file));
      files[file] = createHash("sha256").update(bytes).digest("hex");
    }
  return { path, files };
}
function git(root, args) {
  const result = runAt(root, "git", args);
  assert.equal(result.status, 0, result.output);
  return result.output.trim();
}
async function prepare(root) {
  git(root, ["init", "-b", "main"]);
  const husky = runAt(root, "pnpm", ["exec", "husky"]);
  assert.equal(husky.status, 0, husky.output);
  git(root, ["add", "."]);
  git(root, ["commit", "-m", "fixture baseline"]);
}
test("real commit hook rejects unsafe code and preserves HEAD", async () => {
  const baseline = await snapshot();
  const root = await copyPreset("node");
  await prepare(root);
  const before = git(root, ["rev-parse", "HEAD"]);
  await write(root, "src/unsafe.ts", "Promise.resolve(1);\nexport {};\n");
  git(root, ["add", "src/unsafe.ts"]);
  const commit = runAt(root, "git", ["commit", "-m", "unsafe fixture"]);
  await saveLog("commit-rejected", commit);
  assert.notEqual(commit.status, 0, commit.output);
  assert.match(commit.output, /no-floating-promises/);
  assert.equal(git(root, ["rev-parse", "HEAD"]), before);
  assert.deepEqual(await snapshot(), baseline);
});
test("real push hook accepts valid code then rejects type errors without updating remote", async () => {
  const baseline = await snapshot();
  const root = await copyPreset("node");
  await prepare(root);
  const remote = await mkdtemp(join(ROOT, ".verification/fixtures", "remote-"));
  git(remote, ["init", "--bare"]);
  git(root, ["remote", "add", "origin", remote]);
  git(root, ["push", "-u", "origin", "HEAD:main"]);
  const before = git(remote, ["rev-parse", "refs/heads/main"]);
  await write(root, "src/bad.ts", 'export const value: number = "bad";\n');
  git(root, ["add", "src/bad.ts"]);
  const commit = runAt(root, "git", ["commit", "-m", "type-error fixture"]);
  assert.notEqual(commit.status, 0, commit.output);
  assert.match(commit.output, /TS2322/);
  const push = runAt(root, "git", ["push", "origin", "HEAD:main"]);
  await saveLog("push-rejected", push);
  assert.notEqual(push.status, 0, push.output);
  assert.match(push.output, /TS2322/);
  assert.equal(git(remote, ["rev-parse", "refs/heads/main"]), before);
  assert.deepEqual(await snapshot(), baseline);
});
test("dependency install preserves pre-existing hooks and global hooks", async () => {
  const baseline = await snapshot();
  const root = await copyPreset("node", { dependencies: false, sample: false });
  git(root, ["init", "-b", "main"]);
  await write(root, ".existing-hooks/pre-commit", "#!/bin/sh\nexit 0\n");
  git(root, ["config", "core.hooksPath", ".existing-hooks"]);
  const content = await readFile(
    join(root, ".existing-hooks/pre-commit"),
    "utf8",
  );
  const installed = runAt(root, "pnpm", [
    "install",
    "--ignore-scripts",
    "--store-dir",
    join(ROOT, ".verification/pnpm-store"),
  ]);
  await saveLog("install-hooks-preserved", installed);
  assert.equal(installed.status, 0, installed.output);
  assert.equal(
    git(root, ["config", "--get", "core.hooksPath"]),
    ".existing-hooks",
  );
  assert.equal(
    await readFile(join(root, ".existing-hooks/pre-commit"), "utf8"),
    content,
  );
  assert.deepEqual(await snapshot(), baseline);
});
