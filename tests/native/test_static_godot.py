"""Catch missing/non-self-contained Godot settings and weakened quality rules."""
import re
import shutil
import subprocess
import sys
import tempfile
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


CHECKER = LEAF / "scripts/check_architecture.py"
PROJECT = """config_version=5

[autoload]

Events="*res://src/autoload/events.gd"
"""
SCENE_CORE = {
    "project.godot": PROJECT,
    "src/core/score.gd": (
        "class_name Score\nextends RefCounted\n"
        "# preload(\"res://src/game/player.gd\") and Events in a comment are ignored\n"
        "const LABEL := \"Events get_tree()\"\n\n\n"
        "static func add(a: int, b: int) -> int:\n\treturn a + b\n"),
    "src/core/rules.gd": (
        "extends \"res://src/core/score.gd\"\n"
        "const Helper = preload(\"res://src/core/score.gd\")\n\n\n"
        "func total() -> int:\n\treturn Score.add(1, 2)\n"),
    "src/game/player.gd": (
        "class_name Player\nextends Node2D\nsignal died\n\n\n"
        "func _ready() -> void:\n\tEvents.started.emit()\n\tprint(Score.add(1, 1))\n"
        "\tget_tree().paused = false\n"),
    "src/game/player.tscn": (
        "[gd_scene load_steps=2 format=3]\n\n"
        "[ext_resource type=\"Script\" path=\"res://src/game/player.gd\" id=\"1\"]\n"),
    "src/ui/hud.gd": (
        "extends Control\nconst PlayerScene = preload(\"res://src/game/player.tscn\")\n"
        "var player: Player\n\n\nfunc _ready() -> void:\n\tEvents.started.connect(_on_started)\n\n\n"
        "func _on_started() -> void:\n\tpass\n"),
    "src/autoload/events.gd": (
        "extends Node\nsignal started\nconst Points = preload(\"res://src/core/score.gd\")\n"),
    "tests/test_score.gd": "extends RefCounted\nconst P = preload(\"res://src/game/player.gd\")\n",
}
FEATURES = {
    "project.godot": PROJECT,
    "src/shared/item.gd": "class_name Item\nextends Resource\n",
    "src/autoload/events.gd": "extends Node\nsignal bought(item: Item)\n",
    "src/features/inventory/inventory.gd": (
        "class_name Inventory\nextends Node\nvar items: Array[Item] = []\n\n\n"
        "func _ready() -> void:\n\tEvents.bought.connect(items.append)\n"),
    "src/features/inventory/inventory.tscn": (
        "[ext_resource type=\"Script\" path=\"res://src/features/inventory/inventory.gd\" id=\"1\"]\n"),
    "src/features/shop/shop.gd": (
        "extends Node\nconst Shared = preload(\"res://src/shared/item.gd\")\n\n\n"
        "func buy(item: Item) -> void:\n\tEvents.bought.emit(item)\n"),
}


class GodotArchitectureTests(unittest.TestCase):
    def run_checker(self, files, rules, extra=None):
        cache = ROOT / ".verification/native/godot-architecture"
        cache.mkdir(parents=True, exist_ok=True)
        project = Path(tempfile.mkdtemp(prefix="arch-", dir=cache))
        merged = dict(files)
        merged.update(extra or {})
        for relative, text in merged.items():
            if text is None:
                continue
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--root", str(project),
             str(LEAF / "architecture" / rules)], text=True, capture_output=True)
        shutil.rmtree(project)
        return result.returncode, result.stdout + result.stderr

    def assert_violation(self, files, rules, extra, *needles):
        code, output = self.run_checker(files, rules, extra)
        self.assertEqual(code, 1, output)
        for needle in needles:
            self.assertIn(needle, output)

    def test_scene_core_compliant_project_passes(self):
        code, output = self.run_checker(SCENE_CORE, "scene-core.json")
        self.assertEqual(code, 0, output)
        self.assertIn("0 violations", output)

    def test_scene_core_rejects_core_extending_node(self):
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": "extends Node\n"},
                              "src/core/bad.gd:1", "extends Node")
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": "extends RefCounted\n\n\nclass Inner extends Sprite2D:\n\tpass\n"},
                              "src/core/bad.gd:4", "extends Sprite2D")

    def test_scene_core_rejects_core_loading_game_or_ui(self):
        for line in ['const P = preload("res://src/game/player.gd")',
                     "var s: Resource = load('res://src/ui/hud.gd')",
                     'var r: Resource = ResourceLoader.load("res://src/game/player.tscn")',
                     'extends "res://src/game/player.gd"']:
            with self.subTest(line=line):
                self.assert_violation(SCENE_CORE, "scene-core.json",
                                      {"src/core/bad.gd": line + "\n"},
                                      "src/core/bad.gd:1", "core -> ")

    def test_scene_core_rejects_core_referencing_autoload(self):
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": "extends RefCounted\n\n\nfunc f() -> void:\n\tEvents.started.emit()\n"},
                              "src/core/bad.gd:5", "Events", "core -> autoload")
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": 'var n: String = "/root/Events"\n'},
                              "src/core/bad.gd:1", "core -> autoload")

    def test_scene_core_rejects_class_name_reference_across_layers(self):
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": "extends RefCounted\nvar p: Player\n"},
                              "src/core/bad.gd:2", "Player", "core -> game")
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/core/bad.gd": "extends Player\n"},
                              "src/core/bad.gd:1", "core -> game")
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/game/bad.gd": "class_name Bad\nextends Node\nvar h: Hud\n",
                               "src/ui/hud.gd": "class_name Hud\nextends Control\n"},
                              "src/game/bad.gd:3", "game -> ui")

    def test_scene_core_rejects_scene_tree_calls_in_core(self):
        for line in ["\tget_tree().quit()", "\tvar t: SceneTree = Engine.get_main_loop()",
                     "\tget_node(\"A\").hide()"]:
            with self.subTest(line=line):
                self.assert_violation(SCENE_CORE, "scene-core.json",
                                      {"src/core/bad.gd": "extends RefCounted\n\n\nfunc f() -> void:\n" + line + "\n"},
                                      "src/core/bad.gd:5")

    def test_scene_core_rejects_misplaced_autoload_and_unlayered_files(self):
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"project.godot": PROJECT + 'Bus="*res://src/game/bus.gd"\n',
                               "src/game/bus.gd": "extends Node\n"},
                              "project.godot", "Bus", "src/autoload")
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/main.gd": "extends Node\n"}, "src/main.gd", "layer")

    def test_scene_core_checks_scene_files(self):
        self.assert_violation(SCENE_CORE, "scene-core.json",
                              {"src/game/hud_holder.tscn":
                               '[ext_resource type="PackedScene" path="res://src/ui/hud.tscn" id="1"]\n'},
                              "src/game/hud_holder.tscn:1", "game -> ui")

    def test_features_compliant_project_passes(self):
        code, output = self.run_checker(FEATURES, "features.json")
        self.assertEqual(code, 0, output)
        self.assertIn("0 violations", output)

    def test_features_reject_cross_feature_references(self):
        for name, text in [
                ("src/features/shop/bad.gd", 'extends Node\nvar s: Resource = load("res://src/features/inventory/inventory.gd")\n'),
                ("src/features/shop/bad.gd", "extends Node\nvar i: Inventory\n"),
                ("src/features/shop/bad.tscn",
                 '[ext_resource type="Script" path="res://src/features/inventory/inventory.gd" id="1"]\n')]:
            with self.subTest(text=text):
                self.assert_violation(FEATURES, "features.json", {name: text}, name,
                                      "features/shop -> features/inventory")

    def test_features_shared_must_not_depend_on_features(self):
        self.assert_violation(FEATURES, "features.json",
                              {"src/shared/bad.gd": "extends RefCounted\nvar i: Inventory\n"},
                              "src/shared/bad.gd:2", "shared -> features/inventory")

    def test_missing_or_invalid_rules_fail_closed(self):
        result = subprocess.run([sys.executable, str(CHECKER), "--root", str(LEAF),
                                 str(LEAF / "architecture/missing.json")],
                                text=True, capture_output=True)
        self.assertNotIn(result.returncode, (0, 1), result.stdout + result.stderr)
        self.assertIn("missing.json", result.stderr)

    def test_check_sh_runs_architecture_stage_in_all(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("format|lint|architecture|typecheck|test|all", text)
        self.assertIn("for step in format lint architecture typecheck test", text)
        self.assertIn("python3 scripts/check_architecture.py architecture.json", text)

    def test_readme_architecture_section(self):
        text = (LEAF / "README.md").read_text()
        section = text.split("## アーキテクチャ", 1)[1].split("\n## ", 1)[0]
        for phrase in ["### 選び方", "### シーンの組み合わせ＋純粋な core（既定）", "### 機能ごとのフォルダ",
                       "```mermaid", "MUST NOT", "architecture/scene-core.json",
                       "architecture/features.json", "scripts/check_architecture.py", "検出しない"]:
            self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main()
