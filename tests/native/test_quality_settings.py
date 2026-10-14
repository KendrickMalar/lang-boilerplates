"""Real fixed-tool acceptance: copied settings reject defects and accept corrected code.

No dependencies are installed. Fixtures and logs remain under this worktree.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".verification/native/quality"


def fixture(prefix):
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=prefix + "-", dir=CACHE))
    (root / "home").mkdir()
    return root


def run(command, root, *, env=None, input=None):
    environment = os.environ.copy()
    environment.update(HOME=str(root / "home"), CFFIXED_USER_HOME=str(root / "home"))
    if env:
        environment.update(env)
    result = subprocess.run(command, cwd=root, env=environment, input=input,
                            text=True, capture_output=True, timeout=120, check=False)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    path = logs / f"{len(list(logs.iterdir())):03d}.log"
    path.write_text(f"command={command!r}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


class RustQualityTests(unittest.TestCase):
    def test_individual_clippy_rules_reject_defects_and_accept_corrections(self):
        # Removing a selected lint from the copied manifest must break its case.
        rustup = shutil.which("rustup")
        self.assertIsNotNone(rustup, "existing rustup required; do not install")
        lookup = subprocess.run([rustup, "which", "--toolchain", "1.92.0", "cargo"],
                                env={**os.environ, "RUSTUP_AUTO_INSTALL": "0"},
                                text=True, capture_output=True, check=False)
        self.assertEqual(lookup.returncode, 0, lookup.stderr)
        cargo = Path(lookup.stdout.strip())
        cases = [
            ("redundant_clone", 'let name = String::from("hello"); let copy = name.clone(); println!("{copy}");',
             'let name = String::from("hello"); let copy = name; println!("{copy}");'),
            ("assigning_clones", 'let mut target = String::new(); println!("{target}"); let source = String::from("hello"); target = source.clone(); println!("{target}");',
             'let mut target = String::new(); println!("{target}"); let source = String::from("hello"); target.clone_from(&source); println!("{target}");'),
            ("or_fun_call", 'let value: Option<String> = std::env::args().nth(1); let text = value.unwrap_or(String::from("fallback")); println!("{text}");',
             'let value: Option<String> = std::env::args().nth(1); let text = value.unwrap_or_else(|| String::from("fallback")); println!("{text}");'),
        ]
        settings = (ROOT / "rust/tauri/src-tauri/Cargo.toml").read_text()
        lint_tables = settings[settings.index("[lints.rust]"):]
        for rule, bad, good in cases:
            with self.subTest(rule=rule):
                root = fixture(rule)
                (root / "src").mkdir()
                (root / "Cargo.toml").write_text('[package]\nname="quality-fixture"\nversion="0.1.0"\nedition="2024"\n' + lint_tables)
                env = {"PATH": str(cargo.parent) + os.pathsep + os.environ["PATH"],
                       "CARGO_HOME": str(root / "cargo"), "CARGO_TARGET_DIR": str(root / "target"),
                       "RUSTC": str(cargo.parent / "rustc"), "RUSTUP_AUTO_INSTALL": "0", "CARGO_NET_OFFLINE": "true"}
                version = run([str(cargo.parent / "rustc"), "--version"], root, env=env)
                self.assertEqual(version.returncode, 0, version.stderr)
                self.assertIn("rustc 1.92.0 ", version.stdout)
                command = [str(cargo), "clippy", "--offline", "--all-targets", "--", "-D", "warnings"]
                (root / "src/main.rs").write_text("fn main() { " + bad + " }\n")
                rejected = run(command, root, env=env)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn(rule, rejected.stderr)
                (root / "src/main.rs").write_text("fn main() { " + good + " }\n")
                accepted = run(command, root, env=env)
                self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)


class SwiftQualityTests(unittest.TestCase):
    def setUp(self):
        self.swiftlint = shutil.which("swiftlint")
        self.assertIsNotNone(self.swiftlint, "existing SwiftLint required; do not install")
        self.developer = os.environ.get("DEVELOPER_DIR", "/Applications/Xcode.app/Contents/Developer")
        self.assertTrue(Path(self.developer).is_dir(), "existing full Xcode required")

    def lint(self, root):
        version = run([self.swiftlint, "version"], root)
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), "0.65.1")
        return run([self.swiftlint, "lint", "--strict", "--no-cache", "--config", ".swiftlint.yml", "Sample.swift"], root,
                   env={"DEVELOPER_DIR": self.developer})

    def copy_settings(self, platform):
        root = fixture("swift-" + platform)
        for name in [".swiftlint.yml", ".swift-format"]:
            shutil.copy2(ROOT / "swift" / platform / name, root / name)
        return root

    def test_selected_swiftlint_rules_reject_defects_and_accept_corrections(self):
        cases = [
            ("identical_operands", "func equal(_ left: Int, _ right: Int) -> Bool { left == left }\n",
             "func equal(_ left: Int, _ right: Int) -> Bool { left == right }\n"),
            ("discarded_notification_center_observer", 'import Foundation\nfunc observe(_ center: NotificationCenter) {\n    center.addObserver(forName: .NSSystemTimeZoneDidChange, object: nil, queue: nil) { _ in }\n}\n',
             'import Foundation\nfunc observe(_ center: NotificationCenter) -> NSObjectProtocol {\n    let observer = center.addObserver(forName: .NSSystemTimeZoneDidChange, object: nil, queue: nil) { _ in }\n    return observer\n}\n'),
            ("unhandled_throwing_task", 'func throwingWork() throws {}\nfunc launch() {\n    Task { try throwingWork() }\n}\n',
             'func throwingWork() throws {}\nfunc launch() async throws {\n    let task = Task { try throwingWork() }\n    try await task.value\n}\n'),
            ("balanced_xctest_lifecycle", 'import XCTest\nfinal class SampleTests: XCTestCase {\n    var value = 0\n    override func setUp() { super.setUp(); value = 1 }\n    func testValue() { XCTAssertEqual(2 + 2, 4) }\n}\n',
             'import XCTest\nfinal class SampleTests: XCTestCase {\n    var value = 0\n    override func setUp() { super.setUp(); value = 1 }\n    override func tearDown() { value = 0; super.tearDown() }\n    func testValue() { XCTAssertEqual(2 + 2, 4) }\n}\n'),
            ("empty_xctest_method", 'import XCTest\nfinal class SampleTests: XCTestCase {\n    func testValue() {}\n}\n',
             'import XCTest\nfinal class SampleTests: XCTestCase {\n    func testValue() { XCTAssertEqual(2 + 2, 4) }\n}\n'),
        ]
        for platform in ["macos", "ios"]:
            for rule, bad, good in cases:
                with self.subTest(platform=platform, rule=rule):
                    root = self.copy_settings(platform)
                    (root / "Sample.swift").write_text(bad)
                    rejected = self.lint(root)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertIn(rule, rejected.stdout + rejected.stderr)
                    (root / "Sample.swift").write_text(good)
                    accepted = self.lint(root)
                    self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

    def test_formatted_collections_and_long_strings_pass_both_tools(self):
        sources = [
            'let words = [\n"alpha",\n"beta",\n"gamma"\n]\nprint(words)\n',
            'let message = "' + "A" * 220 + '"\nprint(message)\n',
        ]
        for platform in ["macos", "ios"]:
            for source in sources:
                with self.subTest(platform=platform, source=source[:40]):
                    root = self.copy_settings(platform)
                    env = {"DEVELOPER_DIR": self.developer}
                    command = ["xcrun", "swift-format", "format", "--configuration", ".swift-format"]
                    formatted = run(command, root, env=env, input=source)
                    self.assertEqual(formatted.returncode, 0, formatted.stderr)
                    second = run(command, root, env=env, input=formatted.stdout)
                    self.assertEqual(second.returncode, 0, second.stderr)
                    self.assertEqual(second.stdout, formatted.stdout)
                    (root / "Sample.swift").write_text(formatted.stdout)
                    checked = run(["xcrun", "swift-format", "lint", "--strict", "--configuration", ".swift-format", "Sample.swift"], root, env=env)
                    self.assertEqual(checked.returncode, 0, checked.stderr)
                    linted = self.lint(root)
                    self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)


class LuauQualityTests(unittest.TestCase):
    def test_lint_only_defect_fails_and_normal_or_intentionally_unused_code_passes(self):
        tool = Path.home() / ".rokit/tool-storage/johnnymorganz/luau-lsp/1.69.0/luau-lsp"
        self.assertTrue(tool.is_file(), "existing luau-lsp 1.69.0 required; do not install")
        root = fixture("luau")
        shutil.copy2(ROOT / "roblox/rojo/.luaurc", root / ".luaurc")
        version = run([str(tool), "--version"], root)
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("1.69.0", version.stdout)
        (root / "Sample.luau").write_text("local unused = 1\nreturn 2\n")
        command = [str(tool), "analyze", "--platform=standard", "Sample.luau"]
        rejected = run(command, root)
        output = rejected.stdout + rejected.stderr
        self.assertNotEqual(rejected.returncode, 0, output)
        self.assertIn("LocalUnused", output)
        self.assertNotIn("TypeError", output)
        for good in ["local value = 1\nreturn value\n", "local _unused = 1\nreturn 2\n"]:
            (root / "Sample.luau").write_text(good)
            accepted = run(command, root)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)


if __name__ == "__main__":
    unittest.main()
