import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { ROOT } from "./helpers.mjs";
test("language README links resolve to the complete settings distribution", () => {
  const doc = join(ROOT, "typescript/README.md");
  assert.ok(existsSync(doc), "missing Scaffold TypeScript README");
  const text = readFileSync(doc, "utf8");
  const linked = new Set(
    [...text.matchAll(/\]\(\.\/([^\s)#]+)\)/g)].map((match) => match[1]),
  );
  for (const relative of linked)
    assert.ok(
      existsSync(join(dirname(doc), relative)),
      "missing link: " + relative,
    );
  function walk(dir) {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
      entry.isDirectory()
        ? walk(join(dir, entry.name))
        : [join(dir, entry.name)],
    );
  }
  const distributed = walk(join(ROOT, "typescript")).filter(
    (path) => !path.endsWith("README.md"),
  );
  for (const path of distributed)
    assert.ok(
      linked.has(path.slice(join(ROOT, "typescript").length + 1)),
      "unlisted copy file: " + path,
    );
  assert.ok(
    !distributed.some(
      (path) =>
        /\/(src|node_modules|_)\//.test(path) ||
        path.endsWith(".test.ts") ||
        path.endsWith("index.html"),
    ),
  );
});
