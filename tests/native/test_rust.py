"""Exercise actual Cargo gates: removing a gate must break a rejection test."""
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.native.rust_helpers import (
    CACHE,
    LEAF,
    LIB_SOURCE,
    copy_rust_fixture,
    run_rust,
    rust_env,
    verify_conditional_msrv,
)


class RustFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = copy_rust_fixture()
        cls.baseline = {p: p.read_bytes() for p in cls.fixture.rglob("*")
                        if p.is_file() and ("src-tauri/src" in str(p) or p.name in
                            {"Cargo.lock", "Cargo.toml", "build.rs", "tauri.conf.json", "main.json", "rust-toolchain.toml"})}

    def setUp(self):
        from tests.native.rust_helpers import restore_rust_baseline
        restore_rust_baseline(self.fixture, self.baseline)
        self.assertTrue(all(path.read_bytes() == data for path, data in self.baseline.items()))


    def check(self, stage="all"):
        result = run_rust(["sh", "scripts/check.sh", stage], self.fixture)
        result.stdout += result.stderr
        return result

    def rejected(self, result, diagnostic):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(diagnostic, result.stdout)



class RustTests(RustFixtureTests):
    def test_clean_rust_check(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        for stage in ["format", "lint", "test", "build"]:
            self.assertIn(f"stage: {stage}", result.stdout)
        self.assertIn("1 passed", result.stdout)
        self.assertIn("rustc 1.92.0", result.stdout)
        proof = json.loads((self.fixture / "dependency-evidence.json").read_text())
        self.assertEqual(proof["lock_sha256"], hashlib.sha256((self.fixture / "src-tauri/Cargo.lock").read_bytes()).hexdigest())
        self.assertEqual([command["exit"] for command in proof["commands"]], [0, 0])
        self.assertEqual(proof["target"], str(CACHE / "targets" / self.fixture.name))
        self.assertEqual(len(proof["undeclared_msrv"]), 106)

    def test_conditional_msrv_rejects_actual_build_failure_failed_test_and_empty_test(self):
        original = json.loads((self.fixture / "dependency-evidence.json").read_text())
        main = self.fixture / "src-tauri/src/main.rs"
        lib = self.fixture / "src-tauri/src/lib.rs"
        for stage, contents in [("build", "fn invalid rust"), ("test", LIB_SOURCE.replace("super::add(2, 3), 5", "super::add(2, 3), 6")),
                                ("test", "pub fn no_tests() {}\n")]:
            main.write_text(contents if stage == "build" else "fn main() {}\n")
            lib.write_text(LIB_SOURCE if stage == "build" else contents)
            with self.subTest(stage=stage, contents=contents), self.assertRaisesRegex(RuntimeError, f"{stage} evidence failed"):
                verify_conditional_msrv(self.fixture, original["undeclared_msrv"])
            proof = json.loads((self.fixture / "dependency-evidence.json").read_text())
            self.assertNotEqual(proof["commands"][-1]["exit"], 0)
            self.assertEqual(len(proof["commands"]), 1 if stage == "build" else 2)

    def test_format_rejected(self):
        (self.fixture / "src-tauri/src/main.rs").write_text("fn main(){println!(\"hi\");}\n")
        result = self.check()
        self.rejected(result, "Diff in")
        self.assertNotIn("stage: lint", result.stdout)

    def test_unwrap_rejected(self):
        (self.fixture / "src-tauri/src/main.rs").write_text(
            "fn main() {\n    let value = std::env::var(\"MISSING\").unwrap();\n    println!(\"{value}\");\n}\n")
        result = self.check()
        self.rejected(result, "unwrap_used")
        self.assertNotIn("stage: test", result.stdout)

    def test_unused_result_rejected(self):
        (self.fixture / "src-tauri/src/main.rs").write_text(
            "fn main() {\n    std::fs::read(\"missing\");\n}\n")
        result = self.check()
        self.rejected(result, "unused-must-use")
        self.assertNotIn("stage: test", result.stdout)

    def test_failure_stops_build(self):
        (self.fixture / "src-tauri/src/lib.rs").write_text(
            LIB_SOURCE.replace("super::add(2, 3), 5", "super::add(2, 3), 6"))
        result = self.check()
        self.rejected(result, "test result: FAILED")
        self.assertNotIn("stage: build", result.stdout)

    def test_missing_source_test_lock_or_tool_rejected(self):
        lib = self.fixture / "src-tauri/src/lib.rs"
        main = self.fixture / "src-tauri/src/main.rs"
        for contents in ["", " \n"]:
            with self.subTest(source=repr(contents)):
                lib.write_text(contents)
                main.write_text(contents)
                self.rejected(self.check(), "source")
        lib.write_text("pub fn add(left: u32, right: u32) -> u32 {\n    left + right\n}\n")
        main.write_text("fn main() {}\n")
        self.rejected(self.check("test"), "no tests")
        lib.write_text(LIB_SOURCE.replace("    #[test]", "    #[test]\n    #[ignore]"))
        self.rejected(self.check("test"), "no tests executed")
        lib.write_text(LIB_SOURCE)
        for source in [main, lib, self.fixture / "src-tauri/Cargo.toml"]:
            source.rename(source.with_suffix(".saved"))
            self.rejected(self.check(), "missing")
            source.with_suffix(".saved").rename(source)
        lock = self.fixture / "src-tauri/Cargo.lock"
        lock.rename(lock.with_suffix(".saved"))
        self.rejected(self.check(), "Cargo.lock")
        lock.with_suffix(".saved").rename(lock)
        saved_lock = lock.read_text()
        lock.write_text("")
        self.rejected(self.check(), "Cargo.lock")
        lock.write_text(saved_lock)
        # A fresh empty Rustup HOME must fail before any rustup auto-bootstrap.
        env = rust_env(self.fixture)
        empty = Path(tempfile.mkdtemp(prefix="empty-rustup-", dir=self.fixture))
        env["RUSTUP_HOME"] = str(empty)
        env["RUSTUP_AUTO_INSTALL"] = "1"
        result = subprocess.run(["sh", "scripts/check.sh"], cwd=self.fixture, env=env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (self.fixture / f"missing-tool-{time.time_ns()}.log").write_text(f"exit={result.returncode}\n{result.stdout}")
        self.rejected(result, "installed")
        self.assertFalse((empty / "toolchains").exists())
        self.assertFalse((empty / "downloads").exists())
        self.assertNotIn("stage:", result.stdout)
        env["PATH"] = "/usr/bin:/bin"
        result = subprocess.run(["sh", "scripts/check.sh"], cwd=self.fixture, env=env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (self.fixture / f"missing-rustup-{time.time_ns()}.log").write_text(f"exit={result.returncode}\n{result.stdout}")
        self.rejected(result, "rustup must already be installed")

    def test_missing_components_do_not_install(self):
        installed = next((CACHE / "rustup/toolchains").glob("1.92.0-*"))
        for missing in ["cargo-fmt", "cargo-clippy"]:
            home = Path(tempfile.mkdtemp(prefix="missing-" + missing + "-", dir=self.fixture))
            binaries = home / "toolchains" / installed.name / "bin"
            binaries.mkdir(parents=True)
            for name in ["cargo", "rustc", "cargo-fmt", "cargo-clippy"]:
                if name != missing:
                    (binaries / name).symlink_to(installed / "bin" / name)
            env = rust_env(self.fixture)
            env["RUSTUP_HOME"] = str(home)
            env["RUSTUP_AUTO_INSTALL"] = "1"
            result = subprocess.run(["sh", "scripts/check.sh"], cwd=self.fixture, env=env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            (self.fixture / f"{missing}-{time.time_ns()}.log").write_text(f"exit={result.returncode}\n{result.stdout}")
            self.rejected(result, "installed")
            self.assertNotIn("stage:", result.stdout)
            self.assertFalse((home / "downloads").exists())
            self.assertFalse((binaries / missing).exists())

    def test_permission_and_old_tool_rejected(self):
        env = rust_env(self.fixture)
        blocked = Path(tempfile.mkdtemp(prefix="blocked-target-", dir=self.fixture))
        blocked.chmod(0o500)
        env["CARGO_TARGET_DIR"] = str(blocked / "target")
        result = subprocess.run(["sh", "scripts/check.sh", "build"], cwd=self.fixture,
                                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (self.fixture / f"permission-{time.time_ns()}.log").write_text(f"exit={result.returncode}\n{result.stdout}")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        blocked.chmod(0o700)
        self.assertIn("Permission denied", result.stdout)
        # Mutated pin must not silently run current/default stable.
        (self.fixture / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.91.0"\n')
        self.rejected(self.check(), "1.92.0")

    def test_reused_target_recovers_from_ignored_failed_invalid_source_and_config(self):
        from tests.native import rust_helpers
        restore = getattr(rust_helpers, "restore_rust_baseline", None)
        self.assertTrue(callable(restore), "missing audited fixture baseline restore")
        lib = self.fixture / "src-tauri/src/lib.rs"
        main = self.fixture / "src-tauri/src/main.rs"
        config = self.fixture / "src-tauri/tauri.conf.json"
        for path, contents, stage, diagnostic in [
            (lib, LIB_SOURCE.replace("    #[test]", "    #[test]\n    #[ignore]"), "test", "no tests executed"),
            (lib, LIB_SOURCE.replace("super::add(2, 3), 5", "super::add(2, 3), 6"), "test", "FAILED"),
            (main, "fn invalid rust", "build", "error"),
            (config, "{}", "build", "error"),
        ]:
            with self.subTest(contents=contents):
                path.write_text(contents)
                self.rejected(self.check(stage), diagnostic)
                restore(self.fixture, self.baseline)
                result = self.check("all")
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("1 passed", result.stdout)


class TauriBoundaryTests(RustFixtureTests):
    # Own fixture/target; do not inherit the quality test cases.
    @classmethod
    def setUpClass(cls):
        if not (LEAF / "src-tauri/build.rs").exists():
            cls.fixture = None
            return
        super().setUpClass()
        from tests.native.rust_helpers import configure_tauri_fixture
        configure_tauri_fixture(cls.fixture)
        cls.baseline = {p: p.read_bytes() for p in cls.fixture.rglob("*")
                        if p.is_file() and ("src-tauri/src" in str(p) or p.name in
                            {"Cargo.lock", "Cargo.toml", "build.rs", "tauri.conf.json", "main.json", "rust-toolchain.toml"})}

    def setUp(self):
        self.assertIsNotNone(self.fixture, "Tauri boundary settings missing")
        super().setUp()

    def test_allowed_and_denied_ipc(self):
        result = self.check("all")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("tests::allowed_and_denied_ipc ... ok", result.stdout)
        result = self.check("build")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_custom_command_boundary_not_plugin_only(self):
        build = self.fixture / "src-tauri/build.rs"
        # Ignore stale autogenerated app permissions without deleting evidence.
        build.write_text(build.read_text().replace(
            '.commands(&["allowed", "denied"])',
            '.commands(&[]).permissions_path_pattern("permissions-empty/**/*")'))
        capability = self.fixture / "src-tauri/capabilities/main.json"
        value = json.loads(capability.read_text())
        value["permissions"] = ["core:window:allow-title"]
        capability.write_text(json.dumps(value))
        result = self.check("test")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("unregistered command bypassed ACL", result.stdout)
        from tests.native.rust_helpers import restore_rust_baseline
        restore_rust_baseline(self.fixture, self.baseline)
        result = self.check("test")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("1 passed", result.stdout)

    def test_missing_frontend_native_build_rejected(self):
        config = self.fixture / "src-tauri/tauri.conf.json"
        value = json.loads(config.read_text())
        value["build"]["frontendDist"] = "../missing-dist"
        config.write_text(json.dumps(value))
        result = self.check("build")
        self.rejected(result, "frontendDist")


class DependencyApprovalTests(unittest.TestCase):
    def setUp(self):
        from tests.native import rust_helpers
        candidate = getattr(rust_helpers, "validate_rust_dependencies", None)
        self.assertTrue(callable(candidate), "missing fixed-lock dependency approval gate")
        assert callable(candidate)
        self.validator = candidate
        self.record = Path(tempfile.mkdtemp(prefix="approval-test-", dir=CACHE))
        shutil.copytree(CACHE / "approved-resolution", self.record, dirs_exist_ok=True)
        self.lock = self.record / "Cargo.lock"
        self.metadata = json.loads((self.record / "metadata.json").read_text())

    def test_dependency_approval_accepts_fixed_evidenced_set(self):
        undeclared = self.validator(self.metadata, self.lock, self.record)
        self.assertEqual(len(undeclared), 106)

    def test_dependency_approval_rejects_unknown_name_version_source_and_msrv(self):
        for field, value in [("name", "unapproved"), ("version", "999.0.0"),
                             ("source", "registry+https://unknown.invalid"), ("rust_version", "1.91")]:
            metadata = copy.deepcopy(self.metadata)
            metadata["packages"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "unknown.*consult supervisor"):
                self.validator(metadata, self.lock, self.record)
        metadata = copy.deepcopy(self.metadata)
        for version in ["1.93", "1.92.1"]:
            metadata["packages"][0]["rust_version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(RuntimeError, "MSRV mismatch"):
                self.validator(metadata, self.lock, self.record)

    def test_dependency_approval_rejects_absent_record_and_changed_lock(self):
        with self.assertRaisesRegex(RuntimeError, "approval.*consult supervisor"):
            self.validator(self.metadata, self.lock, self.record / "absent")
        self.lock.write_text(self.lock.read_text() + "\n# changed\n")
        with self.assertRaisesRegex(RuntimeError, "lock.*consult supervisor"):
            self.validator(self.metadata, self.lock, self.record)

    def test_dependency_approval_rejects_failed_empty_unperformed_or_wrong_lock_evidence(self):
        original = json.loads((self.record / "approval.json").read_text())
        original_proof = json.loads((self.record / original["evidence"]["test"]["file"]).read_text())
        for field, value in [("exit", 101), ("stdout", "stage: test\n0 passed"),
                             ("command", []), ("lock_sha256", "different")]:
            record = copy.deepcopy(original)
            entry = record["evidence"]["test"]
            proof = copy.deepcopy(original_proof)
            proof[field] = value
            (self.record / entry["file"]).write_text(json.dumps(proof))
            entry["sha256"] = hashlib.sha256((self.record / entry["file"]).read_bytes()).hexdigest()
            (self.record / "approval.json").write_text(json.dumps(record))
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "evidence.*consult supervisor"):
                self.validator(self.metadata, self.lock, self.record)


class RustEnvironmentEvidenceTests(unittest.TestCase):
    def setUp(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="helper-contract-", dir=CACHE))

    def test_parent_home_is_not_used_by_environment_or_subprocess(self):
        import os
        import sys
        from unittest.mock import patch
        parent = self.root / "parent-home"
        parent.mkdir()
        expected = self.root / "home"
        with patch.dict(os.environ, {"HOME": str(parent), "CFFIXED_USER_HOME": str(parent),
                                     "RUSTUP_AUTO_INSTALL": "1"}):
            env = rust_env(self.root)
            self.assertEqual(env["HOME"], str(expected))
            self.assertEqual(env["CFFIXED_USER_HOME"], str(expected))
            self.assertTrue(expected.is_dir())
            result = run_rust([sys.executable, "-c",
                'import os,json; from pathlib import Path; '
                'Path(os.environ["HOME"], "subprocess-marker").write_text("isolated"); '
                'print(json.dumps({key: os.environ[key] for key in '
                '("HOME", "CFFIXED_USER_HOME", "RUSTUP_AUTO_INSTALL", "CARGO_NET_OFFLINE", '
                '"CARGO_HOME", "RUSTUP_HOME", "CARGO_TARGET_DIR")}))'], self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["HOME"], str(expected))
        self.assertEqual(actual["CFFIXED_USER_HOME"], str(expected))
        self.assertEqual(actual["RUSTUP_AUTO_INSTALL"], "0")
        self.assertEqual(actual["CARGO_NET_OFFLINE"], "true")
        self.assertEqual(actual["CARGO_HOME"], str(CACHE / "cargo"))
        self.assertEqual(actual["RUSTUP_HOME"], str(CACHE / "rustup"))
        self.assertEqual(actual["CARGO_TARGET_DIR"], str(CACHE / "targets" / self.root.name))
        self.assertTrue((expected / "subprocess-marker").is_file())
        self.assertEqual(list(parent.iterdir()), [])
        receipts = [json.loads(path.read_text()) for path in (CACHE / "logs").glob(self.root.name + "-*.json")]
        self.assertEqual(receipts[-1]["environment"]["HOME"], str(expected))

    def test_cwdless_environment_uses_cache_home_not_parent_home(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"HOME": str(self.root), "CFFIXED_USER_HOME": str(self.root)}):
            env = rust_env()
        self.assertEqual(env["HOME"], str(CACHE / "home"))
        self.assertEqual(env["CFFIXED_USER_HOME"], str(CACHE / "home"))
        self.assertTrue((CACHE / "home").is_dir())
        self.assertEqual(env["CARGO_TARGET_DIR"], str(CACHE / "target"))

    def test_receipt_hashes_all_inputs_without_generated_or_cache_trees(self):
        import sys
        included = ["src-tauri/src/nested/custom.input", "src-tauri/custom-config/policy.data",
                    "src-tauri/permissions/nested/command.toml", "src-tauri/Cargo.lock",
                    "src-tauri/Cargo.toml", "src-tauri/build.rs", "rust-toolchain.toml",
                    "rustfmt.toml", ".cargo/config.toml", "scripts/check.sh", "dist/index.html",
                    "src-tauri/src/cache/mod.rs", "src-tauri/src/nested/target/mod.rs",
                    "src-tauri/permissions/gen/command.toml", "src-tauri/cache/policy.toml",
                    "src-tauri/.cache/input.data", "scripts/target/custom.sh",
                    ".cargo/cache/config.toml", "dist/gen/input.html"]
        excluded = ["src-tauri/target/debug/binary", "src-tauri/gen/schema.json",
                    "target/build/binary", "src-tauri/src/.git/objects/blob",
                    "home/cache/artifact", ".git/objects/blob"]
        for name in included + excluded:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        result = run_rust([sys.executable, "-c", "print('receipt probe')"], self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipts = list((CACHE / "logs").glob(self.root.name + "-*.json"))
        self.assertEqual(len(receipts), 1)
        hashes = json.loads(receipts[0].read_text())["files_sha256"]
        self.assertEqual(set(hashes), set(included))
        for name in included:
            self.assertEqual(hashes[name], hashlib.sha256(name.encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
