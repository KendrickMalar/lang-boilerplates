"""Catch missing/non-self-contained Godot settings and weakened quality rules."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "godot/mobile-game"
INSTALLERS = ["brew install", "pip install", "uv tool install", "pipx install", "npm install"]


class StaticGodotTests(unittest.TestCase):
    def test_tool_versions_are_pinned_and_never_installed(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("GODOT_VERSION=4.7.2", text)
        self.assertIn("GDTOOLKIT_VERSION=4.5.0", text)
        for line in text.splitlines():
            for command in INSTALLERS:
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_project_settings(self):
        lines = (LEAF / "project.godot").read_text().splitlines()
        for expected in ["config_version=5",
                         'config/features=PackedStringArray("4.7", "Mobile")',
                         "gdscript/warnings/untyped_declaration=2",
                         'renderer/rendering_method="mobile"',
                         "textures/vram_compression/import_etc2_astc=true"]:
            self.assertIn(expected, lines)

    def test_check_judges_godot_output_not_only_exit_code(self):
        text = (LEAF / "scripts/check.sh").read_text()
        for marker in ["SCRIPT ERROR", "Parse Error", "Failed to load script", "--check-only",
                       "--import", "scripts/test_runner.gd"]:
            self.assertIn(marker, text)

    def test_runner_rejects_coroutine_tests(self):
        runner = (LEAF / "scripts/test_runner.gd").read_text()
        self.assertIn("GDScriptFunctionState", runner)
        self.assertIn("await", (LEAF / "README.md").read_text())

    def test_readme_says_verdict_comes_from_check_sh(self):
        text = (LEAF / "README.md").read_text()
        self.assertIn("check.sh 経由", text)
        self.assertIn("godot --headless --path . --script scripts/test_runner.gd", text)

    def test_gdtoolkit_configs_pin_full_defaults(self):
        lint = (LEAF / "gdlintrc").read_text()
        for entry in ["max-line-length: 100", "tab-characters: 1", "  .godot: null",
                      "  build: null", "function-arguments-number: 10"]:
            self.assertIn(entry, lint)
        fmt = (LEAF / "gdformatrc").read_text()
        for entry in ["line_length: 100", "use_spaces: null", "  .godot: null"]:
            self.assertIn(entry, fmt)

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/.godot/", "/build/", "/.verification/", ".DS_Store"]:
            self.assertIn(entry, ignored)
        self.assertNotIn("export_presets.cfg", ignored)
        scripts = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.gd"))
        self.assertEqual(scripts, ["scripts/test_context.gd", "scripts/test_runner.gd"])
        for empty in ["src", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])
        self.assertFalse((LEAF / ".godot").exists())

    def test_hooks_use_repository_root_gate(self):
        for hook in ["pre-commit", "pre-push"]:
            text = (LEAF / ".husky" / hook).read_text()
            self.assertIn("node check-commit.mjs", text)
        self.assertIn("scripts/check.sh all", (LEAF / "package.json").read_text())

    def test_readme_links_resolve(self):
        text = (LEAF / "README.md").read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((LEAF / link).exists(), link)
        for phrase in ["gdlint", "untyped_declaration", "TestContext", "SCRIPT ERROR",
                       "blender/assets", "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
