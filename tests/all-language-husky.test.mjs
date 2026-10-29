import test from "node:test";
import assert from "node:assert/strict";
import {
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { ROOT } from "./helpers.mjs";

const leaves = [
  "rust/tauri",
  "swift/macos",
  "swift/ios",
  "roblox/rojo",
  "godot/mobile",
  "blender/assets",
];
// Only the slow native compiler/test command is substituted. Git and Husky are real.
function fixture(leaf) {
  const parent = join(ROOT, ".verification", "husky-unification");
  mkdirSync(parent, { recursive: true });
  const sandbox = mkdtempSync(join(parent, "case-"));
  const root = join(sandbox, "project");
  cpSync(join(ROOT, leaf), root, { recursive: true });
  const env = {
    ...process.env,
    HOME: join(sandbox, "home"),
    XDG_CONFIG_HOME: join(sandbox, "home/.config"),
    GIT_CONFIG_GLOBAL: "/dev/null",
    GIT_CONFIG_NOSYSTEM: "1",
    GIT_AUTHOR_NAME: "Fixture",
    GIT_AUTHOR_EMAIL: "fixture@example.invalid",
    GIT_COMMITTER_NAME: "Fixture",
    GIT_COMMITTER_EMAIL: "fixture@example.invalid",
    HUSKY: "1",
  };
  for (const key of Object.keys(env))
    if (
      /^GIT_(DIR|WORK_TREE|INDEX_FILE|COMMON_DIR|CONFIG_COUNT|CONFIG_KEY_|CONFIG_VALUE_)/.test(
        key,
      )
    )
      delete env[key];
  mkdirSync(env.HOME, { recursive: true });
  const run = (command, args, options = {}) =>
    spawnSync(command, args, {
      cwd: root,
      env,
      encoding: "utf8",
      timeout: 30000,
      ...options,
    });
  const git = (...args) => {
    const r = run("git", args);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    return r.stdout.trim();
  };
  const packagePath = join(root, "package.json");
  const pkg = JSON.parse(readFileSync(packagePath, "utf8"));
  pkg.scripts.check = "node verify.mjs";
  // Preserve the real Luau guard route in the template; this fixture exercises generic hook plumbing.
  delete pkg.scripts["check:git"];
  writeFileSync(packagePath, JSON.stringify(pkg, null, 2) + "\n");
  writeFileSync(
    join(root, "verify.mjs"),
    'import {readFileSync} from "node:fs";\nif(readFileSync("input.txt","utf8").includes("FAIL")) { console.error("native test failed"); process.exit(17); }\n',
  );
  writeFileSync(join(root, "input.txt"), "PASS\n");
  writeFileSync(
    join(root, ".gitignore"),
    readFileSync(join(root, ".gitignore"), "utf8") +
      "\n/node_modules/\n/.husky/_/\n",
  );
  const dependencies = run("pnpm", [
    "install",
    "--ignore-scripts",
    "--engine-strict",
    "--store-dir",
    join(ROOT, ".verification/pnpm-store"),
  ]);
  assert.equal(
    dependencies.status,
    0,
    dependencies.stdout + dependencies.stderr,
  );
  git("init", "-q", "-b", "fixture");
  // Run actual Husky 9.1.7 after the explicit dependency install, never from a hook.
  const installed = run(process.execPath, [
    join(ROOT, "node_modules/husky/bin.js"),
  ]);
  assert.equal(installed.status, 0, installed.stdout + installed.stderr);
  assert.equal(git("config", "--local", "--get", "core.hooksPath"), ".husky/_");
  git("add", ".");
  git("commit", "-qm", "normal fixture");
  return { root, sandbox, env, run, git };
}

for (const leaf of leaves) {
  test(`${leaf}: real Husky rejects failing tests at commit and push, preserving refs`, () => {
    const f = fixture(leaf);
    const head = f.git("rev-parse", "HEAD");
    const remote = join(f.sandbox, "remote.git");
    assert.equal(f.run("git", ["init", "--bare", "-q", remote]).status, 0);
    f.git("push", remote, "HEAD:refs/heads/fixture");
    writeFileSync(join(f.root, "input.txt"), "FAIL\n");
    f.git("add", "input.txt");
    const commit = f.run("git", ["commit", "-qm", "must reject"]);
    assert.notEqual(commit.status, 0);
    assert.match(commit.stdout + commit.stderr, /native test failed/);
    assert.equal(f.git("rev-parse", "HEAD"), head);
    const push = f.run("git", ["push", remote, "HEAD:refs/heads/other"]);
    assert.notEqual(push.status, 0);
    assert.match(push.stdout + push.stderr, /native test failed/);
    assert.equal(f.git("ls-remote", remote, "refs/heads/other"), "");
    assert.equal(
      f.git("ls-remote", remote, "refs/heads/fixture").split(/\s/)[0],
      head,
    );
  });
}

for (const fault of [
  "unstaged",
  "untracked",
  "assume-unchanged",
  "skip-worktree",
  "index-mutation",
]) {
  test(`native commit gate rejects ${fault} without undoing user changes`, () => {
    const f = fixture("swift/macos");
    const head = f.git("rev-parse", "HEAD");
    if (fault === "untracked") writeFileSync(join(f.root, "new.txt"), "keep");
    else if (fault === "index-mutation") {
      writeFileSync(
        join(f.root, "verify.mjs"),
        'import {writeFileSync} from "node:fs"; import {execFileSync} from "node:child_process"; writeFileSync("input.txt","mutated"); execFileSync("git",["add","input.txt"]);\n',
      );
      f.git("add", "verify.mjs");
    } else {
      if (fault !== "unstaged")
        f.git("update-index", "--" + fault, "input.txt");
      writeFileSync(join(f.root, "input.txt"), "keep unstaged");
    }
    const result = f.run("git", [
      "commit",
      "--allow-empty",
      "-qm",
      "reject unsafe index",
    ]);
    assert.notEqual(result.status, 0, result.stdout + result.stderr);
    assert.match(
      result.stdout + result.stderr,
      /Unstaged|Untracked|index flags|staged content changed/,
    );
    assert.equal(f.git("rev-parse", "HEAD"), head);
    if (fault === "untracked")
      assert.equal(readFileSync(join(f.root, "new.txt"), "utf8"), "keep");
    else
      assert.match(
        readFileSync(join(f.root, "input.txt"), "utf8"),
        /keep unstaged|mutated/,
      );
  });
}

test("root Husky runs both nested language checks; the second failure blocks commit", () => {
  const f = fixture("godot/mobile");
  const pkgPath = join(f.root, "package.json");
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  pkg.scripts.check =
    "sh game/scripts/check.sh all && sh art/scripts/check.sh all";
  writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  for (const name of ["game", "art"]) {
    mkdirSync(join(f.root, name, "scripts"), { recursive: true });
    writeFileSync(
      join(f.root, name, "scripts/check.sh"),
      `#!/bin/sh\n[ "$1" = all ] || exit 9\nprintf '${name} checked\\n'\n${name === "art" ? "exit 19" : "exit 0"}\n`,
    );
  }
  f.git("add", ".");
  const before = f.git("rev-parse", "HEAD");
  const result = f.run("git", ["commit", "-qm", "reject second language"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout + result.stderr, /game checked[\s\S]*art checked/);
  assert.equal(f.git("rev-parse", "HEAD"), before);
});

test("Roblox Husky preserves exact push update stdin for its existing Luau guard", () => {
  const f = fixture("roblox/rojo");
  const pkgPath = join(f.root, "package.json");
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  pkg.scripts["check:git"] = "node guard.mjs";
  writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  writeFileSync(
    join(f.root, "guard.mjs"),
    'import {readFileSync} from "node:fs"; if(process.argv[2]!=="push" || readFileSync(0,"utf8")!=="exact update\\n") process.exit(31);\n',
  );
  f.git("add", ".");
  const result = f.run("sh", [".husky/pre-push"], { input: "exact update\n" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("global bridge preserves existing dispatcher and runs the current linked worktree gate", () => {
  const f = fixture("swift/macos");
  const global = join(f.sandbox, "global-hooks");
  mkdirSync(global);
  const config = join(f.sandbox, "gitconfig");
  for (const hook of ["pre-commit", "pre-push"]) {
    writeFileSync(
      join(global, hook),
      '#!/bin/sh\nexec "$(git rev-parse --git-common-dir)/hooks/' +
        hook +
        '" "$@"\n',
      { mode: 0o700 },
    );
  }
  writeFileSync(config, "[core]\n  hooksPath = " + global + "\n");
  f.env.GIT_CONFIG_GLOBAL = config;
  f.git("config", "--local", "--unset", "core.hooksPath");
  const globalBefore = readFileSync(join(global, "pre-commit"));
  for (const hook of ["pre-commit", "pre-push"]) {
    writeFileSync(
      join(f.root, ".git/hooks", hook),
      '#!/bin/sh\nroot="$(git rev-parse --show-toplevel)" || exit 1\ncd "$root" || exit 1\nexport PATH="$root/node_modules/.bin:$PATH"\nexec sh "$root/.husky/' +
        hook +
        '" "$@"\n',
      { mode: 0o700 },
    );
  }
  const linked = join(f.sandbox, "linked");
  f.git("worktree", "add", "-b", "linked", linked);
  // Each worktree needs its own explicitly installed dependencies.
  let r = f.run(
    "pnpm",
    [
      "install",
      "--ignore-scripts",
      "--engine-strict",
      "--store-dir",
      join(ROOT, ".verification/pnpm-store"),
    ],
    { cwd: linked },
  );
  assert.equal(r.status, 0, r.stdout + r.stderr);
  writeFileSync(join(linked, "input.txt"), "FAIL linked\n");
  r = f.run("git", ["add", "input.txt"], { cwd: linked });
  assert.equal(r.status, 0, r.stderr);
  const before = f.git("rev-parse", "linked");
  r = f.run("git", ["commit", "-qm", "reject linked"], { cwd: linked });
  assert.notEqual(r.status, 0);
  assert.match(r.stdout + r.stderr, /native test failed/);
  assert.equal(f.git("rev-parse", "linked"), before);
  assert.equal(readFileSync(join(f.root, "input.txt"), "utf8"), "PASS\n");
  assert.deepEqual(readFileSync(join(global, "pre-commit")), globalBefore);
  assert.equal(
    f.run("git", ["config", "--local", "--get", "core.hooksPath"], {
      cwd: linked,
    }).status,
    1,
  );
});

test("foreign hook cannot silently run a different project's gate", () => {
  const source = fixture("roblox/rojo");
  const other = fixture("roblox/rojo");
  const result = other.run("sh", [join(source.root, ".husky/pre-commit")]);
  assert.notEqual(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /project root/);
});

test("stale dependencies block commit without implicit install or lock mutation", () => {
  const f = fixture("swift/macos");
  const pkgPath = join(f.root, "package.json");
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  pkg.devDependencies.husky = "0.0.0";
  writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  f.git("add", "package.json");
  const before = f.git("rev-parse", "HEAD");
  const lockBefore = readFileSync(join(f.root, "pnpm-lock.yaml"));
  // Any accidental registry access fails locally, not against a third-party service.
  f.env.npm_config_registry = "http://127.0.0.1:9";
  const result = f.run("git", ["commit", "-qm", "reject stale dependencies"]);
  assert.notEqual(result.status, 0);
  assert.match(
    result.stdout + result.stderr,
    /ERR_PNPM_VERIFY_DEPS_BEFORE_RUN/,
  );
  assert.equal(f.git("rev-parse", "HEAD"), before);
  assert.deepEqual(readFileSync(join(f.root, "pnpm-lock.yaml")), lockBefore);
});
