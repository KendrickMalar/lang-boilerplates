import { readdir, lstat } from "node:fs/promises";
import { join, relative } from "node:path";

export async function productSources(root) {
  const sourceDirectory = join(root, "src");
  let info;
  try {
    info = await lstat(sourceDirectory);
  } catch (error) {
    if (error?.code === "ENOENT")
      throw new Error("No product source directory: src", { cause: error });
    throw error;
  }
  if (info.isSymbolicLink() || !info.isDirectory()) {
    throw new Error(
      "Product source directory must be a real directory, not a symlink.",
    );
  }
  const extension = /\.(?:[cm]?[jt]s|tsx)$/;
  const testFile = /\.(?:test|spec)\.(?:[cm]?[jt]s|tsx)$/;
  async function collect(directory) {
    const files = [];
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (entry.name === "__tests__") continue;
      const path = join(directory, entry.name);
      if (entry.isSymbolicLink())
        throw new Error(
          "Product source symlinks are not supported: " + relative(root, path),
        );
      if (entry.isDirectory()) files.push(...(await collect(path)));
      else if (
        entry.isFile() &&
        extension.test(entry.name) &&
        !testFile.test(entry.name)
      )
        files.push(path);
    }
    return files;
  }
  const files = (await collect(sourceDirectory)).sort();
  if (files.length === 0)
    throw new Error("No product source files found for quality checks.");
  return files;
}
