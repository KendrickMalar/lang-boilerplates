"""Standard Xcode fixtures in Git-ignored storage; never distributed app source."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.verification/native/swift'
APP_SOURCE = '''import SwiftUI

@main
struct FixtureApp: App {
    var body: some Scene {
        WindowGroup {
            Text("Fixture")
        }
    }
}
'''
TEST_SOURCE = '''import XCTest

final class FixtureTests: XCTestCase {
    func testAddition() {
        XCTAssertEqual(2 + 2, 4)
    }
}
'''


def swift_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    defaults = {
        'DEVELOPER_DIR': '/Applications/Xcode.app/Contents/Developer',
        'SWIFTLINT_BIN': str(CACHE / 'tools/swiftlint'),
        'NATIVE_APP_PROJECT': 'Fixture.xcodeproj',
        'NATIVE_APP_SCHEME': 'Fixture',
        'NATIVE_APP_SOURCE_DIR': 'Sources',
        'NATIVE_APP_DESTINATION': f'platform=macOS,arch={platform.machine()}',
        'NATIVE_APP_VERIFY_UNSIGNED': '1',
        'HOME': str(root / 'home'),
        'CFFIXED_USER_HOME': str(root / 'home'),
    }
    for key, value in defaults.items():
        if key in ('HOME', 'CFFIXED_USER_HOME'):
            env[key] = value
        else:
            env.setdefault(key, value)
    (root / 'home').mkdir(exist_ok=True)
    return env


def run_swift(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=swift_env(cwd), text=True,
                            capture_output=True, check=False)
    logs = CACHE / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    stem = f'{cwd.name}-{time.time_ns()}'
    log = logs / f'{stem}.log'
    log.write_text(f'cwd={cwd}\ncommand={command!r}\nexit={result.returncode}\n'
                   + result.stdout + '\n' + result.stderr)
    # Hash only fixture inputs, never walk DerivedData/package caches.
    inputs = [cwd / '.native-app-fixture', cwd / 'Fixture.xcodeproj/project.pbxproj',
              cwd / '.swiftlint.yml', cwd / 'Modules/Package.swift']
    for directory in ['Config', 'Sources', 'scripts', 'Modules/Sources', 'Modules/Tests',
                      'Fixture.xcodeproj/xcshareddata']:
        inputs.extend((cwd / directory).rglob('*'))
    (logs / f'{stem}.json').write_text(json.dumps({
        'cwd': str(cwd), 'command': command, 'exit': result.returncode, 'log': str(log),
        'environment': {key: value for key, value in swift_env(cwd).items()
                        if key.startswith('NATIVE_APP_') or key in ('DEVELOPER_DIR', 'SWIFTLINT_BIN', 'HOME')},
        'input_sha256': {str(path.relative_to(cwd)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in inputs if path.is_file()},
    }, indent=2))
    return result


def copy_swift_fixture(platform: Literal['macos', 'ios']) -> Path:
    leaf = ROOT / 'swift' / platform
    if not leaf.is_dir():
        raise RuntimeError(f'{platform} leaf absent; do not borrow sibling settings')
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f'{platform}-', dir=CACHE))
    shutil.copytree(leaf, root, dirs_exist_ok=True)
    (root / '.native-app-fixture').write_text('approved-isolated-fixture\n')
    make_app_project(root, platform)
    return root


def make_app_project(root: Path, platform: Literal['macos', 'ios'], *,
                     connect_quality: bool = True, include_test: bool = True) -> tuple[Path, str]:
    if platform not in ('macos', 'ios'):
        raise ValueError('unsupported Swift fixture platform')
    sdk = 'macosx' if platform == 'macos' else 'iphoneos'
    executable = 'Contents/MacOS/Fixture' if platform == 'macos' else 'Fixture'
    project = root / 'Fixture.xcodeproj'
    schemes = project / 'xcshareddata/xcschemes'
    schemes.mkdir(parents=True, exist_ok=True)
    for directory, source, name in [('App', APP_SOURCE, 'FixtureApp'),
                                     ('AppTests', TEST_SOURCE if include_test else '', 'FixtureTests')]:
        path = root / 'Sources' / directory
        path.mkdir(parents=True, exist_ok=True)
        (path / f'{name}.swift').write_text(source)
    objects: dict[str, str] = {}

    def ident(name):
        return hashlib.sha256(name.encode()).hexdigest()[:24].upper()

    def add(name, content):
        objects[ident(name)] = content
        return ident(name)

    def refs(names):
        return '(' + ', '.join(ident(name) for name in names) + ',)'

    for name, path, kind in [('appSource', 'Sources/App/FixtureApp.swift', 'sourcecode.swift'),
                             ('testSource', 'Sources/AppTests/FixtureTests.swift', 'sourcecode.swift'),
                             ('debug', 'Config/Debug.xcconfig', 'text.xcconfig'),
                             ('release', 'Config/Release.xcconfig', 'text.xcconfig'),
                             ('appProduct', 'Fixture.app', 'wrapper.application'),
                             ('testProduct', 'FixtureTests.xctest', 'wrapper.cfbundle')]:
        tree = 'BUILT_PRODUCTS_DIR' if name.endswith('Product') else 'SOURCE_ROOT'
        add(name, f'isa = PBXFileReference; lastKnownFileType = {kind}; path = "{path}"; sourceTree = {tree};')
    add('mainGroup', 'isa = PBXGroup; children = ' + refs(['appSource', 'testSource', 'debug', 'release', 'products']) + '; sourceTree = "<group>";')
    add('products', 'isa = PBXGroup; children = ' + refs(['appProduct', 'testProduct']) + '; name = Products; sourceTree = "<group>";')
    add('proxy', f'isa = PBXContainerItemProxy; containerPortal = {ident("project")}; proxyType = 1; remoteGlobalIDString = {ident("app")}; remoteInfo = Fixture;')
    add('dependency', f'isa = PBXTargetDependency; target = {ident("app")}; targetProxy = {ident("proxy")};')
    targets = ['app', 'test'] if include_test else ['app']
    for target in targets:
        is_app = target == 'app'
        source = 'appSource' if is_app else 'testSource'
        add(target + 'BuildFile', f'isa = PBXBuildFile; fileRef = {ident(source)};')
        add(target + 'Sources', 'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ' + refs([target + 'BuildFile']) + '; runOnlyForDeploymentPostprocessing = 0;')
        add(target + 'Frameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
        add(target + 'Resources', 'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
        name = 'Fixture' if is_app else 'FixtureTests'
        kind = 'application' if is_app else 'bundle.unit-test'
        dependencies = '()' if is_app else refs(['dependency'])
        add(target, f'isa = PBXNativeTarget; buildConfigurationList = {ident(target + "Configs")}; buildPhases = {refs([target + "Sources", target + "Frameworks", target + "Resources"])}; buildRules = (); dependencies = {dependencies}; name = {name}; productName = {name}; productReference = {ident(target + "Product")}; productType = "com.apple.product-type.{kind}";')
        for config in ['Debug', 'Release']:
            base = f'baseConfigurationReference = {ident(config.lower())};' if connect_quality else ''
            host = '' if is_app else f'TEST_HOST = "$(BUILT_PRODUCTS_DIR)/Fixture.app/{executable}"; BUNDLE_LOADER = "$(TEST_HOST)";'
            add(target + config, f'isa = XCBuildConfiguration; {base} buildSettings = {{ ALWAYS_SEARCH_USER_PATHS = NO; PRODUCT_NAME = "$(TARGET_NAME)"; PRODUCT_BUNDLE_IDENTIFIER = "org.example.nativefixture.{target}"; SDKROOT = {sdk}; GENERATE_INFOPLIST_FILE = YES; {host} }}; name = {config};')
        add(target + 'Configs', f'isa = XCConfigurationList; buildConfigurations = {refs([target + "Debug", target + "Release"])}; defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
    for config in ['Debug', 'Release']:
        add('project' + config, f'isa = XCBuildConfiguration; buildSettings = {{}}; name = {config};')
    add('projectConfigs', f'isa = XCConfigurationList; buildConfigurations = {refs(["projectDebug", "projectRelease"])}; defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
    add('project', f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 2700; }}; buildConfigurationList = {ident("projectConfigs")}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = {ident("mainGroup")}; productRefGroup = {ident("products")}; projectDirPath = ""; projectRoot = ""; targets = {refs(targets)};')
    body = '\n'.join(f'{key} = {{ {value} }};' for key, value in objects.items())
    (project / 'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n' + body + f'\n}}; rootObject = {ident("project")}; }}\n')

    def reference(target):
        name = 'Fixture' if target == 'app' else 'FixtureTests'
        product = 'Fixture.app' if target == 'app' else 'FixtureTests.xctest'
        return f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ident(target)}" BuildableName="{product}" BlueprintName="{name}" ReferencedContainer="container:Fixture.xcodeproj"/>'

    entries = ''.join(f'<BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{reference(target)}</BuildActionEntry>' for target in targets)
    testable = f'<TestableReference skipped="NO">{reference("test")}</TestableReference>' if include_test else ''
    (schemes / 'Fixture.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2700" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>{entries}</BuildActionEntries></BuildAction>
<TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables>{testable}</Testables></TestAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference('app')}</BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"/>
<AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''')
    return project, 'Fixture'


# Architecture fixtures: generated outside the leaf, never distributed.
ARCH_SOURCES = {
    'Sources/Core/Item.swift': 'public struct Item: Sendable, Equatable {\n    public let name: String\n\n    public init(name: String) {\n        self.name = name\n    }\n}\n\npublic protocol ItemLoading: Sendable {\n    func load() -> [Item]\n}\n',
    'Sources/Clients/ItemClient.swift': 'import Core\n\npublic struct ItemClient: ItemLoading {\n    public init() {}\n\n    public func load() -> [Item] {\n        [Item(name: "fixture")]\n    }\n}\n',
    'Sources/Features/Home/HomeView.swift': 'import Core\nimport SwiftUI\n\npublic struct HomeView: View {\n    let items: [Item]\n\n    public init(items: [Item]) {\n        self.items = items\n    }\n\n    public var body: some View {\n        Text(items.first?.name ?? "")\n    }\n}\n',
    'Sources/Features/Settings/SettingsView.swift': 'import Core\nimport SwiftUI\n\npublic struct SettingsView: View {\n    public init() {}\n\n    public var body: some View {\n        Text("Settings")\n    }\n}\n',
    'Tests/CoreTests/ItemTests.swift': 'import Core\nimport XCTest\n\nfinal class ItemTests: XCTestCase {\n    func testName() {\n        XCTAssertEqual(Item(name: "a").name, "a")\n    }\n}\n',
}
SINGLE_TARGET_SOURCES = {
    'Sources/App/Models/Item.swift': 'import Foundation\n\nstruct Item: Identifiable {\n    let id = UUID()\n    let name: String\n}\n',
    'Sources/App/Services/ItemService.swift': 'import Foundation\n\nstruct ItemService {\n    func load() -> [Item] {\n        [Item(name: "fixture")]\n    }\n}\n',
    'Sources/App/Views/ItemList.swift': 'import SwiftUI\n\nstruct ItemList: View {\n    let items: [Item]\n\n    var body: some View {\n        List(items) { item in\n            Text(item.name)\n        }\n    }\n}\n',
}


def install_architecture(root: Path, option: Literal['thin-app-packages', 'single-target']) -> None:
    """Follow the leaf README: copy the option check and merge its SwiftLint rules."""
    source = root / 'architecture' / option
    shutil.copy(source / 'check-architecture.sh', root / 'scripts/check-architecture.sh')
    lint = root / '.swiftlint.yml'
    lint.write_text(lint.read_text().rstrip('\n') + '\n' + (source / 'swiftlint-rules.yml').read_text())
    if option == 'thin-app-packages':
        package = root / 'Modules'
        package.mkdir()
        shutil.copy(source / 'Package.swift.example', package / 'Package.swift')
        for relative, text in ARCH_SOURCES.items():
            (package / relative).parent.mkdir(parents=True, exist_ok=True)
            (package / relative).write_text(text)
    else:
        for relative, text in SINGLE_TARGET_SOURCES.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(text)


def copy_architecture_fixture(platform: Literal['macos', 'ios'],
                              option: Literal['thin-app-packages', 'single-target']) -> Path:
    root = copy_swift_fixture(platform)
    install_architecture(root, option)
    return root
