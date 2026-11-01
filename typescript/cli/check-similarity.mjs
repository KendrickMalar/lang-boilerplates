import { readFile, realpath } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { parseSync } from "oxc-parser";
import { productSources } from "./quality-sources.mjs";

const root = dirname(fileURLToPath(import.meta.url));

function execute(binary, args, timeout) {
  const result = spawnSync(binary, args, {
    cwd: root,
    encoding: "utf8",
    timeout,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error) {
    throw new Error(
      "similarity-ts is not installed or could not run: " +
        result.error.message,
    );
  }
  if (result.signal || result.status === null)
    throw new Error("similarity-ts did not complete.");
  return result;
}

try {
  if ((await realpath(process.cwd())) !== (await realpath(root))) {
    throw new Error("Run similarity checks at the project root.");
  }
  const binary = join(
    root,
    ".tools",
    "similarity",
    process.platform === "win32" ? "similarity-ts.exe" : "similarity-ts",
  );
  const version = execute(binary, ["--version"], 15000);
  if (
    version.status !== 0 ||
    version.stdout.trim() !== "similarity-ts 0.5.0" ||
    version.stderr.trim()
  ) {
    throw new Error(
      "Expected similarity-ts 0.5.0. Install the pinned tool explicitly.",
    );
  }
  const files = await productSources(root);
  for (const file of files) {
    const source = await readFile(file, "utf8");
    const parsed = parseSync(relative(root, file), source);
    if (parsed.errors.length > 0) {
      throw new Error(
        "Similarity parser errors in " +
          relative(root, file) +
          ": " +
          parsed.errors.map((error) => error.message).join("; "),
      );
    }
  }
  const result = execute(
    binary,
    [
      ...files.map((file) => relative(root, file)),
      "--threshold",
      "0.90",
      "--min-tokens",
      "50",
      "--no-types",
      "--no-fast",
      "--fail-on-duplicates",
    ],
    120000,
  );
  process.stdout.write(result.stdout);
  const expectedWarning =
    "Warning: Both --min-lines and --min-tokens specified. Using --min-tokens=50";
  const stderr = result.stderr
    .split(/\r?\n/)
    .filter((line) => line.trim() && line !== expectedWarning)
    .join("\n");
  if (stderr)
    throw new Error("Similarity inspection reported errors: " + stderr);
  if (result.status !== 0)
    throw new Error(
      "Similarity check failed (exit " + result.status.toString() + ").",
    );
  console.log(
    "Similarity check passed: " +
      files.length.toString() +
      " source files; threshold 90%, minimum 50 AST nodes.",
  );
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
