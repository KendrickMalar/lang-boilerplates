"""Catch missing/non-self-contained Blender asset settings and weakened checks."""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "blender/assets"
INSTALLERS = ["brew install", "pip install", "uv tool install", "pipx install", "npm install"]


class StaticBlenderTests(unittest.TestCase):
    def test_tool_versions_are_pinned_and_never_installed(self):
        text = (LEAF / "scripts/check.sh").read_text()
        for pin in ["BLENDER_VERSION=5.2.2", "RUFF_VERSION=0.17.0", "GLTF_TRANSFORM_VERSION=4.5.1"]:
            self.assertIn(pin, text)
        for line in text.splitlines():
            for command in INSTALLERS:
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_blender_failures_reach_the_exit_code(self):
        check = (LEAF / "scripts/check.sh").read_text()
        for marker in ["--python-exit-code 1", "--factory-startup", "gltf-transform validate"]:
            self.assertIn(marker, check)
        for script in ["build.py", "test.py"]:
            self.assertIn("sys.exit(main())", (LEAF / "scripts" / script).read_text())

    def test_ruff_settings_match_blender_python(self):
        config = tomllib.loads((LEAF / "pyproject.toml").read_text())
        self.assertEqual(set(config), {"tool"})
        ruff = config["tool"]["ruff"]
        self.assertEqual(ruff["target-version"], "py313")
        self.assertEqual(ruff["line-length"], 100)
        self.assertEqual(ruff["lint"]["select"], ["E", "F", "W", "I", "B", "UP"])

    def test_triangle_budget_default(self):
        text = (LEAF / "scripts/build.py").read_text()
        self.assertIn("DEFAULT_MAX_TRIANGLES = 3000", text)
        self.assertIn("MAX_TRIANGLES", text)

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/build/", "__pycache__/", "/.verification/", ".DS_Store", "*.blend1"]:
            self.assertIn(entry, ignored)
        python = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.py"))
        self.assertEqual(python, ["scripts/build.py", "scripts/test.py"])
        for empty in ["models", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])
        self.assertEqual(list(LEAF.rglob("*.glb")), [])

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
        for phrase in ["MAX_TRIANGLES", "build()", "--python-exit-code", "godot/mobile", "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
