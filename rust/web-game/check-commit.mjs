import { spawnSync } from "node:child_process";
import { realpathSync, readFileSync } from "node:fs";

function git(args) {
    const result = spawnSync("git", args, {
        encoding: "utf8",
        maxBuffer: 16 * 1024 * 1024,
    });
    if (result.error || result.status !== 0) {
        throw new Error(
            "Git inspection failed: " +
                (result.error?.message ?? result.stderr),
        );
    }
    return result.stdout;
}

function assertStaged() {
    if (
        git(["ls-files", "-v", "-z"])
            .split("\0")
            .some((entry) => /^[a-zS] /.test(entry))
    ) {
        throw new Error(
            "Unsupported Git index flags: remove assume-unchanged/skip-worktree explicitly before committing.",
        );
    }
    if (git(["diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z"])) {
        throw new Error(
            "Unstaged changes: stage all changes before committing. No files were stashed or staged automatically.",
        );
    }
    if (git(["ls-files", "--others", "--exclude-standard", "-z"])) {
        throw new Error(
            "Untracked files: stage them or explicitly ignore them before committing.",
        );
    }
}

try {
    const mode = process.argv[2] ?? "commit";
    if (process.argv.length > 3 || !["commit", "push"].includes(mode)) {
        throw new Error("usage: node check-commit.mjs [commit|push]");
    }
    if (
        realpathSync(git(["rev-parse", "--show-toplevel"]).trim()) !==
        realpathSync(process.cwd())
    ) {
        throw new Error("Run the commit gate at the Git project root.");
    }
    if (mode === "commit") assertStaged();
    const staged = git([
        "diff",
        "--cached",
        "--no-ext-diff",
        "--no-textconv",
        "--raw",
        "--no-abbrev",
        "-z",
    ]);
    const manifest = JSON.parse(readFileSync("package.json", "utf8"));
    const script = manifest.scripts?.["check:git"] ? "check:git" : "check";
    const args = ["run", script, ...(script === "check:git" ? [mode] : [])];
    const check = spawnSync("pnpm", args, {
        stdio: "inherit",
        // pnpm injects false into nested scripts; re-enable the outer Git gate explicitly.
        env: { ...process.env, pnpm_config_verify_deps_before_run: "error" },
        shell: process.platform === "win32",
    });
    if (check.error || check.status !== 0) {
        throw new Error(
            "Commit checks failed" +
                (check.error ? ": " + check.error.message : "."),
        );
    }
    if (mode === "push") process.exit(0);
    assertStaged();
    if (
        staged !==
        git([
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-textconv",
            "--raw",
            "--no-abbrev",
            "-z",
        ])
    ) {
        throw new Error(
            "The staged content changed during checks. Run the commit again.",
        );
    }
} catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
}
