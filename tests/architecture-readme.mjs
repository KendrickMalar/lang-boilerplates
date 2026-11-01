// Finds the "## アーキテクチャ" section of a leaf README, or one choice inside it.
export function architectureSection(readme, heading) {
  const start = readme.indexOf("\n## アーキテクチャ\n");
  if (start < 0) throw new Error("missing ## アーキテクチャ");
  const end = readme.indexOf("\n## ", start + 1);
  const section = readme.slice(start, end < 0 ? undefined : end);
  if (heading === undefined) return section;
  const marker = "\n### " + heading + "\n";
  const from = section.indexOf(marker);
  if (from < 0) throw new Error("missing ### " + heading);
  const to = section.indexOf("\n### ", from + 1);
  return section.slice(from, to < 0 ? undefined : to);
}
