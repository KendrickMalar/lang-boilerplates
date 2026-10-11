"""Real local Git commit/push with native checks; never remote services/global config."""
import hashlib
import json
import os
import re
import time
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.verification/native/catalog-hooks'


def global_hooks_snapshot():
    result = subprocess.run(['git', 'config', '--global', '--get', 'core.hooksPath'],
                            capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    path = Path(os.path.expandvars(os.path.expanduser(result.stdout.strip())))
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in path.rglob('*') if p.is_file()} if result.stdout.strip() and path.is_dir() else {}
    return {'path': result.stdout.strip(), 'hashes': files}


def copy_check_script(leaf, root):
    ref = os.environ.get('NATIVE_HOOK_CHECK_REF')
    if ref:
        if not re.fullmatch(r'[0-9a-f]{40}', ref):
            raise RuntimeError('invalid NATIVE_HOOK_CHECK_REF; full commit SHA required')
        data = subprocess.check_output(['git', 'show', f'{ref}:{leaf}/scripts/check.sh'], cwd=ROOT, stderr=subprocess.PIPE)
    else:
        data = (ROOT / leaf / 'scripts/check.sh').read_bytes()
    (root / 'scripts/check.sh').write_bytes(data)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f'check-selection-{time.time_ns()}.json').write_text(json.dumps({
        'fixture': str(root), 'leaf': leaf, 'selected_ref': ref or 'working-tree',
        'script_sha256': hashlib.sha256(data).hexdigest()}, indent=2))


class HookContractTests(unittest.TestCase):
    def test_hooks_executable_and_empty_project_fails_without_install(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        for leaf in ['rust/tauri', 'swift/macos', 'swift/ios', 'roblox/rojo']:
            for hook in ['pre-commit', 'pre-push']:
                with self.subTest(leaf=leaf, hook=hook):
                    source = ROOT / leaf / '.githooks' / hook
                    self.assertTrue(source.is_file(), 'manual hook missing')
                    self.assertTrue(os.access(source, os.X_OK), 'hook must be executable')
                    project = Path(tempfile.mkdtemp(prefix='empty-', dir=CACHE))
                    shutil.copytree(ROOT / leaf, project, dirs_exist_ok=True)
                    env = os.environ.copy()
                    env.update(HOME=str(project), GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
                    subprocess.run(['git', 'init', '-q', str(project)], env=env, check=True)
                    result = subprocess.run([str(project / '.githooks' / hook)], cwd=project,
                                            env=env, text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_documented_opt_in_preserves_existing_hooks(self):
        for leaf in ['rust/tauri', 'swift/macos', 'swift/ios', 'roblox/rojo']:
            text = (ROOT / leaf / 'README.md').read_text()
            for command in ['git config --show-origin --get-all core.hooksPath',
                            'git rev-parse --git-path hooks',
                            'git config --local core.hooksPath .githooks']:
                self.assertIn(command, text)
            self.assertIn('既存フック', text)
            self.assertIn('別承認', text)

    def test_explicit_check_ref_missing_or_invalid_fails_closed(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        sandbox = Path(tempfile.mkdtemp(prefix='bad-ref-', dir=CACHE))
        (sandbox / 'scripts').mkdir()
        for ref in ['not-a-commit', '0' * 40]:
            with self.subTest(ref=ref), patch.dict(os.environ, {'NATIVE_HOOK_CHECK_REF': ref}):
                with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                    copy_check_script('rust/tauri', sandbox)
        self.assertFalse((sandbox / 'scripts/check.sh').exists())


def exercise_git_gates(test: unittest.TestCase, platform: str, inputs):
    CACHE.mkdir(parents=True, exist_ok=True)
    before = global_hooks_snapshot()
    root, env, source, test_source, bad_format, bad_test = inputs
    sandbox = Path(tempfile.mkdtemp(prefix=platform + '-', dir=CACHE))
    # External Git directory keeps reused Rust crate/source paths and target unchanged.
    (root / 'home').mkdir(exist_ok=True)
    env.update(HOME=str(root / 'home'), GIT_DIR=str(sandbox / 'git'), GIT_WORK_TREE=str(root),
               GIT_CONFIG_GLOBAL=str(sandbox / 'global.gitconfig'), GIT_CONFIG_NOSYSTEM='1',
               GIT_AUTHOR_NAME='Native fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Native fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    (sandbox / 'global.gitconfig').write_text('[core]\n\thooksPath = ' + str(sandbox / 'existing-hooks') + '\n')
    (sandbox / 'existing-hooks').mkdir()
    existing = sandbox / 'existing-hooks/pre-commit'
    existing.write_text('#!/bin/sh\nexit 23\n')
    existing.chmod(0o755)
    existing_hash = hashlib.sha256(existing.read_bytes()).hexdigest()
    (sandbox / 'inputs.json').write_text(json.dumps({
        'fixture': str(root), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'test_sha256': hashlib.sha256(test_source.read_bytes()).hexdigest(),
        'check_sha256': hashlib.sha256((root / 'scripts/check.sh').read_bytes()).hexdigest(),
        'selected_ref': os.environ.get('NATIVE_HOOK_CHECK_REF', 'working-tree'),
        'lock_sha256': hashlib.sha256((root / 'src-tauri/Cargo.lock').read_bytes()).hexdigest() if platform == 'rust' else None,
        'target': env.get('CARGO_TARGET_DIR'),
        'destination': env.get('NATIVE_APP_DESTINATION')}, indent=2))
    receipts = []

    def run(args, success=True):
        result = subprocess.run(['git', *args], cwd=root, env=env, text=True, capture_output=True)
        receipt = {'command': ['git', *args], 'exit': result.returncode,
                   'stdout': result.stdout, 'stderr': result.stderr}
        receipts.append(receipt)
        (sandbox / 'commands.json').write_text(json.dumps(receipts, indent=2))
        if success:
            test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            test.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    original_source, original_test = source.read_bytes(), test_source.read_bytes()
    try:
        run(['init', '-q'])
        run(['add', '--', str(source.relative_to(root)), str(test_source.relative_to(root))])
        # Existing inherited hook is not overwritten; opt-in requires separate permission.
        run(['commit', '-qm', 'existing hook refuses activation'], success=False)
        test.assertEqual(existing.read_text(), '#!/bin/sh\nexit 23\n')
        run(['config', '--local', 'core.hooksPath', str(root / '.githooks')])
        run(['commit', '-qm', 'normal native fixture'])
        head = run(['rev-parse', 'HEAD'])
        remote = sandbox / 'remote.git'
        # Override inherited GIT_DIR only for bare init; no network transport.
        result = subprocess.run(['git', 'init', '--bare', '-q', str(remote)],
                                env={k: v for k, v in env.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE')},
                                text=True, capture_output=True)
        test.assertEqual(result.returncode, 0, result.stderr)
        receipts.append({'command': ['git', 'init', '--bare', '-q', str(remote)], 'exit': result.returncode})
        run(['push', str(remote), 'HEAD:refs/heads/fixture'])
        output = receipts[-1]['stdout'] + receipts[-1]['stderr']
        for stage in ['format', 'lint', 'test', 'build']:
            test.assertIn('stage: ' + stage, output)
        if platform == 'rust':
            test.assertIn('1 passed', output)
        elif platform == 'roblox':
            test.assertIn('1 passed, 0 failed', output)
        else:
            test.assertRegex(output, r'"passedTests"\s*:\s*1')
        def remote_head():
            return run(['ls-remote', str(remote), 'refs/heads/fixture']).split()[0]
        test.assertEqual(remote_head(), head)
        source.write_text(bad_format)
        run(['add', '--', str(source.relative_to(root))])
        run(['commit', '-qm', 'bad format'], success=False)
        output = receipts[-1]['stdout'] + receipts[-1]['stderr']
        test.assertIn('[Spacing]' if platform in ('macos', 'ios') else 'Diff in', output)
        test.assertNotIn('stage: lint', output)
        test.assertEqual(run(['rev-parse', 'HEAD']), head)
        source.write_bytes(original_source)
        run(['add', '--', str(source.relative_to(root))])
        # Formatter-only commit accepts a formatted failing test; full push rejects it.
        test_source.write_text(bad_test)
        run(['add', '--', str(test_source.relative_to(root))])
        run(['commit', '-qm', 'formatted failing test'])
        bad_head = run(['rev-parse', 'HEAD'])
        test.assertNotEqual(bad_head, head)
        run(['push', str(remote), 'HEAD:refs/heads/fixture'], success=False)
        output = receipts[-1]['stdout'] + receipts[-1]['stderr']
        test.assertIn({'rust': 'test result: FAILED', 'roblox': 'FAIL tests/Greeting.spec.luau'}
                      .get(platform, 'FixtureTests.testAddition()'), output)
        test.assertNotIn('stage: build', output)
        test.assertEqual(run(['rev-parse', 'HEAD']), bad_head)
        test.assertEqual(remote_head(), head)
        test_source.write_bytes(original_test)
        run(['add', '--', str(test_source.relative_to(root))])
        run(['commit', '-qm', 'restore normal test'])
        run(['push', str(remote), 'HEAD:refs/heads/fixture'])
        test.assertEqual(remote_head(), run(['rev-parse', 'HEAD']))
    finally:
        source.write_bytes(original_source)
        test_source.write_bytes(original_test)
        after = global_hooks_snapshot()
        (sandbox / 'global-preservation.json').write_text(json.dumps({'before': before, 'after': after}, indent=2))
        test.assertEqual(before, after)
        test.assertEqual(hashlib.sha256(existing.read_bytes()).hexdigest(), existing_hash)

class RustHookTests(unittest.TestCase):
    platform = 'rust'

    def test_real_commit_push_gates_and_global_preservation(self):
        leaf = ROOT / ("rust/tauri" if self.platform == "rust" else "swift/" + self.platform)
        self.assertTrue((leaf / ".githooks/pre-commit").is_file(), "manual hook missing")
        exercise_git_gates(self, self.platform, self.fixture_inputs())

    def fixture_inputs(self):
        from tests.native.rust_helpers import CACHE as RUST_CACHE, LIB_SOURCE, rust_env
        selected = os.environ.get('NATIVE_HOOK_RUST_FIXTURE', '')
        self.assertEqual(selected, 'fixture-50ncrnnd', 'reuse must be explicitly approved; no new Rust target')
        root = RUST_CACHE / selected
        self.assertTrue(root.is_dir())
        self.assertFalse((root / '.git').exists(), 'existing Git ownership: stop')
        self.assertTrue((RUST_CACHE / 'targets' / selected).is_dir())
        # Restore only the approved fixture baseline, retaining its crate path/target.
        for name in ['rust-toolchain.toml', 'rustfmt.toml', '.cargo/config.toml',
                     'src-tauri/Cargo.toml', 'src-tauri/build.rs', 'src-tauri/tauri.conf.json',
                     'src-tauri/capabilities/main.json']:
            data = (ROOT / 'rust/tauri' / name).read_bytes()
            (root / name).write_bytes(data)
        copy_check_script('rust/tauri', root)
        lock = (RUST_CACHE / 'approved-resolution/Cargo.lock').read_bytes()
        (root / 'src-tauri/Cargo.lock').write_bytes(lock)
        source = root / 'src-tauri/src/main.rs'
        tests = root / 'src-tauri/src/lib.rs'
        source.write_text('fn main() {}\n')
        tests.write_text(LIB_SOURCE)
        from tests.native.rust_helpers import run_rust, validate_rust_dependencies
        result = run_rust(['rustup', 'run', '1.92.0', 'cargo', 'metadata', '--offline', '--locked',
                           '--format-version', '1', '--manifest-path', 'src-tauri/Cargo.toml'], root)
        self.assertEqual(result.returncode, 0, result.stderr)
        validate_rust_dependencies(json.loads(result.stdout), root / 'src-tauri/Cargo.lock',
                                   RUST_CACHE / 'approved-resolution')
        shutil.copytree(ROOT / 'rust/tauri/.githooks', root / '.githooks', dirs_exist_ok=True)
        return (root, rust_env(root), source, tests, 'fn main(){println!("bad");}\n',
                LIB_SOURCE.replace('super::add(2, 3), 5', 'super::add(2, 3), 6'))


class MacOSHookTests(unittest.TestCase):
    platform = 'macos'

    def test_real_commit_push_gates_and_global_preservation(self):
        leaf = ROOT / ("rust/tauri" if self.platform == "rust" else "swift/" + self.platform)
        self.assertTrue((leaf / ".githooks/pre-commit").is_file(), "manual hook missing")
        exercise_git_gates(self, self.platform, self.fixture_inputs())

    def fixture_inputs(self):
        from tests.native.swift_helpers import copy_swift_fixture, swift_env
        root = copy_swift_fixture(self.platform)
        copy_check_script('swift/' + self.platform, root)
        env = swift_env(root)
        if self.platform == 'ios':
            self.assertTrue(os.environ.get('NATIVE_IOS_TEST_DESTINATION'), 'approved destination required')
            env['NATIVE_APP_DESTINATION'] = os.environ['NATIVE_IOS_TEST_DESTINATION']
        source = root / 'Sources/App/FixtureApp.swift'
        tests = root / 'Sources/AppTests/FixtureTests.swift'
        return (root, env, source, tests,
                'import SwiftUI\n@main struct FixtureApp: App{var body: some Scene{WindowGroup{Text("Hi")}}}\n',
                tests.read_text().replace('XCTAssertEqual(2 + 2, 4)', 'XCTAssertEqual(2 + 2, 5)'))


class IOSHookTests(MacOSHookTests):
    platform = 'ios'


class RobloxHookTests(unittest.TestCase):
    platform = 'roblox'

    def test_real_commit_push_gates_and_global_preservation(self):
        self.assertTrue((ROOT / 'roblox/rojo/.githooks/pre-commit').is_file(), 'manual hook missing')
        exercise_git_gates(self, self.platform, self.fixture_inputs())

    def fixture_inputs(self):
        from tests.native.roblox_helpers import GREETING_SPEC, copy_fixture, roblox_env
        root = copy_fixture('hooks')
        copy_check_script('roblox/rojo', root)
        source = root / 'src/shared/Greeting.luau'
        tests = root / 'tests/Greeting.spec.luau'
        return (root, roblox_env(root), source, tests, 'local Greeting={}\nreturn Greeting\n',
                GREETING_SPEC.replace('"Hello, Roblox!"', '"Bye"'))


if __name__ == '__main__':
    unittest.main()
