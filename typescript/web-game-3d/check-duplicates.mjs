import { stat, realpath } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { productSources } from "./quality-sources.mjs";

const root = dirname(fileURLToPath(import.meta.url));
try {
  if ((await realpath(process.cwd())) !== (await realpath(root)))
    throw new Error("Run duplication checks at the project root.");
  const files = await productSources(root);
  let maxSize = 1;
  for (const file of files)
    maxSize = Math.max(maxSize, (await stat(file)).size);
  // The engine otherwise silently skips files above its default 1 MiB limit.
  const result = spawnSync(
    process.execPath,
    [
      join(root, "node_modules", "jscpd", "run-jscpd.js"),
      "--config",
      ".jscpd.json",
      "--max-size",
      maxSize.toString(),
      "--no-gitignore",
      ...files.map((file) => relative(root, file)),
    ],
    { cwd: root, stdio: "inherit", timeout: 120000 },
  );
  if (result.error || result.status !== 0)
    throw new Error(
      "Duplication check failed" +
        (result.error ? ": " + result.error.message : "."),
    );
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
