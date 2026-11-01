# Thin app + local package: sourced by `scripts/check.sh architecture`.
# Copy to scripts/check-architecture.sh and set NATIVE_APP_ARCHITECTURE=thin-app-packages
# and NATIVE_APP_PACKAGE_DIR (the local package directory). Uses check.sh's fail,
# SWIFTLINT_BIN, formatter and the fresh per-invocation directory $invocation.
expected_architecture=thin-app-packages
[ "$NATIVE_APP_ARCHITECTURE" = "$expected_architecture" ] ||
    fail "scripts/check-architecture.sh is for $expected_architecture, not $NATIVE_APP_ARCHITECTURE"
[ -n "${NATIVE_APP_PACKAGE_DIR:-}" ] || fail 'missing NATIVE_APP_PACKAGE_DIR (local Swift package directory)'
python3 - <<'PY'
import os
from pathlib import Path
root = Path.cwd().resolve()
package = Path(os.environ['NATIVE_APP_PACKAGE_DIR']).resolve()
if not package.is_relative_to(root) or package == root:
    raise SystemExit('error: local package must be inside project root')
if not (package / 'Package.swift').is_file():
    raise SystemExit('error: missing Package.swift in NATIVE_APP_PACKAGE_DIR')
if not any(p.read_text().strip() for p in (package / 'Sources').rglob('*.swift')):
    raise SystemExit('error: empty local package sources')
PY
printf 'architecture: %s (%s)\n' "$expected_architecture" "$NATIVE_APP_PACKAGE_DIR"
grep -q '^custom_rules:$' .swiftlint.yml || fail 'missing SwiftLint architecture rule: custom_rules'
for rule in arch_core_pure_swift arch_feature_isolation arch_clients_no_features; do
    grep -q "^  $rule:\$" .swiftlint.yml ||
        fail "missing SwiftLint architecture rule: $rule (merge architecture/$expected_architecture/swiftlint-rules.yml)"
done
# NATIVE_APP_SOURCE_DIR may not contain the package, so format/lint it here too.
set -- "$NATIVE_APP_PACKAGE_DIR/Sources"
[ ! -d "$NATIVE_APP_PACKAGE_DIR/Tests" ] || set -- "$@" "$NATIVE_APP_PACKAGE_DIR/Tests"
"$formatter" lint --strict --recursive --configuration .swift-format "$@"
"$SWIFTLINT_BIN" lint --strict --no-cache --config .swiftlint.yml "$@"
# Declared target edges: SwiftPM permits whatever the manifest declares.
swift=$(xcrun --find swift) || fail 'missing swift'
case "$swift" in "$DEVELOPER_DIR"/*) ;; *) fail "tool outside DEVELOPER_DIR: $swift" ;; esac
"$swift" package --package-path "$NATIVE_APP_PACKAGE_DIR" --scratch-path "$invocation/architecture-manifest" \
    dump-package > "$invocation/architecture-manifest.json"
python3 - "$invocation/architecture-manifest.json" <<'PY'
import json, os, sys
from pathlib import Path
manifest = json.load(open(sys.argv[1]))
targets = {target['name']: target for target in manifest['targets']}
errors = []
def local(target):
    names = []
    for dependency in target['dependencies']:
        for kind in ('byName', 'target'):
            if kind in dependency and dependency[kind][0] in targets:
                names.append(dependency[kind][0])
    return names
if targets.get('Core', {}).get('type') != 'regular':
    errors.append('Core: a regular target named Core is required')
for name, target in targets.items():
    if target['type'] == 'test':
        continue
    if target['type'] != 'regular':
        errors.append(f'{name}: {target["type"]} targets are not part of this architecture')
    elif name == 'Core':
        if target['dependencies']:
            errors.append(f'Core: must not depend on anything, found {target["dependencies"]}')
    elif name == 'Clients' or name.endswith('Feature'):
        forbidden = [dependency for dependency in local(target) if dependency != 'Core']
        if forbidden:
            errors.append(f'{name}: may depend only on Core, found {forbidden}')
    else:
        errors.append(f'{name}: unknown layer (allowed: Core, Clients, <Name>Feature, test targets)')
if manifest.get('dependencies') and not (Path(os.environ['NATIVE_APP_PACKAGE_DIR']) / 'Package.resolved').is_file():
    errors.append('external packages require the local package Package.resolved')
for error in errors:
    print(f'error: architecture violation: {error}', file=sys.stderr)
if errors:
    raise SystemExit(1)
print('architecture: manifest layers', {name: local(target) for name, target in targets.items()})
PY
# Undeclared imports fail only in a clean build; incremental builds can pass.
printf 'architecture: clean package build (%s)\n' "$invocation/architecture-build"
"$swift" build --package-path "$NATIVE_APP_PACKAGE_DIR" --scratch-path "$invocation/architecture-build" \
    --build-tests --disable-automatic-resolution --explicit-target-dependency-import-check error
