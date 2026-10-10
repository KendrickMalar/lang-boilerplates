import { lstatSync, realpathSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
if (realpathSync(process.cwd()) !== root) {
  throw new Error("Refusing to clean dist outside this project root.");
}
const dist = join(root, "dist");
let info;
try {
  info = lstatSync(dist);
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
if (info?.isSymbolicLink()) {
  throw new Error("Refusing to clean a symbolic link dist.");
}
if (info && !info.isDirectory()) {
  throw new Error("Refusing to clean dist: not a normal directory.");
}
if (info) rmSync(dist, { recursive: true });
