"""Dependency-direction checker: each architecture option passes its own layout and rejects each breach.

Uses the pinned Rojo/Lune from existing Rokit storage (never installs). No seed or network needed.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.native.roblox_helpers import CACHE, LEAF, roblox_env, tool_bin_dir

MODULES = {
    "src/shared/Net.luau": "return { ping = \"Ping\" }\n",
    "src/shared/Rules.luau": 'local Net = require("./Net")\n\nreturn { net = Net }\n',
    "src/server/main.server.luau": (
        "local Combat = require(script.Parent.services.Combat)\n"
        "local Data = require(script.Parent:WaitForChild(\"services\"):WaitForChild(\"Data\"))\n"
        "Combat.Start({ data = Data })\n"),
    "src/server/services/Combat.luau": (
        'local Rules = require("../../shared/Rules")\n'
        "local ReplicatedStorage = game:GetService(\"ReplicatedStorage\")\n"
        "local Promise = require(ReplicatedStorage.Packages.Promise)\n"
        "return { Start = function(_deps) end, rules = Rules, promise = Promise }\n"),
    "src/server/services/Data.luau": (
        "local Net = require(game:GetService(\"ReplicatedStorage\").Shared.Net)\n"
        "local DataStoreService = game:GetService(\"DataStoreService\")\n"
        "return { net = Net, store = DataStoreService }\n"),
    "src/client/main.client.luau": "local Input = require(script.Parent.controllers.Input)\nInput.Start({})\n",
    "src/client/controllers/Input.luau": (
        "-- require(script.Parent.Parent.Parent) in a comment is ignored\n"
        "local ReplicatedStorage = game:GetService(\"ReplicatedStorage\")\n"
        "local Rules = require(ReplicatedStorage:WaitForChild(\"Shared\").Rules)\n"
        "local text = \"require(script)\"\n"
        "return { Start = function(_deps) end, rules = Rules, text = text }\n"),
}

ECS = {
    "src/shared/components/Health.luau": (
        "local ReplicatedStorage = game:GetService(\"ReplicatedStorage\")\n"
        "local jecs = require(ReplicatedStorage.Packages.jecs)\n"
        "return { Health = jecs.component() }\n"),
    "src/shared/components/Regen.luau": 'local Health = require("./Health")\n\nreturn { Regen = Health }\n',
    "src/shared/world.luau": 'local Health = require("./components/Health")\n\nreturn { health = Health }\n',
    "src/server/main.server.luau": (
        "local regen = require(script.Parent.systems.regen)\n"
        "local damage = require(script.Parent.systems.damage)\n"
        "regen()\ndamage()\n"),
    "src/server/systems/regen.luau": (
        'local Health = require("../../shared/components/Health")\n'
        'local world = require("../../shared/world")\n'
        "return function() return Health, world end\n"),
    "src/server/systems/damage.luau": 'local Health = require("../../shared/components/Health")\n\n'
                                      "return function() return Health end\n",
    "src/client/main.client.luau": "local hud = require(script.Parent.systems.hud)\nhud()\n",
    "src/client/systems/hud.luau": (
        "local Health = require(game:GetService(\"ReplicatedStorage\").Shared.components.Health)\n"
        "return function() return Health end\n"),
}


def make_project(name: str, option: str, files: dict[str, str]) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"arch-{name}-", dir=CACHE)) / "project"
    shutil.copytree(LEAF, root)
    shutil.copy2(root / f"architecture/{option}.json", root / "architecture.json")
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return root


def run_architecture(root: Path) -> subprocess.CompletedProcess:
    env = roblox_env(root)
    bins = tool_bin_dir()
    sourcemap = subprocess.run([str(bins / "rojo"), "sourcemap", "default.project.json", "--output",
                                "sourcemap.json"], cwd=root, env=env, text=True, capture_output=True)
    if sourcemap.returncode:
        raise RuntimeError(sourcemap.stdout + sourcemap.stderr)
    return subprocess.run([str(bins / "lune"), "run", "scripts/check-architecture.luau", "architecture.json",
                           "sourcemap.json"], cwd=root, env=env, text=True, capture_output=True)


class ArchitectureCheckTests(unittest.TestCase):
    def assert_passes(self, result):
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("0 violations", output)

    def assert_fails(self, result, *needles):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        for needle in needles:
            self.assertIn(needle, output)

    # --- modules (default) -------------------------------------------------
    def test_modules_layout_passes(self):
        result = run_architecture(make_project("modules-ok", "modules", MODULES))
        self.assert_passes(result)
        self.assertIn("architecture: modules", result.stdout)

    def test_modules_shared_requires_server_by_string(self):
        files = dict(MODULES)
        files["src/shared/Rules.luau"] = 'local Combat = require("../server/services/Combat")\n\nreturn Combat\n'
        self.assert_fails(run_architecture(make_project("shared-string", "modules", files)),
                          "src/shared/Rules.luau:1", "shared must not require services")

    def test_modules_shared_requires_server_by_instance_path(self):
        files = dict(MODULES)
        files["src/shared/Rules.luau"] = (
            "local Combat = require(game:GetService(\"ServerScriptService\").Server.services.Combat)\n"
            "return Combat\n")
        self.assert_fails(run_architecture(make_project("shared-instance", "modules", files)),
                          "shared must not require services", "shared must not use ServerScriptService")

    def test_modules_shared_uses_server_only_service(self):
        files = dict(MODULES)
        files["src/shared/Net.luau"] = 'local store = game:GetService("DataStoreService")\n\nreturn store\n'
        self.assert_fails(run_architecture(make_project("shared-service", "modules", files)),
                          "src/shared/Net.luau:1", "shared must not use DataStoreService")

    def test_modules_client_requires_server(self):
        files = dict(MODULES)
        files["src/client/controllers/Input.luau"] = (
            'local Combat = require("../../server/services/Combat")\n\nreturn Combat\n')
        self.assert_fails(run_architecture(make_project("client-server", "modules", files)),
                          "controllers must not require services")

    def test_modules_service_cycle(self):
        files = dict(MODULES)
        files["src/server/services/Combat.luau"] = 'local Data = require("./Data")\n\nreturn Data\n'
        files["src/server/services/Data.luau"] = 'local Combat = require(script.Parent.Combat)\n\nreturn Combat\n'
        self.assert_fails(run_architecture(make_project("cycle", "modules", files)), "dependency cycle in services",
                          "src/server/services/Combat.luau -> src/server/services/Data.luau")

    def test_modules_shared_cycle_through_init_file(self):
        files = dict(MODULES)
        del files["src/shared/Net.luau"]
        files["src/shared/Net/init.luau"] = (
            '--[==[ require(game) in a long comment is ignored ]==]\n'
            'local Codec = require("@self/Codec")\nlocal Rules = require("./Rules")\n\nreturn { Codec, Rules }\n')
        files["src/shared/Net/Codec.luau"] = "local s = [[require(x)]]\nlocal t = `a{1}`\n\nreturn { s, t }\n"
        self.assert_fails(run_architecture(make_project("init-cycle", "modules", files)),
                          "dependency cycle in shared",
                          "src/shared/Net/init.luau -> src/shared/Rules.luau -> src/shared/Net/init.luau")

    def test_modules_dynamic_require_fails_closed(self):
        files = dict(MODULES)
        files["src/server/services/Combat.luau"] = (
            'local name = "Data"\nlocal Data = require(script.Parent[name])\n\nreturn Data\n')
        self.assert_fails(run_architecture(make_project("dynamic", "modules", files)), "dynamic require")

    def test_modules_require_as_value_fails_closed(self):
        files = dict(MODULES)
        files["src/server/services/Combat.luau"] = 'local load = require\n\nreturn load("./Data")\n'
        self.assert_fails(run_architecture(make_project("alias", "modules", files)), "require used as a value")

    def test_modules_unresolved_require(self):
        files = dict(MODULES)
        files["src/shared/Rules.luau"] = 'local Missing = require("./Missing")\n\nreturn Missing\n'
        self.assert_fails(run_architecture(make_project("unresolved", "modules", files)), "cannot resolve")

    def test_modules_second_boot_script(self):
        files = dict(MODULES)
        files["src/server/extra.server.luau"] = "print(1)\n"
        self.assert_fails(run_architecture(make_project("twoboot", "modules", files)), "at most 1 boot script")

    def test_modules_boot_script_in_shared(self):
        files = dict(MODULES)
        files["src/shared/boot.client.luau"] = "print(1)\n"
        self.assert_fails(run_architecture(make_project("sharedboot", "modules", files)),
                          "boot script outside")

    def test_modules_module_outside_services(self):
        files = dict(MODULES)
        files["src/server/Helpers.luau"] = "return {}\n"
        self.assert_fails(run_architecture(make_project("loose", "modules", files)),
                          "src/server/Helpers.luau", "ModuleScripts are not allowed in server")

    def test_unknown_rule_key_fails_closed(self):
        root = make_project("badrules", "modules", MODULES)
        rules = json.loads((root / "architecture.json").read_text())
        rules["layers"][0]["mayRequier"] = []
        (root / "architecture.json").write_text(json.dumps(rules))
        self.assert_fails(run_architecture(root), "unknown key")

    # --- ECS ---------------------------------------------------------------
    def test_ecs_layout_passes(self):
        result = run_architecture(make_project("ecs-ok", "ecs", ECS))
        self.assert_passes(result)
        self.assertIn("architecture: ecs", result.stdout)

    def test_ecs_system_requires_system(self):
        files = dict(ECS)
        files["src/server/systems/damage.luau"] = 'local regen = require("./regen")\n\nreturn regen\n'
        self.assert_fails(run_architecture(make_project("ecs-systems", "ecs", files)),
                          "server-systems must not require server-systems")

    def test_ecs_component_requires_shared_logic(self):
        files = dict(ECS)
        files["src/shared/components/Regen.luau"] = 'local world = require("../world")\n\nreturn world\n'
        self.assert_fails(run_architecture(make_project("ecs-component", "ecs", files)),
                          "components must not require shared")

    def test_ecs_shared_requires_server_system(self):
        files = dict(ECS)
        files["src/shared/world.luau"] = 'local regen = require("../server/systems/regen")\n\nreturn regen\n'
        self.assert_fails(run_architecture(make_project("ecs-shared", "ecs", files)),
                          "shared must not require server-systems")

    def test_ecs_client_requires_server_system(self):
        files = dict(ECS)
        files["src/client/systems/hud.luau"] = (
            "local regen = require(game:GetService(\"ServerScriptService\").Server.systems.regen)\nreturn regen\n")
        self.assert_fails(run_architecture(make_project("ecs-client", "ecs", files)),
                          "client-systems must not require server-systems")


class ArchitectureStageTests(unittest.TestCase):
    """check.sh wiring: the stage exists, runs the checker, and refuses a missing rule file."""

    def run_stage(self, root: Path) -> subprocess.CompletedProcess:
        (root / "roblox.yml").write_text("# placeholder: the architecture stage does not lint\n")
        return subprocess.run(["sh", "scripts/check.sh", "architecture"], cwd=root, env=roblox_env(root),
                              text=True, capture_output=True)

    def test_stage_passes_and_fails(self):
        ok = self.run_stage(make_project("stage-ok", "modules", MODULES))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("stage: architecture", ok.stdout)
        files = dict(MODULES)
        files["src/shared/Rules.luau"] = 'local Combat = require("../server/services/Combat")\n\nreturn Combat\n'
        bad = self.run_stage(make_project("stage-bad", "modules", files))
        self.assertNotEqual(bad.returncode, 0, bad.stdout + bad.stderr)
        self.assertIn("shared must not require services", bad.stdout + bad.stderr)

    def test_stage_requires_rule_file(self):
        root = make_project("stage-missing", "modules", MODULES)
        (root / "architecture.json").unlink()
        result = self.run_stage(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing architecture.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
