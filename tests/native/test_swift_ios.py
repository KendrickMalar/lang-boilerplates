"""iOS Simulator app acceptance; caller supplies an explicitly approved device ID."""
import importlib
import json
import os
import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from swift_architecture_cases import SingleTargetCases, ThinAppPackagesCases


class IOSSwiftTests(unittest.TestCase):
    fixture: Path | None = None
    def setUp(self):
        self.assertTrue(Path(__file__).with_name('swift_helpers.py').is_file(),
                        'Swift fixture helper missing')
        self.helper = importlib.import_module('swift_helpers')
        if type(self).fixture is None:
            type(self).fixture = self.helper.copy_swift_fixture('ios')
        assert self.fixture is not None
        self.root = self.fixture

    def run_check(self, stage='all', *, success=True, contains=None):
        destination = os.environ.get('NATIVE_IOS_TEST_DESTINATION', '')
        with patch.dict(os.environ, {'NATIVE_APP_DESTINATION': destination}):
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

    def test_ios_clean_app_test_and_build(self):
        output = self.run_check()
        for stage in ['format', 'lint', 'settings', 'test', 'build']:
            self.assertIn(f'stage: {stage}', output)
        invocation = Path(re.search(r'artifacts: (.+)', output)[1])
        summary = json.loads((invocation / 'test-summary.json').read_text())
        self.assertEqual(summary['totalTestCount'], 1)
        self.assertEqual(summary['passedTests'], 1)
        self.assertEqual(summary['failedTests'], 0)
        identifier = os.environ['NATIVE_IOS_TEST_DESTINATION'].split('id=')[1]
        records = summary['devicesAndConfigurations']
        self.assertTrue(records, 'actual test destination missing')
        runtimes = {r['identifier']: r for r in json.loads((invocation / 'runtimes.json').read_text())['runtimes']}
        devices = json.loads((invocation / 'devices.json').read_text())['devices']
        runtime = next(runtimes[key] for key, values in devices.items()
                       if any(device['udid'] == identifier for device in values))
        for record in records:
            device = record['device']
            self.assertEqual(device['deviceId'], identifier)
            self.assertEqual(device['platform'], 'iOS Simulator')
            self.assertEqual(device['osVersion'], runtime['version'])
            self.assertEqual(device['osBuildNumber'], runtime['buildversion'])

    def test_mode_warning_and_deployment_settings(self):
        self.run_check('settings')
        for key, value in [('SWIFT_VERSION', '5'),
                           ('SWIFT_TREAT_WARNINGS_AS_ERRORS', 'NO'),
                           ('IPHONEOS_DEPLOYMENT_TARGET', '16.0'),
                           ('TARGETED_DEVICE_FAMILY', '1')]:
            original = (self.root / 'Config/Quality.xcconfig').read_text()
            changed = re.sub(rf'^{key} = .*$', f'{key} = {value}', original, flags=re.MULTILINE)
            with self.change('Config/Quality.xcconfig', changed):
                self.run_check('settings', success=False, contains='quality mismatch')

    def test_ios_quality_is_connected(self):
        project = self.root / 'Fixture.xcodeproj/project.pbxproj'
        with self.change(str(project.relative_to(self.root)),
                         re.sub(r'baseConfigurationReference = [A-F0-9]+;', '', project.read_text())):
            self.run_check('settings', success=False, contains='quality mismatch')

    def test_ios_actor_and_test_failure_rejected(self):
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
        ]:
            with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                self.run_check(success=False, contains=diagnostic)
        with self.change('Sources/App/FixtureApp.swift', ''), self.change('Sources/AppTests/FixtureTests.swift', ''):
            self.run_check(success=False, contains='empty Swift source')
        with self.change('Sources/AppTests/FixtureTests.swift', 'import XCTest\nfinal class FixtureTests: XCTestCase {}\n'):
            self.run_check('test', success=False)

    def test_missing_or_wrong_destination_rejected(self):
        for destination in ['', 'generic/platform=iOS Simulator', 'platform=macOS',
                            'platform=iOS,id=00000000-0000-0000-0000-000000000000',
                            'platform=iOS Simulator,id=00000000-0000-0000-0000-000000000000']:
            with self.subTest(destination=destination), patch.dict(os.environ, {'NATIVE_IOS_TEST_DESTINATION': destination}):
                self.run_check(success=False, contains='destination')

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


class IOSThinAppPackagesTests(ThinAppPackagesCases, unittest.TestCase):
    platform = 'ios'
    ui_framework = 'UIKit'


class IOSSingleTargetTests(SingleTargetCases, unittest.TestCase):
    platform = 'ios'
    ui_framework = 'UIKit'


if __name__ == '__main__':
    unittest.main()
