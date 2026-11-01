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


class StaticSwiftArchitectureTests(unittest.TestCase):
    UI = {'macos': 'AppKit', 'ios': 'UIKit'}
    OTHER_UI = {'macos': 'UIKit', 'ios': 'AppKit'}

    def section(self, platform):
        readme = (ROOT / 'swift' / platform / 'README.md').read_text()
        self.assertIn('\n## アーキテクチャ\n', readme)
        return readme.split('\n## アーキテクチャ\n', 1)[1].split('\n## ', 1)[0]

    def test_readme_section_shape_and_order(self):
        for platform in ['macos', 'ios']:
            with self.subTest(platform=platform):
                section = self.section(platform)
                headings = re.findall(r'^### (.+)$', section, re.MULTILINE)
                self.assertEqual(headings, ['選び方', '薄いアプリ＋ローカルパッケージ（既定）',
                                            '1ターゲット＋フォルダ規則'])
                self.assertIn('scaffold', section.split('### ', 1)[0])
                for option, name in [('thin-app-packages', '薄いアプリ＋ローカルパッケージ（既定）'),
                                     ('single-target', '1ターゲット＋フォルダ規則')]:
                    body = section.split(f'### {name}\n', 1)[1].split('\n### ', 1)[0]
                    self.assertIn('```mermaid\nflowchart', body)
                    self.assertIn('| 規則 | MUST／MUST NOT |', body)
                    self.assertIn('向く', body)
                    self.assertIn('向かない', body)
                    self.assertIn(f'architecture/{option}/check-architecture.sh', body)
                    self.assertIn(f'architecture/{option}/swiftlint-rules.yml', body)
                    self.assertIn(f'NATIVE_APP_ARCHITECTURE={option}', body)
                    self.assertIn(self.UI[platform], body)

    def test_option_files_are_self_contained_and_platform_specific(self):
        for platform in ['macos', 'ios']:
            leaf = ROOT / 'swift' / platform / 'architecture'
            with self.subTest(platform=platform):
                manifest = (leaf / 'thin-app-packages/Package.swift.example').read_text()
                self.assertIn('// swift-tools-version: 6.', manifest)
                platform_decl = '.macOS(.v15)' if platform == 'macos' else '.iOS(.v17)'
                self.assertIn(platform_decl, manifest)
                self.assertIn('.target(name: "Core")', manifest)
                for name in ['Clients', 'HomeFeature', 'SettingsFeature']:
                    self.assertIn(f'.target(name: "{name}", dependencies: ["Core"]', manifest)
                thin = (leaf / 'thin-app-packages/swiftlint-rules.yml').read_text()
                single = (leaf / 'single-target/swiftlint-rules.yml').read_text()
                for text, rules in [(thin, ['arch_core_pure_swift', 'arch_feature_isolation',
                                            'arch_clients_no_features']),
                                    (single, ['arch_models_no_ui', 'arch_services_no_ui'])]:
                    self.assertTrue(text.startswith('custom_rules:\n'))
                    for rule in rules:
                        self.assertIn(f'\n  {rule}:\n', text)
                    self.assertEqual(text.count('severity: error'), len(rules))
                    self.assertIn(self.UI[platform], text)
                    self.assertNotIn(self.OTHER_UI[platform], text)
                for option in ['thin-app-packages', 'single-target']:
                    script = (leaf / option / 'check-architecture.sh').read_text()
                    self.assertIn(f"expected_architecture={option}", script)
                    self.assertNotIn('../', script)
                self.assertIn('"$swift" build' if platform == 'macos' else 'generic/platform=iOS Simulator',
                              (leaf / 'thin-app-packages/check-architecture.sh').read_text())

    def test_check_supports_architecture_stage(self):
        for platform in ['macos', 'ios']:
            with self.subTest(platform=platform):
                check = (ROOT / 'swift' / platform / 'scripts/check.sh').read_text()
                self.assertIn('format|lint|architecture|settings|test|build|all', check)
                self.assertIn('for next in format lint architecture settings test build', check)
                self.assertIn('NATIVE_APP_ARCHITECTURE', check)
                self.assertNotIn('not selected', check)
                self.assertIn('missing NATIVE_APP_ARCHITECTURE', check)


if __name__ == '__main__':
    unittest.main()
