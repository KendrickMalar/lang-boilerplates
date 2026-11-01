"""Shared architecture enforcement cases; concrete classes live in the platform suites.

Each case edits a generated fixture (outside the leaf) and runs the copied
`scripts/check.sh architecture`, so the leaf files themselves are what is tested.
"""
import importlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


def with_import(text, module):
    """Add an import while keeping swift-format's lexicographic import order."""
    lines = text.splitlines(keepends=True)
    count = next((i for i, line in enumerate(lines) if not line.startswith('import ')), len(lines))
    imports = sorted(lines[:count] + [f'import {module}\n'])
    separator = [] if count or not lines else ['\n']
    return ''.join(imports + separator + lines[count:])


class ArchitectureCaseBase:
    platform = 'macos'
    option = 'thin-app-packages'
    ui_framework = 'AppKit'
    fixtures: dict = {}

    def setUp(self):
        self.helper = importlib.import_module('swift_helpers')
        key = (type(self).__name__, self.platform, self.option)
        if key not in ArchitectureCaseBase.fixtures:
            ArchitectureCaseBase.fixtures[key] = self.helper.copy_architecture_fixture(
                self.platform, self.option)
        self.root = ArchitectureCaseBase.fixtures[key]

    def architecture_env(self):
        env = {'NATIVE_APP_ARCHITECTURE': self.option}
        if self.option == 'thin-app-packages':
            env['NATIVE_APP_PACKAGE_DIR'] = 'Modules'
        if self.platform == 'ios':
            env['NATIVE_APP_DESTINATION'] = os.environ.get('NATIVE_IOS_TEST_DESTINATION', '')
        return env

    def run_check(self, stage='architecture', *, success=True, contains=None, env=None):
        values = self.architecture_env()
        values.update(env or {})
        # '' means unset: check.sh treats empty as missing, and swift_env keeps it.
        with patch.dict(os.environ, {k: '' if v is None else v for k, v in values.items()}):
            result = self.helper.run_swift(['sh', 'scripts/check.sh', stage], self.root)
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output[-12000:])
        else:
            self.assertNotEqual(result.returncode, 0, output[-12000:])
        if contains:
            self.assertIn(contains, output)
        return output

    @contextmanager
    def change(self, relative, text):
        path = self.root / relative
        existed = path.exists()
        original = path.read_bytes() if existed else b''
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        try:
            yield
        finally:
            if existed:
                path.write_bytes(original)
            else:
                path.unlink()

    def test_selection_and_rule_presence_required(self):
        for stage in ['architecture', 'all']:
            with self.subTest(stage=stage):
                output = self.run_check(stage, env={'NATIVE_APP_ARCHITECTURE': None}, success=False,
                                        contains='missing NATIVE_APP_ARCHITECTURE')
                self.assertIn('README アーキテクチャ', output)
                self.assertIn('check-architecture.sh', output)
                self.assertNotIn('stage: ', output)
        output = self.run_check('all', env={'NATIVE_APP_ARCHITECTURE': 'tca'}, success=False,
                                contains='unknown architecture')
        self.assertNotIn('stage: ', output)
        self.run_check(env={'NATIVE_APP_ARCHITECTURE': 'tca'}, success=False,
                       contains='unknown architecture')
        other = 'single-target' if self.option == 'thin-app-packages' else 'thin-app-packages'
        self.run_check(env={'NATIVE_APP_ARCHITECTURE': other, 'NATIVE_APP_PACKAGE_DIR': 'Modules'},
                       success=False, contains='check-architecture.sh is for')
        lint = (self.root / '.swiftlint.yml').read_text()
        stripped = re.sub(r'\ncustom_rules:\n(?:  .*\n|\n)*', '\n', lint)
        self.assertNotEqual(lint, stripped)
        with self.change('.swiftlint.yml', stripped):
            self.run_check(success=False, contains='missing SwiftLint architecture rule')
        with self.change('scripts/check-architecture.sh', ''):
            self.run_check(success=False, contains='check-architecture.sh')


class ThinAppPackagesCases(ArchitectureCaseBase):
    option = 'thin-app-packages'
    core = 'Modules/Sources/Core/Item.swift'
    home = 'Modules/Sources/Features/Home/HomeView.swift'
    client = 'Modules/Sources/Clients/ItemClient.swift'
    core_test = 'Modules/Tests/CoreTests/ItemTests.swift'

    def read(self, relative):
        return (self.root / relative).read_text()

    def test_compliant_package_passes(self):
        output = self.run_check()
        self.assertIn('stage: architecture', output)
        self.assertIn('architecture: thin-app-packages', output)
        self.assertIn('architecture: clean package build', output)

    def test_all_runs_architecture_before_settings(self):
        output = self.run_check('all')
        stages = re.findall(r'^stage: (\w+)$', output, re.MULTILINE)
        self.assertEqual(stages, ['format', 'lint', 'architecture', 'settings', 'test', 'build'])

    def test_core_ui_and_persistence_imports_rejected(self):
        for module in ['SwiftUI', self.ui_framework, 'SwiftData']:
            with self.subTest(module=module), self.change(self.core, with_import(self.read(self.core), module)):
                self.run_check(success=False, contains='arch_core_pure_swift')

    def test_core_importing_feature_or_client_rejected(self):
        for module in ['HomeFeature', 'Clients']:
            with self.subTest(module=module), self.change(self.core, with_import(self.read(self.core), module)):
                self.run_check(success=False, contains='arch_core_pure_swift')

    def test_feature_importing_feature_or_client_rejected(self):
        for module in ['SettingsFeature', 'Clients']:
            with self.subTest(module=module), self.change(self.home, with_import(self.read(self.home), module)):
                self.run_check(success=False, contains='arch_feature_isolation')

    def test_client_importing_feature_rejected(self):
        with self.change(self.client, with_import(self.read(self.client), 'HomeFeature')):
            self.run_check(success=False, contains='arch_clients_no_features')

    def test_declared_forbidden_manifest_edges_rejected(self):
        manifest = 'Modules/Package.swift'
        original = self.read(manifest)
        for old, new, diagnostic in [
            ('dependencies: ["Core"], path: "Sources/Features/Home"',
             'dependencies: ["Core", "SettingsFeature"], path: "Sources/Features/Home"', 'HomeFeature'),
            ('.target(name: "Clients", dependencies: ["Core"])',
             '.target(name: "Clients", dependencies: ["Core", "HomeFeature"])', 'Clients'),
            ('.target(name: "Core")', '.target(name: "Core", dependencies: ["Clients"])', 'Core'),
        ]:
            self.assertIn(old, original)
            with self.subTest(edge=new), self.change(manifest, original.replace(old, new)):
                self.run_check(success=False, contains=f'architecture violation: {diagnostic}')
        unknown = original.replace('.target(name: "Core"),', '.target(name: "Core"),\n        .target(name: "Shared"),')
        with self.change(manifest, unknown), self.change('Modules/Sources/Shared/Shared.swift', 'public enum Shared {}\n'):
            self.run_check(success=False, contains='architecture violation: Shared')

    def test_undeclared_target_import_rejected_after_successful_build(self):
        # A previous successful build leaves HomeFeature modules behind; the check
        # must still fail because every invocation uses a new build directory.
        self.run_check()
        importing = self.read(self.core_test).replace(
            'import Core\n', 'import Core\nimport HomeFeature\n').replace(
            '        XCTAssertEqual(Item(name: "a").name, "a")\n',
            '        XCTAssertEqual(Item(name: "a").name, "a")\n        _ = HomeView(items: [])\n')
        with self.change(self.core_test, importing):
            for _ in range(2):
                output = self.run_check(success=False)
                self.assertIn('architecture: clean package build', output)
                self.assertRegex(output, r"(?i)(unable to resolve module dependency|no such module): 'HomeFeature'")

    def test_package_dir_validation(self):
        for value, diagnostic in [(None, 'NATIVE_APP_PACKAGE_DIR'), ('../outside', 'package'),
                                  ('Missing', 'Package.swift')]:
            with self.subTest(value=value):
                self.run_check(env={'NATIVE_APP_PACKAGE_DIR': value}, success=False, contains=diagnostic)


class SingleTargetCases(ArchitectureCaseBase):
    option = 'single-target'
    model = 'Sources/App/Models/Item.swift'
    service = 'Sources/App/Services/ItemService.swift'

    def test_compliant_folders_pass(self):
        commented = '// import SwiftUI is forbidden here.\n' + (self.root / self.model).read_text()
        with self.change(self.model, commented):
            output = self.run_check()
            self.assertIn('architecture: single-target', output)
            self.run_check('lint')

    def test_model_ui_import_rejected_in_architecture_and_lint(self):
        original = (self.root / self.model).read_text()
        for module in ['SwiftUI', self.ui_framework]:
            with self.subTest(module=module), self.change(self.model, with_import(original, module)):
                self.run_check(success=False, contains='arch_models_no_ui')
                self.run_check('lint', success=False, contains='arch_models_no_ui')

    def test_service_ui_import_rejected(self):
        original = (self.root / self.service).read_text()
        with self.change(self.service, with_import(original, 'SwiftUI')):
            self.run_check(success=False, contains='arch_services_no_ui')


__all__ = ['ThinAppPackagesCases', 'SingleTargetCases', 'Path']
