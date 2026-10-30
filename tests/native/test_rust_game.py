"""Real-tool gates for the Rust game-server leaves (isolated toolchain, offline)."""
import os
import subprocess
import unittest
from pathlib import Path

from tests.native.rust_game_helpers import (CACHE, copy_leaf, game_env, run_game,
                                            write_fake_crate)

CLEAN = '''//! Core game rules.

/// Adds two scores without overflowing.
#[must_use]
pub const fn add(left: u32, right: u32) -> u32 {
    left.saturating_add(right)
}

#[cfg(test)]
mod tests {
    use super::add;

    #[test]
    fn adds() {
        assert_eq!(add(1, 2), 3);
    }
}
'''


def write_crate(root: Path, name: str, lib: str, *, workspace_lints: bool = True,
                deps: str = "") -> None:
    crate = root / "crates" / name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    lints = "\n[lints]\nworkspace = true\n" if workspace_lints else ""
    (crate / "Cargo.toml").write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\n'
        'edition.workspace = true\nrust-version.workspace = true\npublish.workspace = true\n'
        f'\n[dependencies]\n{deps}\n{lints}')
    (crate / "src/lib.rs").write_text(lib)


def with_items(items: str) -> str:
    """CLEAN plus extra top-level items before the test module."""
    head, tests = CLEAN.split("#[cfg(test)]")
    return f"{head}{items.strip()}\n\n#[cfg(test)]{tests}"


class RealtimeCommitGateTests(unittest.TestCase):
    def project(self, lib: str = CLEAN, *, root: Path | None = None, **crate) -> Path:
        root = root or copy_leaf("game-realtime", self._testMethodName.removeprefix("test_"))
        write_crate(root, "core", lib, **crate)
        if "deps" in crate:
            manifest = root / "Cargo.toml"
            manifest.write_text(manifest.read_text().replace(
                'members = ["crates/*"]\n', 'members = ["crates/*"]\nexclude = ["vendor"]\n'))
        locked = run_game(["cargo", "generate-lockfile", "--offline"], root)
        self.assertEqual(locked.returncode, 0, locked.stderr)
        return root

    def commit(self, root: Path) -> subprocess.CompletedProcess[str]:
        return run_game(["sh", "scripts/check.sh", "commit"], root)

    def assert_rejected(self, result: subprocess.CompletedProcess[str], needle: str):
        """Needles are diagnostic text (Clippy help anchors, rustc -D/-F notes, check.sh errors)."""
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(needle, result.stderr)

    def test_clean_workspace_without_dependencies_passes(self):
        result = self.commit(self.project())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stages = [f"stage: {name}" for name in ("format", "lint", "deps", "test")]
        positions = [result.stdout.find(stage) for stage in stages]
        self.assertNotIn(-1, positions, result.stdout)
        self.assertEqual(positions, sorted(positions))

    def test_internal_path_dependency_passes(self):
        # Versionless path deps between the workspace's own crates are not banned wildcards.
        root = copy_leaf("game-realtime", "internal_path_dependency")
        write_crate(root, "rules", CLEAN)
        lib = CLEAN.replace("left.saturating_add(right)", "rules::add(left, right)")
        result = self.commit(self.project(lib, root=root, deps='rules = { path = "../rules" }'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_binary_only_crate_passes(self):
        root = self.project()
        source = root / "crates/core/src"
        main = CLEAN.replace("#[cfg(test)]", "fn main() {\n"
                             "    let _ = add(u32::try_from(std::env::args().count()).unwrap_or(0), 1);\n"
                             "}\n\n#[cfg(test)]")
        (source / "lib.rs").unlink()
        (source / "main.rs").write_text(main)
        result = self.commit(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("doctests: skipped (no library targets)", result.stdout)

    def test_unwrap_allowed_only_in_tests(self):
        in_test = CLEAN.replace("assert_eq!(add(1, 2), 3);",
                                'assert_eq!(add(1, "2".parse().unwrap()), 3);')
        result = self.commit(self.project(in_test))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        in_body = with_items('''
/// Parses a score.
///
/// # Panics
///
/// Panics when `text` is not a number.
#[must_use]
pub fn parse(text: &str) -> u32 {
    text.parse().unwrap()
}
''')
        self.assert_rejected(self.commit(self.project(in_body)), "#unwrap_used")

    def test_print_rejected(self):
        lib = with_items('''
/// Greets.
pub fn greet() {
    println!("hello");
}
''')
        self.assert_rejected(self.commit(self.project(lib)), "#print_stdout")

    def test_missing_docs_rejected(self):
        lib = with_items('''
#[must_use]
pub const fn double(value: u32) -> u32 {
    value.saturating_mul(2)
}
''')
        self.assert_rejected(self.commit(self.project(lib)), "`-D missing-docs`")

    def test_unsafe_rejected(self):
        lib = with_items('''
/// Reads the first byte.
#[must_use]
pub fn first(bytes: &[u8]) -> Option<u8> {
    if bytes.is_empty() {
        return None;
    }
    // SAFETY: `bytes` is not empty.
    Some(unsafe { *bytes.get_unchecked(0) })
}
''')
        self.assert_rejected(self.commit(self.project(lib)), "`-F unsafe-code`")

    def test_pedantic_rejected(self):
        lib = with_items('''
/// Returns a constant score.
pub fn bonus() -> Vec<u32> {
    vec![1]
}
''')
        self.assert_rejected(self.commit(self.project(lib)), "#must_use_candidate")

    def test_thread_sleep_rejected(self):
        lib = with_items('''
/// Waits one tick.
pub fn wait() {
    std::thread::sleep(std::time::Duration::from_millis(1));
}
''')
        self.assert_rejected(self.commit(self.project(lib)), "#disallowed_methods")

    def test_format_rejected(self):
        lib = CLEAN.replace("left.saturating_add(right)", "left.saturating_add( right )")
        result = self.commit(self.project(lib))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: format", result.stdout)
        self.assertNotIn("stage: lint", result.stdout)

    def test_member_without_workspace_lints_rejected(self):
        result = self.commit(self.project(workspace_lints=False))
        self.assert_rejected(result, "member must set [lints] workspace = true")

    def test_unused_dependency_rejected(self):
        root = copy_leaf("game-realtime", "unused_dependency")
        dep = write_fake_crate(root, "helper", "//! Stand-in crate.\n")
        root = self.project(root=root, deps=dep)
        result = self.commit(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: deps", result.stdout)
        self.assertIn("unused dependency `helper`", result.stdout)
        self.assertNotIn("stage: test", result.stdout)

    def test_zero_tests_rejected(self):
        lib = CLEAN.split("#[cfg(test)]")[0].rstrip() + "\n"
        result = self.commit(self.project(lib))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: test", result.stdout)
        self.assertIn("no tests to run", result.stderr)

    def test_missing_lock_or_tool_rejected(self):
        root = self.project()
        (root / "Cargo.lock").unlink()
        self.assert_rejected(self.commit(root), "missing Cargo.lock")
        root = self.project()
        env = game_env(root)
        tools = str(CACHE / "tools/bin")
        env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if p != tools)
        result = subprocess.run(["sh", "scripts/check.sh", "commit"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assert_rejected(result, "cargo-nextest 0.9.150 must already be installed")
        fake = root / "fakebin"
        fake.mkdir()
        (fake / "cargo-nextest").write_text("#!/bin/sh\necho 'cargo-nextest 0.9.149'\n")
        (fake / "cargo-nextest").chmod(0o755)
        env["PATH"] = os.pathsep.join([str(fake), env["PATH"]])
        result = subprocess.run(["sh", "scripts/check.sh", "commit"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assert_rejected(result, "requires cargo-nextest 0.9.150 (found: cargo-nextest 0.9.149)")

    def test_failure_stops_later_stages(self):
        lib = with_items('''
/// Greets.
pub fn greet() {
    println!("hello");
}
''')
        result = self.commit(self.project(lib))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: lint", result.stdout)
        self.assertNotIn("stage: deps", result.stdout)
        self.assertNotIn("stage: test", result.stdout)


if __name__ == "__main__":
    unittest.main()
