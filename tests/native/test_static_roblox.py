"""Catch missing/non-self-contained Rojo settings and weakened quality rules."""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "roblox/roblox-game"
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
        expected = ["scripts/check-architecture.luau", "scripts/check-git.luau", "scripts/git-state.luau", "scripts/setup-similarity.luau",
                    "scripts/similarity.luau", "scripts/test-helpers.luau", "scripts/test.luau",
                    "scripts/verify-similarity.luau"]
        self.assertEqual(luau, expected, "only quality helpers, never product/game source or fixtures")
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

    def test_architecture_rules_fix_dependency_direction(self):
        server_only = ["ServerScriptService", "ServerStorage", "DataStoreService", "MemoryStoreService",
                       "MessagingService"]
        boots = [{"path": "src/server", "kind": "server", "max": 1},
                 {"path": "src/client", "kind": "client", "max": 1}]
        expected = {
            "modules": {
                "shared": ("src/shared", ["shared", "packages"], True, True, server_only),
                "services": ("src/server/services", ["shared", "services", "packages"], True, True, []),
                "server": ("src/server", ["shared", "services", "packages"], False, False, []),
                "controllers": ("src/client/controllers", ["shared", "controllers", "packages"], True, True,
                                server_only),
                "client": ("src/client", ["shared", "controllers", "packages"], False, False, server_only),
            },
            "ecs": {
                "components": ("src/shared/components", ["components", "packages"], True, True, server_only),
                "shared": ("src/shared", ["shared", "components", "packages"], True, True, server_only),
                "server-systems": ("src/server/systems", ["shared", "components", "packages"], False, True, []),
                "server": ("src/server", ["shared", "components", "server-systems", "packages"], False, False, []),
                "client-systems": ("src/client/systems", ["shared", "components", "packages"], False, True,
                                   server_only),
                "client": ("src/client", ["shared", "components", "client-systems", "packages"], False, False,
                           server_only),
            },
        }
        for option, layers in expected.items():
            with self.subTest(option=option):
                rules = json.loads((LEAF / f"architecture/{option}.json").read_text())
                self.assertEqual(rules["schema"], 1)
                self.assertEqual(rules["architecture"], option)
                self.assertEqual(rules["sourceRoot"], "src")
                self.assertEqual(rules["packages"], {"path": "Packages", "instance": ["ReplicatedStorage", "Packages"]})
                self.assertEqual(rules["bootScripts"], boots)
                actual = {layer["name"]: (layer["path"], layer["mayRequire"], layer.get("acyclic", False),
                                          layer.get("modules", True), layer.get("forbiddenServices", []))
                          for layer in rules["layers"]}
                self.assertEqual(actual, layers)
                for layer in rules["layers"]:
                    # Nothing below the server/client side may be reached from shared code.
                    if layer["path"].startswith("src/shared"):
                        self.assertFalse({"server", "services", "client", "controllers", "server-systems",
                                          "client-systems"} & set(layer["mayRequire"]))
                    if layer["path"].startswith("src/client"):
                        self.assertFalse({"server", "services", "server-systems"} & set(layer["mayRequire"]))

    def test_check_runs_architecture_stage(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("for step in format lint architecture typecheck test build similarity; do", text)
        self.assertIn("[ -s architecture.json ] || fail 'missing architecture.json", text)
        self.assertIn("lune run scripts/check-architecture.luau architecture.json sourcemap.json", text)
        checker = (LEAF / "scripts/check-architecture.luau").read_text()
        self.assertTrue(checker.startswith("--!strict"))
        for phrase in ["dynamic require cannot be checked", "require used as a value", "dependency cycle in",
                       "unknown key", "boot script outside"]:
            self.assertIn(phrase, checker)

    def test_architecture_readme_section(self):
        text = (LEAF / "README.md").read_text()
        section = text.split("## アーキテクチャ\n", 1)[1].split("\n## ", 1)[0]
        heads = re.findall(r"^### (.+)$", section, re.M)
        self.assertEqual(heads, ["選び方", "素の ModuleScript＋共有の純粋ロジック（既定）", "ECS（jecs または Matter）"])
        for option in section.split("\n### ")[2:]:
            self.assertIn("```mermaid\nflowchart", option)
            self.assertIn("| 規則", option)
            self.assertIn("MUST NOT", option)
            self.assertIn("向く", option)
            self.assertIn("向かない", option)
            self.assertIn("強制設定", option)
            self.assertIn("ReplicatedStorage", option)
        for phrase in ["scaffold", "Knit", "2024-07", "jecs", "v0.11.0", "v0.8.5", "matter-ecs/matter",
                       "architecture/modules.json", "architecture/ecs.json", "scripts/check-architecture.luau",
                       "Start(deps)"]:
            self.assertIn(phrase, section)
        spec = text.split("## アーキテクチャ検査の仕様（両選択肢共通）\n", 1)[1].split("\n## ", 1)[0]
        for phrase in ["restricted_module_paths", "rojo sourcemap", "動的な require は安全側で違反",
                       "dynamic require cannot be checked", "require used as a value", "スコープを見ず"]:
            self.assertIn(phrase, spec)

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
