"""Catch missing/non-self-contained Rojo settings and weakened quality rules."""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "roblox/rojo"
PINS = {"rojo": "rojo-rbx/rojo@7.7.1", "wally": "UpliftGames/wally@0.3.2",
        "selene": "Kampfkarren/selene@0.32.0", "stylua": "JohnnyMorganz/StyLua@2.5.2",
        "luau-lsp": "JohnnyMorganz/luau-lsp@1.69.0", "lune": "lune-org/lune@0.10.5"}
DEFS_SHA = "7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2"


class StaticRobloxTests(unittest.TestCase):
    def test_tool_pins_are_exact(self):
        tools = tomllib.loads((LEAF / "rokit.toml").read_text())["tools"]
        self.assertEqual(tools, PINS)

    def test_quality_settings(self):
        selene = tomllib.loads((LEAF / "selene.toml").read_text())
        self.assertEqual(selene, {"std": "roblox", "roblox-std-source": "pinned"})
        stylua = tomllib.loads((LEAF / "stylua.toml").read_text())
        self.assertEqual(stylua["syntax"], "Luau")
        self.assertEqual(stylua["column_width"], 120)
        self.assertEqual(stylua["indent_type"], "Tabs")
        self.assertEqual(stylua["quote_style"], "AutoPreferDouble")
        self.assertEqual(stylua["call_parentheses"], "Always")
        self.assertEqual(json.loads((LEAF / ".luaurc").read_text()), {"languageMode": "strict", "lintErrors": True})

    def test_rojo_tree_mapping(self):
        tree = json.loads((LEAF / "default.project.json").read_text())["tree"]
        self.assertEqual(tree["$className"], "DataModel")
        self.assertEqual(tree["ServerScriptService"]["Server"]["$path"], "src/server")
        self.assertEqual(tree["StarterPlayer"]["StarterPlayerScripts"]["Client"]["$path"], "src/client")
        shared = tree["ReplicatedStorage"]
        self.assertEqual(shared["Shared"]["$path"], "src/shared")
        self.assertEqual(shared["Packages"]["$path"], {"optional": "Packages"})

    def test_wally_manifest_has_no_dependencies(self):
        wally = tomllib.loads((LEAF / "wally.toml").read_text())
        self.assertEqual(wally["package"]["realm"], "shared")
        self.assertEqual(wally["package"]["registry"], "https://github.com/UpliftGames/wally-index")
        self.assertEqual(wally.get("dependencies", {}), {})

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/Packages/", "/sourcemap.json", "*.rbxl", "*.rbxlx", "/.luau-lsp-cache/"]:
            self.assertIn(entry, ignored)
        self.assertNotIn("wally.lock", ignored)
        self.assertNotIn("roblox.yml", ignored)
        luau = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.luau"))
        self.assertEqual(luau, ["scripts/test.luau"], "only the test runner is distributed")
        for name in ["roblox.yml", "wally.lock", "sourcemap.json"]:
            self.assertFalse((LEAF / name).exists(), name)
        for empty in ["src/server", "src/client", "src/shared", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])

    def test_check_script_pins_type_definitions(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("luau-lsp/1.69.0/scripts/globalTypes.d.luau", text)
        self.assertIn(DEFS_SHA, text)
        self.assertIn(".luau-lsp-cache/globalTypes-1.69.0.d.luau", text)
        for command in ["rokit install", "wally install", "selene generate-roblox-std"]:
            for line in text.splitlines():
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_readme_links_resolve(self):
        text = (LEAF / "README.md").read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((LEAF / link).exists(), link)
        for phrase in ["selene generate-roblox-std", "wally install", "rokit install",
                       'require("./', "Rosetta", "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
