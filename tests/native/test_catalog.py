"""Catch broken catalog paths, incomplete copies and accidental product distribution."""
import json
import re
import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUST_FILES = {'README.md', 'LICENSE', 'rust-toolchain.toml', 'rustfmt.toml',
              '.editorconfig', '.gitignore', '.cargo/config.toml', 'scripts/check.sh',
              'scripts/check.ps1', 'src-tauri/Cargo.toml', 'src-tauri/build.rs',
              'src-tauri/tauri.conf.json', 'src-tauri/capabilities/main.json',
              '.githooks/pre-commit', '.githooks/pre-push'}
SWIFT_FILES = {'README.md', 'LICENSE', '.swift-format', '.swiftlint.yml',
               '.editorconfig', '.gitignore', 'Config/Quality.xcconfig',
               'Config/Debug.xcconfig', 'Config/Release.xcconfig',
               'Config/VerifyUnsigned.xcconfig', 'scripts/check.sh',
               '.githooks/pre-commit', '.githooks/pre-push'}
ROBLOX_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', 'rokit.toml',
                'default.project.json', 'wally.toml', 'stylua.toml', 'selene.toml', '.luaurc',
                'src/server/.gitkeep', 'src/client/.gitkeep', 'src/shared/.gitkeep',
                'tests/.gitkeep', 'scripts/check.sh', 'scripts/test.luau',
                '.githooks/pre-commit', '.githooks/pre-push'}
GODOT_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', '.gitattributes',
               'project.godot', 'gdlintrc', 'gdformatrc', 'src/.gitkeep', 'tests/.gitkeep',
               'scripts/check.sh', 'scripts/test_runner.gd', 'scripts/test_context.gd',
               '.githooks/pre-commit', '.githooks/pre-push'}
BLENDER_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', 'pyproject.toml',
                 'models/.gitkeep', 'tests/.gitkeep', 'scripts/check.sh', 'scripts/build.py',
                 'scripts/test.py', '.githooks/pre-commit', '.githooks/pre-push'}


def links(path):
    return [link.split('#')[0] for link in re.findall(r'\]\(([^)]+)\)', path.read_text())
            if '://' not in link and not link.startswith('#')]


class CatalogTests(unittest.TestCase):
    def test_root_language_leaf_navigation(self):
        for language, leaves in [('rust', ['tauri']), ('swift', ['macos', 'ios']),
                                 ('roblox', ['rojo']), ('godot', ['mobile']),
                                 ('blender', ['assets'])]:
            self.assertIn(f'./{language}/README.md', links(ROOT / 'README.md'))
            for leaf in leaves:
                self.assertIn(f'{leaf}/README.md', links(ROOT / language / 'README.md'))
                self.assertTrue((ROOT / language / leaf / 'README.md').is_file())

    def test_independent_copy_exact_inventory_and_local_references(self):
        cache = ROOT / '.verification/native/catalog'
        cache.mkdir(parents=True, exist_ok=True)
        for name, expected in [('rust/tauri', RUST_FILES), ('swift/macos', SWIFT_FILES),
                               ('swift/ios', SWIFT_FILES), ('roblox/rojo', ROBLOX_FILES),
                               ('godot/mobile', GODOT_FILES), ('blender/assets', BLENDER_FILES)]:
            with self.subTest(leaf=name):
                source = ROOT / name
                actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
                self.assertEqual(actual, expected, 'unlisted or forbidden distribution file')
                self.assertFalse(any(p.is_symlink() for p in source.rglob('*')))
                dest = Path(tempfile.mkdtemp(prefix='copy-', dir=cache)) / 'project'
                shutil.copytree(source, dest)
                listed = set(links(dest / 'README.md'))
                self.assertTrue((expected - {'README.md'}).issubset(listed), expected - listed)
                for link in listed:
                    path = (dest / link).resolve()
                    self.assertTrue(path.is_relative_to(dest.resolve()), link)
                    self.assertTrue(path.is_file(), link)
                for config in dest.rglob('*.xcconfig'):
                    for include in re.findall(r'#include "([^"]+)"', config.read_text()):
                        path = (config.parent / include).resolve()
                        self.assertTrue(path.is_relative_to(dest.resolve()))
                        self.assertTrue(path.is_file())
                for hook in ['pre-commit', 'pre-push']:
                    self.assertIn('scripts/check.sh', (dest / '.githooks' / hook).read_text())
                    self.assertTrue((dest / 'scripts/check.sh').is_file())

    def test_explicit_nonempty_suites_preserve_typescript_entry(self):
        scripts = json.loads((ROOT / 'package.json').read_text())['scripts']
        self.assertEqual(scripts['test'], 'node --version && pnpm test:static && pnpm test:integration')
        for name, module in [('static', 'test_catalog'), ('rust', 'test_rust'),
                             ('macos', 'test_swift_macos'), ('ios', 'test_swift_ios'),
                             ('roblox', 'test_roblox')]:
            self.assertIn(f'test:native:{name}', scripts)
            self.assertIn(module, scripts[f'test:native:{name}'])
            self.assertNotIn('discover', scripts[f'test:native:{name}'])
            self.assertIn('tests.native.test_catalog', scripts[f'test:native:{name}'])
        self.assertIn('test_static_roblox', scripts['test:native:static'])
        self.assertIn('test_static_godot', scripts['test:native:static'])
        self.assertIn('test_static_blender', scripts['test:native:static'])


class CatalogRunnerTests(unittest.TestCase):
    def test_count_guard_rejects_empty_missing_failed_and_invalid_suites(self):
        self.assertTrue(callable(globals().get('run_native_suites')), 'count-guard runner missing')
        cache = ROOT / '.verification/native/catalog'
        cache.mkdir(parents=True, exist_ok=True)
        sandbox = Path(tempfile.mkdtemp(prefix='runner-', dir=cache))
        (sandbox / 'native_runner_cases.py').write_text(
            'import unittest\nclass Passing(unittest.TestCase):\n'
            '    def test_real(self): self.assertEqual(2 + 2, 4)\n'
            'class Failing(unittest.TestCase):\n'
            '    def test_real(self): self.assertEqual(2 + 2, 5)\n')
        env = os.environ.copy()
        env['PYTHONPATH'] = str(sandbox)
        for names, success, diagnostic in [
            ([], False, 'explicit suite names required'),
            (['bad/name'], False, 'invalid suite name'),
            (['unittest'], False, 'no tests discovered'),
            (['native_runner_cases.Passing', 'unittest'], False, 'no tests discovered'),
            (['tests.native.missing'], False, 'FAILED'),
            (['native_runner_cases.Failing'], False, 'FAILED'),
            (['native_runner_cases.Passing'], True, 'Ran 1 test')]:
            with self.subTest(names=names):
                result = subprocess.run([sys.executable, '-m', 'tests.native.test_catalog', *names],
                                        cwd=ROOT, env=env, text=True, capture_output=True)
                (sandbox / (str(len(list(sandbox.glob('*.log')))) + '.log')).write_text(
                    f'command={names!r}\nexit={result.returncode}\n{result.stdout}\n{result.stderr}')
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                self.assertIn(diagnostic, result.stdout + result.stderr)


def run_native_suites(names):
    if not names:
        raise SystemExit('explicit suite names required')
    suites = []
    for name in names:
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', name):
            raise SystemExit(f'invalid suite name: {name}')
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
        if suite.countTestCases() == 0:
            raise SystemExit(f'no tests discovered: {name}')
        suites.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(run_native_suites(sys.argv[1:]))
