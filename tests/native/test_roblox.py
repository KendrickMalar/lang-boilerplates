"""Real Rokit-pinned tools against isolated fixtures: normal passes, each defect fails."""
import unittest
from unittest.mock import patch

from tests.native import roblox_helpers
from tests.native.roblox_helpers import copy_fixture, roblox_env, run_check


class RobloxCheckTests(unittest.TestCase):
    def assert_fails(self, result, *needles):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        for needle in needles:
            self.assertIn(needle, output)

    def test_normal_all_passes_without_packages(self):
        root = copy_fixture("normal")
        # Roblox globals/API types must resolve in lint and strict typecheck.
        (root / "src/server/Main.server.luau").write_text(
            '--!strict\nlocal Players = game:GetService("Players")\n\nprint(Players.MaxPlayers + 1)\n')
        result = run_check(root, "all")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        for stage in ["format", "lint", "typecheck", "test", "build"]:
            self.assertIn(f"stage: {stage}", output)
        self.assertIn("1 passed, 0 failed", output)
        self.assertFalse((root / "Packages").exists())
        self.assertEqual(list(root.rglob("*.rbxl")), [], "build output must be temporary")

    def test_bad_format(self):
        root = copy_fixture("format")
        (root / "src/shared/Greeting.luau").write_text("local Greeting={}\nreturn Greeting\n")
        self.assert_fails(run_check(root, "format"), "Diff in")

    def test_lint_warning(self):
        root = copy_fixture("lint")
        (root / "src/shared/Unused.luau").write_text("local unused = 1\n\nreturn {}\n")
        self.assert_fails(run_check(root, "lint"), "unused_variable")

    def test_strict_type_error(self):
        root = copy_fixture("types")
        (root / "src/shared/Bad.luau").write_text('--!strict\nlocal n: number = "x"\n\nreturn n\n')
        self.assert_fails(run_check(root, "typecheck"), "Bad.luau", "TypeError")

    def test_failing_spec(self):
        root = copy_fixture("failing")
        spec = root / "tests/Greeting.spec.luau"
        spec.write_text(spec.read_text().replace('"Hello, Roblox!"', '"Bye"'))
        self.assert_fails(run_check(root, "test"), "FAIL", "0 passed, 1 failed")

    def test_spec_not_returning_table(self):
        root = copy_fixture("notable")
        (root / "tests/Broken.spec.luau").write_text("return 1\n")
        self.assert_fails(run_check(root, "test"), "Broken.spec.luau")

    def test_zero_specs(self):
        root = copy_fixture("zero")
        (root / "tests/Greeting.spec.luau").unlink()
        self.assert_fails(run_check(root, "test"), "no tests discovered")

    def test_missing_rojo_path(self):
        root = copy_fixture("path")
        project = root / "default.project.json"
        project.write_text(project.read_text().replace('"src/server"', '"src/missing"'))
        self.assert_fails(run_check(root, "build"), "src/missing")

    def test_missing_tool(self):
        root = copy_fixture("notool")
        env = roblox_env(root)
        env["PATH"] = "/usr/bin:/bin"
        self.assert_fails(run_check(root, "format", env), "rokit install")

    def test_wrong_tool_version(self):
        root = copy_fixture("version")
        pins = root / "rokit.toml"
        pins.write_text(pins.read_text().replace("StyLua@2.5.2", "StyLua@2.5.1"))
        self.assert_fails(run_check(root, "format"), "stylua must be 2.5.1")

    def test_definition_sha_mismatch(self):
        root = copy_fixture("sha")
        (root / ".luau-lsp-cache/globalTypes-1.69.0.d.luau").write_text("-- tampered\n")
        self.assert_fails(run_check(root, "typecheck"), "SHA256 mismatch")

    def test_dependencies_without_packages(self):
        root = copy_fixture("packages")
        wally = root / "wally.toml"
        wally.write_text(wally.read_text() + 'Promise = "evaera/promise@4.0.0"\n')
        self.assert_fails(run_check(root, "format"), "wally install")

    def test_missing_roblox_std(self):
        root = copy_fixture("std")
        (root / "roblox.yml").unlink()
        self.assert_fails(run_check(root, "lint"), "selene generate-roblox-std")

    def test_empty_source(self):
        root = copy_fixture("empty")
        (root / "src/shared/Greeting.luau").unlink()
        self.assert_fails(run_check(root, "format"), "no Luau source")

    def test_server_or_dev_dependencies_are_rejected(self):
        root = copy_fixture("devdeps")
        wally = root / "wally.toml"
        wally.write_text(wally.read_text() + '\n[dev-dependencies]\nTestEZ = "roblox/testez@0.4.1"\n')
        self.assert_fails(run_check(root, "format"), "only [dependencies]")

    def test_commented_wally_dependency_still_requires_packages(self):
        root = copy_fixture("wallycomment")
        wally = root / "wally.toml"
        wally.write_text(wally.read_text().replace("[dependencies]", "[dependencies] # deps")
                         + '  Promise = "evaera/promise@4.0.0"\n')
        self.assert_fails(run_check(root, "format"), "wally install")

    def test_unparsed_rokit_pin_fails_closed(self):
        root = copy_fixture("rokitcomment")
        pins = root / "rokit.toml"
        pins.write_text(pins.read_text().replace('StyLua@2.5.2"', 'StyLua@2.5.2" # formatter'))
        self.assert_fails(run_check(root, "format"), "cannot parse rokit.toml")

    def test_missing_seed_explains_prerequisite(self):
        with patch.object(roblox_helpers, "SEED", roblox_helpers.CACHE / "no-such-seed"):
            with self.assertRaisesRegex(RuntimeError, "seed"):
                copy_fixture("noseed")

    def test_unknown_stage(self):
        root = copy_fixture("stage")
        self.assert_fails(run_check(root, "fmt"), "unknown stage")


if __name__ == "__main__":
    unittest.main()
