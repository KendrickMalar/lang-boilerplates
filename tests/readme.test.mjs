import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./helpers.mjs";

test("language entry links to all standalone README files", () => {
  const entry = readFileSync(join(ROOT, "typescript/README.md"), "utf8");
  for (const name of ["node", "web", "library", "web-game-3d"]) {
    assert.ok(
      entry.includes("./" + name + "/README.md"),
      "missing language entry: " + name,
    );
  }
});
test("each leaf README describes only its own complete distribution", () => {
  for (const name of ["node", "web", "library", "web-game-3d"]) {
    const dir = join(ROOT, "typescript", name);
    const text = readFileSync(join(dir, "README.md"), "utf8");
    const targets = [...text.matchAll(/\]\(([^\s)#]+)\)/g)]
      .map((match) => match[1])
      .filter((path) => !/^https?:\/\//.test(path));
    assert.ok(
      targets.every((path) => path.startsWith("./") && !path.includes("..")),
      name + " uses another directory",
    );
    const linked = new Set(targets.map((path) => path.slice(2)));
    for (const relative of linked)
      assert.ok(
        existsSync(join(dir, relative)),
        name + " missing link: " + relative,
      );
    function walk(path) {
      return readdirSync(path, { withFileTypes: true }).flatMap((entry) =>
        entry.isDirectory()
          ? walk(join(path, entry.name))
          : [join(path, entry.name)],
      );
    }
    for (const file of walk(dir).filter(
      (path) => !path.endsWith("README.md"),
    )) {
      assert.ok(
        linked.has(file.slice(dir.length + 1)),
        name + " unlisted file: " + file,
      );
      assert.ok(
        !/\/(src|node_modules|_)\//.test(file) &&
          !file.endsWith(".test.ts") &&
          !file.endsWith("index.html"),
        file,
      );
    }
  }
});
