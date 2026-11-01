"""Real Xcode app tests, not SwiftPM or mocked build commands."""
import importlib
import os
import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from swift_architecture_cases import SingleTargetCases, ThinAppPackagesCases


class MacOSSwiftTests(unittest.TestCase):
    fixture: Path | None = None
    def setUp(self):
        self.assertTrue(Path(__file__).with_name('swift_helpers.py').is_file(),
                        'Swift fixture helper missing')
        self.helper = importlib.import_module('swift_helpers')
        if type(self).fixture is None:
            type(self).fixture = self.helper.copy_swift_fixture('macos')
        assert self.fixture is not None
        self.root = self.fixture

    def run_check(self, stage='all', *, success=True, contains=None):
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
        original = path.read_bytes()
        path.write_text(text)
        try:
            yield
        finally:
            path.write_bytes(original)

    def test_clean_macos_app(self):
        output = self.run_check()
        for stage in ['format', 'lint', 'settings', 'test', 'build']:
            self.assertIn(f'stage: {stage}', output)
        self.assertRegex(output, r'"passedTests"\s*:\s*1')

    def test_mode_warning_and_deployment_settings(self):
        self.run_check('settings')
        for key, value in [('SWIFT_VERSION', '5'),
                           ('SWIFT_TREAT_WARNINGS_AS_ERRORS', 'NO'),
                           ('MACOSX_DEPLOYMENT_TARGET', '14.0')]:
            with self.change('Config/Quality.xcconfig', f'{key} = {value}\n'):
                self.run_check('settings', success=False, contains='quality mismatch')

    def test_quality_unconnected_rejected(self):
        project = self.root / 'Fixture.xcodeproj/project.pbxproj'
        with self.change(str(project.relative_to(self.root)),
                         re.sub(r'baseConfigurationReference = [A-F0-9]+;', '', project.read_text())):
            self.run_check('settings', success=False, contains='quality mismatch')

    def test_bad_format_lint_actor_and_test_rejected(self):
        app = 'Sources/App/FixtureApp.swift'
        with self.change(app, 'import SwiftUI\n@main struct FixtureApp: App{var body: some Scene{WindowGroup{Text("Hi")}}}\n'):
            output = self.run_check(success=False)
            self.assertIn('stage: format', output)
            self.assertNotIn('stage: lint', output)
        with self.change(app, (self.root / app).read_text() + '\nfunc unwrap(_ value: Int?) -> Int {\n    return value!\n}\n'):
            output = self.run_check(success=False, contains='Force Unwrapping')
            self.assertNotIn('stage: test', output)
        with self.change(app, (self.root / app).read_text() + '\n@MainActor\nfunc isolated() {}\n\nfunc unsafe() {\n    isolated()\n}\n'):
            output = self.run_check(success=False, contains='main actor-isolated')
            self.assertIn('stage: test', output)
            self.assertNotIn('stage: build', output)
        tests = 'Sources/AppTests/FixtureTests.swift'
        with self.change(tests, (self.root / tests).read_text().replace('XCTAssertEqual(2 + 2, 4)', 'XCTAssertEqual(2 + 2, 5)')):
            output = self.run_check(success=False, contains='failed')
            self.assertNotIn('stage: build', output)

    def test_missing_tool_source_project_scheme_test_rejected(self):
        for key, value, diagnostic in [
            ('SWIFTLINT_BIN', '/missing/swiftlint', 'SwiftLint'),
            ('DEVELOPER_DIR', '/missing/Xcode', 'DEVELOPER_DIR'),
            ('NATIVE_APP_PROJECT', 'Missing.xcodeproj', 'project'),
            ('NATIVE_APP_PROJECT', '../outside.xcodeproj', 'project'),
            ('NATIVE_APP_SOURCE_DIR', '../', 'source'),
            ('NATIVE_APP_SCHEME', '', 'scheme'),
            ('NATIVE_APP_SCHEME', 'Missing', 'scheme'),
            ('NATIVE_APP_DESTINATION', '', 'destination'),
            ('NATIVE_APP_DESTINATION', 'generic/platform=iOS', 'destination'),
        ]:
            with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                self.run_check(success=False, contains=diagnostic)
        with self.change('Sources/App/FixtureApp.swift', ''), self.change('Sources/AppTests/FixtureTests.swift', ''):
            self.run_check(success=False, contains='empty Swift source')
        with self.change('Sources/AppTests/FixtureTests.swift', 'import XCTest\nfinal class FixtureTests: XCTestCase {}\n'):
            self.run_check('test', success=False)

    def test_skipped_only_test_rejected(self):
        with self.change('Sources/AppTests/FixtureTests.swift',
                         'import XCTest\nfinal class FixtureTests: XCTestCase {\n    func testSkipped() throws { throw XCTSkip("fixture") }\n}\n'):
            self.run_check('test', success=False, contains='no passing tests')

    def test_minimum_tool_and_unsigned_guard(self):
        # An executable old-version tool must fail before lint/build; not a missing-tool test.
        tool = self.root / 'old-swiftlint'
        tool.write_text('#!/bin/sh\nprintf "0.64.0\\n"\n')
        tool.chmod(0o755)
        with patch.dict(os.environ, {'SWIFTLINT_BIN': str(tool)}):
            self.run_check(success=False, contains='requires SwiftLint 0.65.1')
        with self.change('.native-app-fixture', 'not approved\n'):
            self.run_check('build', success=False, contains='fixture-only')

    def test_remote_package_missing_lock_rejected(self):
        project = 'Fixture.xcodeproj/project.pbxproj'
        original = (self.root / project).read_text()
        # A valid project object, rejected before Xcode can resolve/fetch anything.
        record = ('ABABABABABABABABABABABAB = { isa = XCRemoteSwiftPackageReference; '
                  'repositoryURL = "https://example.invalid/not-approved"; '
                  'requirement = { kind = exactVersion; version = 1.0.0; }; };')
        with self.change(project, original.replace('objects = {', 'objects = {\n' + record)):
            self.run_check(success=False, contains='missing Package.resolved')

    def test_bad_syntax_and_opt_in_rules_rejected(self):
        app = 'Sources/App/FixtureApp.swift'
        with self.change(app, 'import SwiftUI\nstruct Broken {\n'):
            self.run_check('format', success=False, contains='error:')
        for source, rule in [
            ('func nonempty(_ values: [Int]) -> Bool {\n    return values.count > 0\n}\n', 'empty_count'),
            ('func findsOne(_ values: [Int]) -> Bool {\n    return values.first(where: { $0 == 1 }) != nil\n}\n', 'contains_over_first_not_nil'),
        ]:
            with self.subTest(rule=rule), self.change(app, (self.root / app).read_text() + '\n' + source):
                self.run_check('lint', success=False, contains=rule)

    def test_permission_denied_tool_rejected(self):
        tool = self.root / 'nonexecutable-swiftlint'
        tool.write_text('not executable\n')
        tool.chmod(0o600)
        with patch.dict(os.environ, {'SWIFTLINT_BIN': str(tool)}):
            self.run_check(success=False, contains='SwiftLint')


class MacOSThinAppPackagesTests(ThinAppPackagesCases, unittest.TestCase):
    platform = 'macos'
    ui_framework = 'AppKit'


class MacOSSingleTargetTests(SingleTargetCases, unittest.TestCase):
    platform = 'macos'
    ui_framework = 'AppKit'


if __name__ == '__main__':
    unittest.main()
