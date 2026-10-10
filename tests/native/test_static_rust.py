"""Catch missing/non-self-contained configuration and weakened quality rules."""
import json
import re
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "rust/tauri"
CACHE = ROOT / ".verification/native/rust"


class StaticRustTests(unittest.TestCase):
    def test_independent_leaf_contract(self):
        required = ["README.md", "LICENSE", "rust-toolchain.toml", "rustfmt.toml",
                    ".editorconfig", ".gitignore", ".cargo/config.toml",
                    "src-tauri/Cargo.toml", "scripts/check.sh", "scripts/check.ps1"]
        for name in required:
            with self.subTest(name=name):
                self.assertTrue((LEAF / name).is_file(), f"missing setting: {name}")
        if not all((LEAF / name).is_file() for name in required):
            return
        CACHE.mkdir(parents=True, exist_ok=True)
        dest = Path(tempfile.mkdtemp(prefix="static-", dir=CACHE)) / "project"
        shutil.copytree(LEAF, dest)
        manifest = tomllib.loads((dest / "src-tauri/Cargo.toml").read_text())
        self.assertEqual(manifest["package"]["edition"], "2024")
        self.assertEqual(manifest["package"]["rust-version"], "1.92")
        self.assertNotIn("workspace", manifest)
        self.assertEqual(manifest["dependencies"]["tauri"]["version"], "=2.12.2")
        self.assertEqual(manifest["build-dependencies"]["tauri-build"]["version"], "=2.7.1")
        for lint in ["unsafe_code", "unused_must_use"]:
            self.assertEqual(manifest["lints"]["rust"][lint], "deny")
        clippy = manifest["lints"]["clippy"]
        self.assertEqual(clippy["all"], {"level": "warn", "priority": -1})
        for lint in ["unwrap_used", "expect_used", "todo", "dbg_macro"]:
            self.assertEqual(clippy[lint], "deny")
        toolchain = tomllib.loads((dest / "rust-toolchain.toml").read_text())["toolchain"]
        self.assertEqual(toolchain["channel"], "1.92.0")
        self.assertEqual(set(toolchain["components"]), {"rustfmt", "clippy"})
        fmt = tomllib.loads((dest / "rustfmt.toml").read_text())
        self.assertEqual(fmt["edition"], "2024")
        self.assertEqual(fmt["max_width"], 100)
        self.assertEqual(fmt["tab_spaces"], 4)
        self.assertEqual(fmt["newline_style"], "Unix")
        tomllib.loads((dest / ".cargo/config.toml").read_text())
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (dest / "README.md").read_text()):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((dest / link).exists(), link)
        self.assertEqual([p.relative_to(dest).as_posix() for p in dest.rglob("*.rs")],
                         ["src-tauri/build.rs"], "only build helper is distributed")
        self.assertFalse((dest / "Cargo.lock").exists())

    def test_capability_is_explicit_local_main_only(self):
        paths = [LEAF / "src-tauri/tauri.conf.json", LEAF / "src-tauri/capabilities/main.json",
                 LEAF / "src-tauri/build.rs"]
        self.assertTrue(all(path.is_file() for path in paths), "Tauri boundary settings missing")
        if not all(path.is_file() for path in paths):
            return
        config, capability = [json.loads(path.read_text()) for path in paths[:2]]
        self.assertEqual(config["app"]["security"]["capabilities"], ["main"])
        self.assertEqual([window["label"] for window in config["app"]["windows"]], ["main"])
        self.assertEqual(capability["identifier"], "main")
        self.assertEqual(capability["windows"], ["main"])
        self.assertEqual(set(capability["platforms"]), {"macOS", "windows", "linux"})
        self.assertTrue(capability["local"])
        self.assertNotIn("remote", capability)
        self.assertEqual(capability["permissions"], ["core:window:allow-title"])
        self.assertNotIn("beforeBuildCommand", config["build"])
        self.assertNotIn("beforeDevCommand", config["build"])


if __name__ == "__main__":
    unittest.main()
