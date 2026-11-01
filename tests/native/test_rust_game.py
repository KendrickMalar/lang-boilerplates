"""Real-tool gates for the Rust server leaves (isolated toolchain, offline)."""
import os
import subprocess
import unittest
from pathlib import Path

from tests.native.rust_game_helpers import (CACHE, LEAVES, copy_leaf, game_env, run_game,
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


LINTS_FORMS = {
    "table": ("", "\n[lints]\nworkspace = true\n"),
    "dotted": ("lints.workspace = true\n\n", ""),
    "inline": ("lints = { workspace = true }\n\n", ""),
}


def write_crate(root: Path, name: str, lib: str, *, workspace_lints: bool = True,
                deps: str = "", lints_form: str = "table") -> None:
    crate = root / "crates" / name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    head, lints = LINTS_FORMS[lints_form] if workspace_lints else ("", "")
    (crate / "Cargo.toml").write_text(
        f'{head}[package]\nname = "{name}"\nversion = "0.1.0"\n'
        'edition.workspace = true\nrust-version.workspace = true\npublish.workspace = true\n'
        f'\n[dependencies]\n{deps}\n{lints}')
    (crate / "src/lib.rs").write_text(lib)


def with_items(items: str) -> str:
    """CLEAN plus extra top-level items before the test module."""
    head, tests = CLEAN.split("#[cfg(test)]")
    return f"{head}{items.strip()}\n\n#[cfg(test)]{tests}"


class GameLeaf(unittest.TestCase):
    """Fixture helpers for one server leaf (no tests of its own); subclasses set `leaf`."""

    # Fixture directory prefix. None: the test name. Set a neutral one when a needle could
    # otherwise match the fixture path that tools echo (e.g. `Compiling core v0.1.0 (<path>)`).
    prefix: str | None = None
    leaf = "game"

    def project(self, lib: str = CLEAN, *, root: Path | None = None, **crate) -> Path:
        root = root or copy_leaf(self.leaf,
                                 self.prefix or self._testMethodName.removeprefix("test_"))
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


class GameCommitGateTests(GameLeaf):
    def test_clean_workspace_without_dependencies_passes(self):
        result = self.commit(self.project())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stages = [f"stage: {name}" for name in ("format", "lint", "deps", "coverage")]
        positions = [result.stdout.find(stage) for stage in stages]
        self.assertNotIn(-1, positions, result.stdout)
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("stage: test", result.stdout)  # coverage runs the tests once

    def test_internal_path_dependency_passes(self):
        # Versionless path deps between the workspace's own crates are not banned wildcards.
        root = copy_leaf("game", "internal_path_dependency")
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
        # The test stage: main() is untested, so the commit coverage floor would reject it first.
        result = run_game(["sh", "scripts/check.sh", "test"], root)
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

    def test_lints_workspace_true_forms_pass(self):
        # Cargo accepts the table, the dotted key and the inline table.
        for form in ("dotted", "inline"):
            with self.subTest(form=form):
                result = self.commit(self.project(lints_form=form))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_member_without_workspace_lints_rejected(self):
        result = self.commit(self.project(workspace_lints=False))
        self.assert_rejected(result, "member must set [lints] workspace = true")

    def test_unused_dependency_rejected(self):
        root = copy_leaf("game", "unused_dependency")
        dep = write_fake_crate(root, "helper", "//! Stand-in crate.\n")
        root = self.project(root=root, deps=dep)
        result = self.commit(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: deps", result.stdout)
        self.assertIn("unused dependency `helper`", result.stdout)
        self.assertNotIn("stage: coverage", result.stdout)

    def test_zero_tests_rejected(self):
        lib = CLEAN.split("#[cfg(test)]")[0].rstrip() + "\n"
        result = self.commit(self.project(lib))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stage: coverage", result.stdout)
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

    def test_failing_version_probe_rejected(self):
        # A tool that prints the right version but exits non-zero is not trusted.
        root = self.project()
        env = game_env(root)
        fake = root / "fakebin"
        fake.mkdir()
        (fake / "cargo-nextest").write_text("#!/bin/sh\necho 'cargo-nextest 0.9.150'\nexit 3\n")
        (fake / "cargo-nextest").chmod(0o755)
        env["PATH"] = os.pathsep.join([str(fake), env["PATH"]])
        result = subprocess.run(["sh", "scripts/check.sh", "commit"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assert_rejected(result, "cannot read cargo-nextest version")

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
        self.assertNotIn("stage: coverage", result.stdout)


UNTESTED = with_items('''
/// Scores a combo; deliberately left untested to drop line coverage.
#[must_use]
pub const fn combo(hits: u32) -> u32 {
    let base = hits.saturating_mul(10);
    let bonus = if hits > 5 { 50 } else { 0 };
    let streak = if hits > 10 { 100 } else { 0 };
    let total = base.saturating_add(bonus);
    let total = total.saturating_add(streak);
    let capped = if total > 1000 { 1000 } else { total };
    capped.saturating_mul(2)
}
''')
OFFLINE = "advisory database could not be fetched (network required)"
COVERAGE = "error: line coverage below 90% (--fail-under-lines 90)"
PUSH_STAGES = ["format", "lint", "deps", "coverage", "advisories", "build"]


class GamePushGateTests(GameLeaf):
    prefix = "push"

    def push(self, root: Path, *, online: bool = False,
             stage: str = "push") -> subprocess.CompletedProcess[str]:
        return run_game(["sh", "scripts/check.sh", stage], root, online=online)

    def assert_stage_order(self, result: subprocess.CompletedProcess[str]):
        positions = [result.stdout.find(f"stage: {name}") for name in PUSH_STAGES]
        self.assertNotIn(-1, positions, result.stdout)
        self.assertEqual(positions, sorted(positions))

    def test_push_passes_with_full_coverage(self):
        # Network: cargo-deny fetches the RustSec DB (https://github.com/rustsec/advisory-db)
        # into the isolated CARGO_HOME/advisory-dbs.
        result = self.push(self.project(), online=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_stage_order(result)

    def test_all_is_push(self):
        result = self.push(self.project(), online=True, stage="all")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_stage_order(result)

    def test_coverage_below_90_rejected(self):
        result = self.push(self.project(UNTESTED))
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("stage: coverage", result.stdout)
        self.assertNotIn("stage: advisories", result.stdout)
        self.assertIn("1 test run: 1 passed", result.stderr)  # the tests themselves passed
        self.assertIn(COVERAGE, result.stderr)

    def test_commit_rejects_coverage_below_90(self):
        result = self.push(self.project(UNTESTED), stage="commit")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("stage: coverage", result.stdout)
        self.assertIn("1 test run: 1 passed", result.stderr)  # the tests themselves passed
        self.assertIn(COVERAGE, result.stderr)

    def test_commit_runs_doctests_after_coverage(self):
        lib = CLEAN.replace("/// Adds two scores without overflowing.\n",
                            "/// Adds two scores without overflowing.\n///\n/// ```\n"
                            "/// assert_eq!(core::add(1, 2), 4);\n/// ```\n")
        result = self.push(self.project(lib), stage="commit")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("stage: coverage", result.stdout)
        self.assertIn("Doc-tests", result.stdout + result.stderr)
        self.assertNotIn(COVERAGE, result.stderr)

    def test_failing_test_under_coverage_is_not_a_threshold_miss(self):
        result = self.push(self.project(CLEAN.replace("3);", "4);")), stage="coverage")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("1 failed", result.stderr)
        self.assertNotIn(COVERAGE, result.stderr)

    def test_advisories_offline_failure_is_explained(self):
        result = self.push(self.project())
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("stage: advisories", result.stdout)
        self.assertNotIn("stage: build", result.stdout)
        self.assertIn(OFFLINE, result.stderr)

    def test_advisories_fetch_failure_is_explained(self):
        # Online mode but an unreachable proxy: the real fetch fails without using the network.
        root = self.project()
        env = game_env(root, online=True)
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY",
                    "all_proxy"):
            env[key] = "http://127.0.0.1:9"
        result = subprocess.run(["sh", "scripts/check.sh", "advisories"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(OFFLINE, result.stderr)

    def test_advisory_mentioning_network_is_not_a_fetch_failure(self):
        # A real advisory needs a registry crate in Cargo.lock, which cannot be resolved
        # offline from path-only fixtures; a stand-in cargo-deny 0.20.2 prints one instead.
        root = self.project()
        fake = root / "fakebin"
        fake.mkdir()
        (fake / "cargo-deny").write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then echo "cargo-deny 0.20.2"; exit 0; fi\n'
            "echo 'error[vulnerability]: Remote network peer can exhaust memory' >&2\n"
            "echo '  ID: RUSTSEC-2099-0001' >&2\n"
            "exit 1\n")
        (fake / "cargo-deny").chmod(0o755)
        env = game_env(root, online=True)
        env["PATH"] = os.pathsep.join([str(fake), env["PATH"]])
        result = subprocess.run(["sh", "scripts/check.sh", "advisories"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("RUSTSEC-2099-0001", result.stderr)
        self.assertIn("cargo deny check advisories failed (exit 1)", result.stderr)
        self.assertNotIn(OFFLINE, result.stderr)

    def test_build_is_release(self):
        result = self.push(self.project(), stage="build")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage: build", result.stdout)
        self.assertIn("Finished `release` profile", result.stderr)


class GameDeterminismRuleTests(GameLeaf):
    def lint(self, items: str) -> subprocess.CompletedProcess[str]:
        # Lint stage only: rule fixtures add untested items that the commit coverage floor rejects.
        return run_game(["sh", "scripts/check.sh", "lint"], self.project(with_items(items)))

    def test_unchecked_add_rejected(self):
        self.assert_rejected(self.lint('''
/// Adds two scores.
#[must_use]
pub const fn sum(left: u32, right: u32) -> u32 {
    left + right
}
'''), "#arithmetic_side_effects")

    def test_as_cast_rejected(self):
        self.assert_rejected(self.lint('''
/// Widens a score.
#[must_use]
pub const fn widen(value: u32) -> u64 {
    value as u64
}
'''), "#as_conversions")

    def test_indexing_rejected(self):
        self.assert_rejected(self.lint('''
/// Reads the first byte.
#[must_use]
pub const fn first(bytes: &[u8]) -> u8 {
    bytes[0]
}
'''), "#indexing_slicing")

    def test_instant_now_rejected(self):
        self.assert_rejected(self.lint('''
/// Reads the clock.
#[must_use]
pub fn now() -> std::time::Instant {
    std::time::Instant::now()
}
'''), "#disallowed_methods")

    def test_hashmap_new_rejected(self):
        self.assert_rejected(self.lint('''
/// Creates an empty table.
#[must_use]
pub fn table() -> std::collections::HashMap<u32, u32> {
    std::collections::HashMap::new()
}
'''), "#disallowed_types")

    def test_hashmap_collect_rejected(self):
        self.assert_rejected(self.lint('''
/// Indexes scores by themselves.
#[must_use]
pub fn table(scores: &[u32]) -> std::collections::HashMap<u32, u32> {
    scores.iter().map(|&score| (score, score)).collect()
}
'''), "#disallowed_types")

    def test_btreemap_passes(self):
        result = self.lint('''
/// Indexes scores by themselves in a deterministic order.
#[must_use]
pub fn table(scores: &[u32]) -> std::collections::BTreeMap<u32, u32> {
    scores.iter().map(|&score| (score, score)).collect()
}
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fixed_hasher_alias_with_expect_passes(self):
        # The README pattern: one reasoned #[expect] on a fixed-hasher alias.
        result = self.lint('''
/// Hash map with a fixed hasher: iteration order is the same on every run.
#[expect(clippy::disallowed_types, reason = "固定 hasher の alias")]
pub type FixedMap<K, V> =
    std::collections::HashMap<K, V, std::hash::BuildHasherDefault<std::hash::DefaultHasher>>;

/// Indexes scores by themselves.
#[must_use]
pub fn table(scores: &[u32]) -> FixedMap<u32, u32> {
    let mut map = FixedMap::default();
    map.extend(scores.iter().map(|&score| (score, score)));
    map
}
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_instant_now_with_expect_reason_passes(self):
        result = self.lint('''
/// Reads the clock once at the tick loop entry.
#[must_use]
#[expect(clippy::disallowed_methods, reason = "tick の入口")]
pub fn tick_start() -> std::time::Instant {
    std::time::Instant::now()
}
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# Stand-in crates, pre-formatted: `cargo fmt --all` also checks path dependencies.
TOKIO = """pub mod sync {
    pub mod mpsc {
        pub fn unbounded_channel() {}
    }
}
"""
FUTURES = """pub mod channel {
    pub mod mpsc {
        pub fn unbounded() {}
    }
}
"""
SQLX = """pub fn query(_: &str) {}
pub fn query_as(_: &str) {}
"""
REQWEST = """pub struct Client(u8);

impl Client {
    pub fn new() -> Self {
        Self(0)
    }
}

pub fn get(_: &str) {}
"""
BANNED_LIB = "pub fn encode() {}\n"


class FakeDependencyLeaf(GameLeaf):
    """Rule checks that need a dependency: a path-only stand-in crate keeps them offline."""

    prefix = "fakedep"

    def lint_with(self, crate: str, fake_lib: str, items: str) -> subprocess.CompletedProcess[str]:
        root = copy_leaf(self.leaf, self.prefix)
        dep = write_fake_crate(root, crate, fake_lib)
        return self.commit(self.project(with_items(items), root=root, deps=dep))


class AsyncLockRules:
    """await_holding_lock and the push gate, shared by the game, web-game, and web leaves."""

    def lint(self, items: str) -> subprocess.CompletedProcess[str]:
        # Lint stage only: rule fixtures add untested items that the commit coverage floor rejects.
        return run_game(["sh", "scripts/check.sh", "lint"], self.project(with_items(items)))

    def test_guard_held_across_await_rejected(self):
        self.assert_rejected(self.lint('''
/// Holds a guard across an await.
pub async fn held(lock: &std::sync::Mutex<u32>) {
    let guard = lock
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    std::future::ready(()).await;
    drop(guard);
}
'''), "#await_holding_lock")

    def test_guard_dropped_before_await_passes(self):
        result = self.lint('''
/// Reads the value, then awaits without holding the guard.
pub async fn released(lock: &std::sync::Mutex<u32>) -> u32 {
    let value = lock.lock().map_or(0, |guard| *guard);
    std::future::ready(()).await;
    value
}
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_clean_push_passes(self):
        # Network: cargo-deny fetches the RustSec DB into the isolated CARGO_HOME.
        result = run_game(["sh", "scripts/check.sh", "push"], self.project(), online=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        positions = [result.stdout.find(f"stage: {name}") for name in PUSH_STAGES]
        self.assertNotIn(-1, positions, result.stdout)
        self.assertEqual(positions, sorted(positions))


class GameAsyncRuleTests(AsyncLockRules, FakeDependencyLeaf):
    """Room rules merged into the game leaf (former game-room)."""

    leaf = "game"

    def test_unbounded_channel_rejected(self):
        self.assert_rejected(self.lint_with("tokio", TOKIO, '''
/// Opens a queue.
pub fn queue() {
    tokio::sync::mpsc::unbounded_channel();
}
'''), "#disallowed_methods")

    def test_futures_unbounded_rejected(self):
        self.assert_rejected(self.lint_with("futures", FUTURES, '''
/// Opens a queue.
pub fn queue() {
    futures::channel::mpsc::unbounded();
}
'''), "#disallowed_methods")


class WebGameRuleTests(AsyncLockRules, FakeDependencyLeaf):
    leaf = "web-game"

    def test_raw_sqlx_query_rejected(self):
        for call in ("query", "query_as"):
            with self.subTest(call=call):
                self.assert_rejected(self.lint_with("sqlx", SQLX, f'''
/// Runs a raw query.
pub fn run() {{
    sqlx::{call}("SELECT 1");
}}
'''), "#disallowed_methods")

    def test_reqwest_timeoutless_calls_rejected(self):
        # `Client::default` is a trait-impl method; Clippy cannot name it per type (not banned).
        for name, body in (("Client::new", "let _client = reqwest::Client::new();"),
                           ("get", 'reqwest::get("https://example.invalid");')):
            with self.subTest(call=name):
                self.assert_rejected(self.lint_with("reqwest", REQWEST, f'''
/// Calls a timeout-less reqwest entry point.
pub fn call() {{
    {body}
}}
'''), "#disallowed_methods")

    def test_without_sqlx_passes(self):
        root = self.project()
        self.assertFalse((root / ".sqlx").exists())
        result = self.commit(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sets_sqlx_offline(self):
        result = self.commit(self.project())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("env: SQLX_OFFLINE=true\n", result.stdout)

    def test_keeps_caller_sqlx_offline(self):
        root = self.project()
        env = game_env(root)
        env["SQLX_OFFLINE"] = "false"
        result = subprocess.run(["sh", "scripts/check.sh", "format"], cwd=root, env=env,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("env: SQLX_OFFLINE=false\n", result.stdout)


class WebRuleTests(WebGameRuleTests):
    """The generic HTTP API leaf has the same settings as web-game."""

    leaf = "web"


class ServerLeafTests(unittest.TestCase):
    def test_api_leaves_clean_commit_passes(self):
        for leaf in ("web-game", "web"):
            with self.subTest(leaf=leaf):
                root = copy_leaf(leaf, "cleancommit")
                write_crate(root, "core", CLEAN)
                locked = run_game(["cargo", "generate-lockfile", "--offline"], root)
                self.assertEqual(locked.returncode, 0, locked.stderr)
                result = run_game(["sh", "scripts/check.sh", "commit"], root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for stage in ("format", "lint", "deps", "coverage"):
                    self.assertIn(f"stage: {stage}", result.stdout)

    def assert_banned(self, leaf: str, crate: str):
        root = copy_leaf(leaf, "dep")
        dep = write_fake_crate(root, crate, BANNED_LIB)
        write_crate(root, "core", with_items(f'''
/// Calls the stand-in.
pub fn call() {{
    {crate.replace("-", "_")}::encode();
}}
'''), deps=dep)
        manifest = root / "Cargo.toml"
        manifest.write_text(manifest.read_text().replace(
            'members = ["crates/*"]\n', 'members = ["crates/*"]\nexclude = ["vendor"]\n'))
        locked = run_game(["cargo", "generate-lockfile", "--offline"], root)
        self.assertEqual(locked.returncode, 0, locked.stderr)
        result = run_game(["sh", "scripts/check.sh", "deps"], root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"error[banned]: crate '{crate} = 0.1.0' is explicitly banned", result.stderr)

    def test_banned_crate_rejected(self):
        # bincode is banned in every leaf; the stand-in crate is named after it.
        for leaf in LEAVES:
            with self.subTest(leaf=leaf):
                self.assert_banned(leaf, "bincode")

    def test_leaf_specific_ban_rejected(self):
        for leaf, crate in (("game", "actix"), ("web-game", "native-tls"), ("web", "native-tls")):
            with self.subTest(leaf=leaf, crate=crate):
                self.assert_banned(leaf, crate)


if __name__ == "__main__":
    unittest.main()
