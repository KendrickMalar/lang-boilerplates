import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { copyPreset, write, runAt } from "./helpers.mjs";

function git(root, ...args) {
  const result = runAt(root, "git", args);
  assert.equal(result.status, 0, result.output);
  return result.output.trim();
}

test("commit rejects type errors, failing tests, untracked and unstaged changes without changing HEAD", async () => {
  const root = await copyPreset("cli");
  git(root, "init", "-b", "main");
  const husky = runAt(root, "pnpm", ["exec", "husky"]);
  assert.equal(husky.status, 0, husky.output);
  git(root, "add", ".");
  git(root, "commit", "-m", "valid baseline");
  const before = git(root, "rev-parse", "HEAD");
  const original = await readFile(join(root, "src/index.ts"), "utf8");
  const testSource = await readFile(join(root, "tests/index.test.ts"), "utf8");
  for (const [file, source, diagnostic] of [
    ["src/index.ts", 'export const value: number = "bad";\n', /TS2322/],
    [
      "src/index.ts",
      original.replace("a + b", "a+b"),
      /Code style issues|Formatting issues/,
    ],
    [
      "src/index.ts",
      original +
        "\nexport function tooLong(value: number): number {\n" +
        "value += 1;\n".repeat(48) +
        "return value;\n}\n",
      /max-lines-per-function/,
    ],
    [
      "tests/index.test.ts",
      testSource.replace("toBe(3)", "toBe(4)"),
      /AssertionError|expected 3 to be 4/,
    ],
  ]) {
    await write(root, file, source);
    git(root, "add", file);
    const result = runAt(root, "git", ["commit", "-m", "rejected fixture"]);
    assert.notEqual(result.status, 0, result.output);
    assert.match(result.output, diagnostic);
    assert.equal(git(root, "rev-parse", "HEAD"), before);
    await write(root, file, file.startsWith("src/") ? original : testSource);
    git(root, "add", file);
  }
  await write(root, "src/index.ts", original + "// not staged\n");
  let result = runAt(root, "git", [
    "commit",
    "--allow-empty",
    "-m",
    "unstaged fixture",
  ]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /unstaged/i);
  assert.equal(
    await readFile(join(root, "src/index.ts"), "utf8"),
    original + "// not staged\n",
  );
  await write(root, "src/index.ts", original);
  await write(root, "untracked.txt", "must be staged or explicitly ignored\n");
  result = runAt(root, "git", [
    "commit",
    "--allow-empty",
    "-m",
    "untracked fixture",
  ]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /untracked/i);
  assert.equal(git(root, "rev-parse", "HEAD"), before);
  git(root, "add", "untracked.txt");
  git(root, "commit", "-m", "valid staged change");
  assert.notEqual(git(root, "rev-parse", "HEAD"), before);
});

for (const mode of ["unstaged", "index"]) {
  test(
    "commit detects " + mode + " changes made by check without undoing them",
    async () => {
      const root = await copyPreset("cli");
      const pkg = JSON.parse(
        await readFile(join(root, "package.json"), "utf8"),
      );
      pkg.scripts.check = "node mutate-check.mjs";
      await write(root, "package.json", JSON.stringify(pkg, null, 2) + "\n");
      await write(
        root,
        "mutate-check.mjs",
        'import { appendFileSync } from "node:fs";\nimport { execFileSync } from "node:child_process";\n' +
          'appendFileSync("src/index.ts", "// changed during check\\n");\n' +
          (mode === "index"
            ? 'execFileSync("git", ["add", "src/index.ts"]);\n'
            : ""),
      );
      git(root, "init", "-b", "main");
      git(root, "add", ".");
      git(root, "commit", "-m", "fixture before activation");
      const head = git(root, "rev-parse", "HEAD");
      const installed = runAt(root, "pnpm", ["exec", "husky"]);
      assert.equal(installed.status, 0, installed.output);
      const result = runAt(root, "git", [
        "commit",
        "--allow-empty",
        "-m",
        "reject mutation",
      ]);
      assert.notEqual(result.status, 0, result.output);
      assert.match(
        result.output,
        mode === "index" ? /staged content changed/ : /Unstaged changes/,
      );
      assert.equal(git(root, "rev-parse", "HEAD"), head);
      assert.match(
        await readFile(join(root, "src/index.ts"), "utf8"),
        /changed during check/,
      );
    },
  );
}

test("structural clones that pass jscpd cannot be committed", async () => {
  const root = await copyPreset("cli");
  git(root, "init", "-b", "main");
  const installed = runAt(root, "pnpm", ["exec", "husky"]);
  assert.equal(installed.status, 0, installed.output);
  git(root, "add", ".");
  git(root, "commit", "-m", "valid before structural clones");
  const head = git(root, "rev-parse", "HEAD");
  const first =
    "export function first(input: number): number {\n  let result = input;\n" +
    Array.from(
      { length: 30 },
      (_, index) => `  result = Math.max(result + ${index + 1}, ${index + 2});`,
    ).join("\n") +
    "\n  return result;\n}\n";
  await write(root, "src/domain/first.ts", first);
  await write(
    root,
    "src/domain/second.ts",
    first
      .replaceAll("first", "second")
      .replaceAll("input", "value")
      .replaceAll("result", "output"),
  );
  const duplication = runAt(root, "pnpm", ["lint:duplicates"]);
  assert.equal(duplication.status, 0, duplication.output);
  git(root, "add", "src/domain/first.ts", "src/domain/second.ts");
  const result = runAt(root, "git", [
    "commit",
    "-m",
    "reject structural clones",
  ]);
  assert.notEqual(result.status, 0, result.output);
  assert.match(result.output, /Similarity check failed/);
  assert.equal(git(root, "rev-parse", "HEAD"), head);
});

for (const flag of ["--assume-unchanged", "--skip-worktree"]) {
  test("commit refuses hidden working-tree changes via " + flag, async () => {
    const root = await copyPreset("cli");
    git(root, "init", "-b", "main");
    const installed = runAt(root, "pnpm", ["exec", "husky"]);
    assert.equal(installed.status, 0, installed.output);
    git(root, "add", ".");
    git(root, "commit", "-m", "valid before hidden changes");
    const head = git(root, "rev-parse", "HEAD");
    const original = await readFile(join(root, "src/index.ts"), "utf8");
    await write(
      root,
      "src/index.ts",
      'export const invalid: number = "bad";\n',
    );
    git(root, "add", "src/index.ts");
    git(root, "update-index", flag, "src/index.ts");
    await write(root, "src/index.ts", original);
    const rejected = runAt(root, "git", [
      "commit",
      "-m",
      "reject hidden bad staged content",
    ]);
    assert.notEqual(rejected.status, 0, rejected.output);
    assert.match(
      rejected.output,
      /index flags|assume-unchanged|skip-worktree/i,
    );
    assert.equal(git(root, "rev-parse", "HEAD"), head);
    assert.equal(await readFile(join(root, "src/index.ts"), "utf8"), original);
    assert.match(git(root, "show", ":src/index.ts"), /invalid: number = "bad"/);
  });
}
