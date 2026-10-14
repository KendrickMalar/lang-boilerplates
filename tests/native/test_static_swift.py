"""Distribution boundaries for the self-contained Swift settings leaves."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class StaticSwiftTests(unittest.TestCase):
    def test_each_leaf_links_and_includes_are_local(self):
        for platform in ['macos', 'ios']:
            with self.subTest(platform=platform):
                self.check_leaf(ROOT / 'swift' / platform)

    def check_leaf(self, leaf):
        expected = ['README.md', 'LICENSE', '.swift-format', '.swiftlint.yml',
                    '.editorconfig', '.gitignore', 'Config/Quality.xcconfig',
                    'Config/Debug.xcconfig', 'Config/Release.xcconfig',
                    'Config/VerifyUnsigned.xcconfig', 'scripts/check.sh']
        for name in expected:
            self.assertTrue((leaf / name).is_file(), name)
        for link in re.findall(r'\]\(([^)]+)\)', (leaf / 'README.md').read_text()):
            if '://' not in link and not link.startswith('#'):
                path = (leaf / link.split('#')[0]).resolve()
                self.assertTrue(path.is_relative_to(leaf.resolve()), link)
                self.assertTrue(path.exists(), link)
        for config in (leaf / 'Config').glob('*.xcconfig'):
            for include in re.findall(r'#include "([^"]+)"', config.read_text()):
                path = (config.parent / include).resolve()
                self.assertTrue(path.is_relative_to(leaf.resolve()))
                self.assertTrue(path.is_file())
        self.assertFalse(list(leaf.rglob('*.swift')))
        self.assertFalse(list(leaf.rglob('*.xcodeproj')))
        fmt = json.loads((leaf / '.swift-format').read_text())
        self.assertEqual(fmt['indentation'], {'spaces': 4})
        self.assertEqual(fmt['lineLength'], 100)

    def test_ios_deployment_and_family(self):
        path = ROOT / 'swift/ios/Config/Quality.xcconfig'
        self.assertTrue(path.is_file(), 'iOS Quality.xcconfig missing')
        config = path.read_text()
        for setting in ['SWIFT_VERSION = 6', 'SWIFT_TREAT_WARNINGS_AS_ERRORS = YES',
                        'IPHONEOS_DEPLOYMENT_TARGET = 17.0', 'TARGETED_DEVICE_FAMILY = 1,2']:
            self.assertIn(setting, config)
        self.assertNotIn('MACOSX_DEPLOYMENT_TARGET', config)
        self.assertNotIn('SWIFT_DEFAULT_ACTOR_ISOLATION', config)

    def test_mode_warning_and_deployment_settings(self):
        path = ROOT / 'swift/macos/Config/Quality.xcconfig'
        self.assertTrue(path.is_file(), 'Quality.xcconfig missing')
        config = path.read_text()
        for setting in ['SWIFT_VERSION = 6', 'SWIFT_TREAT_WARNINGS_AS_ERRORS = YES',
                        'MACOSX_DEPLOYMENT_TARGET = 15.0']:
            self.assertIn(setting, config)
        self.assertNotIn('SWIFT_DEFAULT_ACTOR_ISOLATION', config)
        lint = (ROOT / 'swift/macos/.swiftlint.yml').read_text()
        for rule in ['empty_count', 'contains_over_first_not_nil', 'force_unwrapping']:
            self.assertIn(rule, lint)
        disabled = lint.split('disabled_rules:\n', 1)[1].split('excluded:', 1)[0]
        self.assertEqual(re.findall(r'^  - (\w+)$', disabled, re.MULTILINE),
                         ['trailing_comma', 'line_length'])


if __name__ == '__main__':
    unittest.main()
