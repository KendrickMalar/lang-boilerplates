import { mkdir, mkdtemp, cp, writeFile } from "node:fs/promises";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

export const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const verification = join(ROOT, ".verification");
let serial = 0;
export function runAt(root, command, args = [], extraEnv = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    timeout: 180000,
    maxBuffer: 16 * 1024 * 1024,
    env: {
      ...process.env,
      HOME: join(verification, "home"),
      XDG_CONFIG_HOME: join(verification, "home", ".config"),
      npm_config_userconfig: join(verification, "home", ".npmrc"),
      GIT_CONFIG_GLOBAL: "/dev/null",
      GIT_CONFIG_NOSYSTEM: "1",
      GIT_AUTHOR_NAME: "Fixture",
      GIT_AUTHOR_EMAIL: "fixture@example.invalid",
      GIT_COMMITTER_NAME: "Fixture",
      GIT_COMMITTER_EMAIL: "fixture@example.invalid",
      ...extraEnv,
    },
  });
  if (result.error) throw result.error;
  return { status: result.status, output: result.stdout + result.stderr };
}
export async function saveLog(name, result) {
  await mkdir(join(verification, "logs"), { recursive: true });
  await writeFile(
    join(verification, "logs", name + "-" + serial++ + ".log"),
    "Test runner " +
      process.version +
      "\nExit: " +
      result.status +
      "\n" +
      result.output,
  );
}
export async function write(root, path, text) {
  await mkdir(dirname(join(root, path)), { recursive: true });
  await writeFile(join(root, path), text);
}
export async function copyPreset(
  name,
  { dependencies = true, sample = true, tests = true } = {},
) {
  await mkdir(join(verification, "fixtures"), { recursive: true });
  await mkdir(join(verification, "home"), { recursive: true });
  const container = await mkdtemp(join(verification, "fixtures", name + "-"));
  const root = join(container, basename(container));
  await cp(join(ROOT, "typescript", name), root, {
    recursive: true,
    force: false,
    errorOnExist: true,
  });
  if (dependencies) {
    const installed = runAt(root, "pnpm", [
      "install",
      "--ignore-scripts",
      "--engine-strict",
      "--store-dir",
      join(verification, "pnpm-store"),
    ]);
    await saveLog(basename(root) + "-install", installed);
    if (installed.status !== 0) throw new Error(installed.output);
  }
  if (sample) {
    await write(
      root,
      "src/index.ts",
      "export function add(a: number, b: number): number {\n  return a + b;\n}\n",
    );
    if (tests)
      await write(
        root,
        "tests/index.test.ts",
        'import { expect, test } from "vitest";\nimport { add } from "../src/index.js";\ntest("adds", () => {\n  expect(add(1, 2)).toBe(3);\n});\n',
      );
    if (name === "web")
      await write(
        root,
        "index.html",
        '<!doctype html>\n<html><head><title>Fixture</title></head><body><script type="module" src="/src/index.ts"></script></body></html>\n',
      );
  }
  if (dependencies) {
    const formatted = runAt(root, "pnpm", ["exec", "prettier", ".", "--write"]);
    if (formatted.status !== 0) throw new Error(formatted.output);
  }
  return root;
}
export async function expectResult(root, args, status, diagnostic) {
  const result = runAt(root, "pnpm", args);
  await saveLog(basename(root) + "-" + args.join("-"), result);
  if (status === 0 && result.status !== 0) throw new Error(result.output);
  if (status !== 0 && result.status === 0)
    throw new Error("Expected rejection: " + args.join(" "));
  if (diagnostic && !diagnostic.test(result.output))
    throw new Error("Wrong failure: " + result.output);
  return result;
}
