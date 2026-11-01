#!/bin/sh
# Manual checks only: no tool installation, global selection or signing changes.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|architecture|settings|test|build|all]'
case "$stage" in format|lint|architecture|settings|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
[ "$(uname -s)" = Darwin ] || fail 'macOS required'
command -v python3 >/dev/null || fail 'Python >=3.9 required'
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python >=3.9 required"'
[ -n "${DEVELOPER_DIR:-}" ] && [ -d "$DEVELOPER_DIR" ] || fail 'missing DEVELOPER_DIR (full Xcode)'
[ -n "${SWIFTLINT_BIN:-}" ] && [ -x "$SWIFTLINT_BIN" ] || fail 'missing executable SwiftLint (SWIFTLINT_BIN)'
[ -n "${NATIVE_APP_PROJECT:-}" ] || fail 'missing project'
[ -n "${NATIVE_APP_SCHEME:-}" ] || fail 'missing scheme'
[ -n "${NATIVE_APP_SOURCE_DIR:-}" ] || fail 'missing source directory'
[ -n "${NATIVE_APP_DESTINATION:-}" ] || fail 'missing destination'
# A concrete Simulator ID avoids generic/build-only and ambiguous destinations.
python3 - <<'PYDEST'
import os, re
if not re.fullmatch(r'platform=iOS Simulator,id=[A-Fa-f0-9-]{36}', os.environ['NATIVE_APP_DESTINATION']):
    raise SystemExit('error: requires concrete iOS Simulator destination (platform=iOS Simulator,id=UUID)')
PYDEST
export NATIVE_APP_WORK_DIR=${NATIVE_APP_WORK_DIR:-.native-check}
python3 - <<'PY'
import os
from pathlib import Path
root = Path.cwd().resolve()
for key, label in [('NATIVE_APP_PROJECT', 'project'), ('NATIVE_APP_SOURCE_DIR', 'source'),
                   ('NATIVE_APP_WORK_DIR', 'work directory')]:
    path = Path(os.environ[key]).resolve()
    if not path.is_relative_to(root) or path == root:
        raise SystemExit(f'error: {label} must be inside project root')
    if label == 'project' and (path.suffix != '.xcodeproj' or not (path / 'project.pbxproj').is_file()):
        raise SystemExit('error: missing standard Xcode project')
    if label == 'source':
        files = list(path.rglob('*.swift'))
        if not files or not any(p.read_text().strip() for p in files):
            raise SystemExit('error: empty Swift source')
        if any(not p.resolve().is_relative_to(root) for p in path.rglob('*')):
            raise SystemExit('error: source symlink outside project root')
# Require the caller's lock before Xcode can resolve external Swift packages.
project = Path(os.environ['NATIVE_APP_PROJECT'])
if 'XCRemoteSwiftPackageReference' in (project / 'project.pbxproj').read_text():
    lock = project / 'project.xcworkspace/xcshareddata/swiftpm/Package.resolved'
    if not lock.is_file() or not lock.read_text().strip():
        raise SystemExit('error: missing Package.resolved for external Swift packages')
# Reject project symlinks outside root, including shared schemes/config references.
project = Path(os.environ['NATIVE_APP_PROJECT'])
if any(not p.resolve().is_relative_to(root) for p in project.rglob('*')):
    raise SystemExit('error: project symlink outside project root')
PY
[ -f .swift-format ] && [ -f .swiftlint.yml ] || fail 'missing quality files'
SWIFTLINT_BIN=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$SWIFTLINT_BIN")
formatter=$(xcrun --find swift-format) || fail 'missing swift-format'
compiler=$(xcrun --find swiftc) || fail 'missing Swift compiler'
xcodebuild=$(xcrun --find xcodebuild) || fail 'missing Xcode'
xcresulttool=$(xcrun --find xcresulttool) || fail 'missing xcresulttool'
compiler_version=$("$compiler" --version)
printf '%s\n' "$compiler_version" | python3 -c 'import re,sys; m=re.search(r"Swift version (\d+)",sys.stdin.read()); assert m and int(m[1])>=6, "requires Swift compiler >=6"'
[ "$("$SWIFTLINT_BIN" version)" = 0.65.1 ] || fail 'requires SwiftLint 0.65.1'
# Same selected Xcode compiler/formatter/SourceKit environment, no CLT fallback.
for tool in "$formatter" "$compiler" "$xcodebuild" "$xcresulttool"; do
    case "$tool" in "$DEVELOPER_DIR"/*) ;; *) fail "tool outside DEVELOPER_DIR: $tool" ;; esac
done
mkdir -p "$NATIVE_APP_WORK_DIR"
work=$(CDPATH= cd -- "$NATIVE_APP_WORK_DIR" && pwd)
invocation=$(mktemp -d "$work/run-XXXXXXXX")
{
    printf 'DEVELOPER_DIR=%s\ndestination=%s\n' "$DEVELOPER_DIR" "$NATIVE_APP_DESTINATION"
    "$xcodebuild" -version
    printf '%s\n' "$compiler_version"
    "$formatter" --version
    "$SWIFTLINT_BIN" version
    xcrun --sdk iphonesimulator --show-sdk-version
    for tool in "$formatter" "$compiler" "$xcodebuild" "$xcresulttool" "$SWIFTLINT_BIN"; do
        printf 'path=%s\n' "$tool"
        shasum -a 256 "$tool"
    done
} > "$invocation/fingerprint.txt"
cat "$invocation/fingerprint.txt"
printf 'artifacts: %s\n' "$invocation"
xcrun simctl list devices available -j > "$invocation/devices.json"
xcrun simctl list runtimes -j > "$invocation/runtimes.json"
python3 - "$invocation/devices.json" "$invocation/runtimes.json" <<'PYDEVICE'
import json, os, sys
identifier = os.environ['NATIVE_APP_DESTINATION'].split('id=')[1]
runtimes = {r['identifier']: r for r in json.load(open(sys.argv[2]))['runtimes']}
for runtime, devices in json.load(open(sys.argv[1]))['devices'].items():
    for device in devices:
        if device['udid'] == identifier and device.get('isAvailable'):
            info = runtimes.get(runtime, {})
            if info.get('platform') != 'iOS' or not info.get('isAvailable'):
                raise SystemExit('error: destination runtime is not available iOS')
            print('Simulator destination:', device['name'], identifier, info['version'], info['buildversion'])
            sys.exit(0)
raise SystemExit('error: destination device is not available')
PYDEVICE
unsigned=${NATIVE_APP_VERIFY_UNSIGNED:-0}
case "$unsigned" in
    0) ;;
    1) [ -f .native-app-fixture ] && [ "$(cat .native-app-fixture)" = approved-isolated-fixture ] || fail 'VerifyUnsigned is fixture-only; explicit approval marker required'
       [ -f Config/VerifyUnsigned.xcconfig ] || fail 'missing VerifyUnsigned.xcconfig' ;;
    *) fail 'NATIVE_APP_VERIFY_UNSIGNED must be 0 or 1' ;;
esac
build_command() {
    if [ "$unsigned" = 1 ]; then
        "$xcodebuild" -project "$NATIVE_APP_PROJECT" -scheme "$NATIVE_APP_SCHEME" \
            -destination "$NATIVE_APP_DESTINATION" -derivedDataPath "$work/DerivedData" \
            -clonedSourcePackagesDirPath "$work/SourcePackages" -disableAutomaticPackageResolution \
            -xcconfig Config/VerifyUnsigned.xcconfig "$@"
    else
        "$xcodebuild" -project "$NATIVE_APP_PROJECT" -scheme "$NATIVE_APP_SCHEME" \
            -destination "$NATIVE_APP_DESTINATION" -derivedDataPath "$work/DerivedData" \
            -clonedSourcePackagesDirPath "$work/SourcePackages" -disableAutomaticPackageResolution "$@"
    fi
}
# A stale/absent scheme must not let format-only checks report a complete setup.
"$xcodebuild" -list -json -project "$NATIVE_APP_PROJECT" -disableAutomaticPackageResolution > "$invocation/project.json"
python3 - "$invocation/project.json" "$NATIVE_APP_SCHEME" <<'PY'
import json, sys
info = json.load(open(sys.argv[1]))
if sys.argv[2] not in info.get('project', {}).get('schemes', []):
    raise SystemExit('error: missing scheme')
PY
settings() {
    for configuration in Debug Release; do
        build_command -configuration "$configuration" -showBuildSettings -json > "$invocation/settings-$configuration.json"
        python3 - "$invocation/settings-$configuration.json" <<'PY'
import json, sys
settings = json.load(open(sys.argv[1]))
expected = {'SWIFT_VERSION': '6', 'SWIFT_TREAT_WARNINGS_AS_ERRORS': 'YES',
            'IPHONEOS_DEPLOYMENT_TARGET': '17.0', 'TARGETED_DEVICE_FAMILY': '1,2',
            'PLATFORM_NAME': 'iphonesimulator'}
if not settings:
    raise SystemExit('error: no target settings')
for target in settings:
    values = target['buildSettings']
    for key, value in expected.items():
        if values.get(key) != value:
            raise SystemExit(f'error: quality mismatch {target["target"]}: {key}={values.get(key)!r}, expected {value}')
    print(target['target'], {key: values[key] for key in expected})
PY
    done
}
# Dependency-direction rules for the architecture chosen in the README.
# The option script is sourced so it reuses fail, the selected tools and this
# invocation's fresh directory; it never reuses DerivedData from other stages.
architecture() {
    case "${NATIVE_APP_ARCHITECTURE:-}" in
        thin-app-packages|single-target) ;;
        '') fail 'missing NATIVE_APP_ARCHITECTURE (thin-app-packages|single-target)' ;;
        *) fail "unknown architecture: $NATIVE_APP_ARCHITECTURE" ;;
    esac
    [ -s scripts/check-architecture.sh ] || fail 'missing scripts/check-architecture.sh (copy architecture/<option>/check-architecture.sh)'
    . ./scripts/check-architecture.sh
}
run_stage() {
    printf 'stage: %s\n' "$1"
    case "$1" in
        format) "$formatter" lint --strict --recursive --configuration .swift-format "$NATIVE_APP_SOURCE_DIR" ;;
        lint) "$SWIFTLINT_BIN" lint --strict --no-cache --config .swiftlint.yml "$NATIVE_APP_SOURCE_DIR" ;;
        architecture) architecture ;;
        settings) settings ;;
        test)
            build_command -configuration Debug -parallel-testing-enabled NO -resultBundlePath "$invocation/tests.xcresult" test
            "$xcresulttool" get test-results summary --path "$invocation/tests.xcresult" > "$invocation/test-summary.json"
            cat "$invocation/test-summary.json"
            python3 - "$invocation/test-summary.json" <<'PY'
import json, sys
summary = json.load(open(sys.argv[1]))
if summary.get('totalTestCount', 0) <= 0 or summary.get('passedTests', 0) <= 0:
    raise SystemExit('error: no passing tests (zero or skipped-only tests)')
if summary.get('failedTests') != 0 or summary.get('testFailures'):
    raise SystemExit('error: failed tests')
PY
            ;;
        build) build_command -configuration Release build ;;
    esac
}
if [ "$stage" = all ]; then
    for next in format lint architecture settings test build; do
        if [ "$next" = architecture ] && [ -z "${NATIVE_APP_ARCHITECTURE:-}" ]; then
            printf '%s\n' 'architecture: not selected (NATIVE_APP_ARCHITECTURE unset)'
            continue
        fi
        run_stage "$next"
    done
else
    # Direct test/build also require effective quality, not just presence of files.
    case "$stage" in test|build) run_stage settings ;; esac
    run_stage "$stage"
fi
