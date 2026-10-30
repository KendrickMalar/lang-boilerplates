import unittest
from pathlib import Path

from tests.native.rust_game_helpers import CACHE, game_env, run_game

TOOLCHAIN = "1.99.1"
TOOLS = {
    "nextest": "0.9.150",
    "deny": "0.20.2",
    "shear": "1.14.0",
    "llvm-cov": "0.9.1",
}
PROBE = CACHE / "fixtures" / "env-probe"


class RustGameEnvironmentTest(unittest.TestCase):
    def test_env_is_isolated(self):
        PROBE.mkdir(parents=True, exist_ok=True)
        env = game_env(PROBE)
        for key in ("HOME", "RUSTUP_HOME", "CARGO_HOME", "CARGO_TARGET_DIR"):
            path = Path(env[key]).resolve()
            self.assertTrue(path.is_relative_to(CACHE.resolve()), f"{key}={path}")
            self.assertNotIn(str(Path.home() / ".rustup"), env[key])
            self.assertNotIn(str(Path.home() / ".cargo"), env[key])
        self.assertEqual(env["CARGO_TARGET_DIR"], str(CACHE / "targets" / "env-probe"))
        self.assertTrue(env["PATH"].startswith(str(CACHE / "tools/bin") + ":"))
        self.assertEqual(env["RUSTUP_AUTO_INSTALL"], "0")
        self.assertEqual(env["CARGO_NET_OFFLINE"], "true")

    def test_toolchain_and_tools_present(self):
        PROBE.mkdir(parents=True, exist_ok=True)
        result = run_game(["rustup", "run", TOOLCHAIN, "rustc", "--version"], PROBE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith(f"rustc {TOOLCHAIN} "), result.stdout)
        for tool, version in TOOLS.items():
            result = run_game(["rustup", "run", TOOLCHAIN, "cargo", tool, "--version"], PROBE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(version, result.stdout)


if __name__ == "__main__":
    unittest.main()
