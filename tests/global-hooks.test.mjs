import test from "node:test";
import assert from "node:assert/strict";
import { chmod, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { ROOT, copyPreset, write, runAt } from "./helpers.mjs";
import { createWebGameFixture, browserEnv } from "./web-game-fixture.mjs";

for (const preset of ["cli", "web", "ts-library", "web-game"]) {
  test(
    preset + " README activates existing global chain without changing it",
    async () => {
      const root =
        preset === "web-game"
          ? await createWebGameFixture()
          : await copyPreset(preset);
      const globalConfig = join(dirname(root), "global.gitconfig");
      const globalHooks = join(dirname(root), "global-hooks");
      const env = { ...browserEnv, GIT_CONFIG_GLOBAL: globalConfig };
      const run = (command, args) => runAt(root, command, args, env);
      const git = (...args) => {
        const result = run("git", args);
        assert.equal(result.status, 0, result.output);
        return result.output.trim();
      };
      git("init", "-b", "main");
      git("add", ".");
      git("commit", "-m", "fixture before hook installation");
      const dispatcher =
        '#!/bin/sh\nhook="$(git rev-parse --git-common-dir)/hooks/$(basename "$0")"\nif test -x "$hook"; then exec "$hook" "$@"; fi\n';
      for (const name of ["pre-commit", "pre-push"]) {
        await write(globalHooks, name, dispatcher);
        await chmod(join(globalHooks, name), 0o755);
      }
      git("config", "--file", globalConfig, "core.hooksPath", globalHooks);
      const configBefore = await readFile(globalConfig, "utf8");
      const readme = await readFile(
        join(ROOT, "typescript", preset, "README.md"),
        "utf8",
      );
      const installation = /```sh\n(set -eu[\s\S]*?)\n```/.exec(readme)?.[1];
      assert.ok(
        installation,
        "README must expose the actual installation command",
      );
      const installed = run("sh", ["-c", installation]);
      assert.equal(installed.status, 0, installed.output);
      assert.equal(
        run("git", ["config", "--local", "--get", "core.hooksPath"]).status,
        1,
      );
      assert.equal(await readFile(globalConfig, "utf8"), configBefore);
      const shared = git(
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
      );
      const wrapperBefore = await readFile(
        join(shared, "hooks/pre-commit"),
        "utf8",
      );
      const repeated = run("sh", ["-c", installation]);
      assert.notEqual(repeated.status, 0, repeated.output);
      assert.equal(
        await readFile(join(shared, "hooks/pre-commit"), "utf8"),
        wrapperBefore,
      );
      git("commit", "--allow-empty", "-m", "valid commit through global chain");
      const head = git("rev-parse", "HEAD");
      const remote = join(dirname(root), "remote.git");
      git("init", "--bare", remote);
      git("remote", "add", "origin", remote);
      git("push", "origin", "HEAD:main");
      if (preset === "cli") {
        const child = join(dirname(root), "linked-worktree");
        git("worktree", "add", "-b", "linked-fixture", child, "HEAD");
        const installed = runAt(
          child,
          "pnpm",
          [
            "install",
            "--ignore-scripts",
            "--engine-strict",
            "--store-dir",
            join(ROOT, ".verification/pnpm-store"),
          ],
          env,
        );
        assert.equal(installed.status, 0, installed.output);
        await write(
          child,
          "src/child.ts",
          'export const child: number = "bad";\n',
        );
        const added = runAt(child, "git", ["add", "src/child.ts"], env);
        assert.equal(added.status, 0, added.output);
        const rejected = runAt(
          child,
          "git",
          ["commit", "-m", "linked worktree rejection"],
          env,
        );
        assert.notEqual(rejected.status, 0, rejected.output);
        assert.match(rejected.output, /TS2322/);
        assert.equal(
          runAt(child, "git", ["rev-parse", "HEAD"], env).output.trim(),
          head,
        );
      }
      await write(
        root,
        "src/invalid.ts",
        'export const invalid: number = "bad";\n',
      );
      git("add", "src/invalid.ts");
      for (const args of [
        ["commit", "-m", "rejected"],
        ["push", "origin", "HEAD:main"],
      ]) {
        const rejected = run("git", args);
        assert.notEqual(rejected.status, 0, rejected.output);
        assert.match(rejected.output, /TS2322/);
      }
      assert.equal(git("rev-parse", "HEAD"), head);
      assert.equal(
        git("--git-dir", remote, "rev-parse", "refs/heads/main"),
        head,
      );
      for (const name of ["pre-commit", "pre-push"]) {
        assert.equal(
          await readFile(join(globalHooks, name), "utf8"),
          dispatcher,
        );
      }
      assert.equal(await readFile(globalConfig, "utf8"), configBefore);
    },
  );
}
