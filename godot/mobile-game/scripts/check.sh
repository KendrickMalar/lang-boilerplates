#!/bin/sh
# Godot project checks. Never installs tools or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|architecture|typecheck|test|all]'
case "$stage" in format|lint|architecture|typecheck|test|all) ;; *) fail "unknown stage: $stage" ;; esac
GODOT_VERSION=4.7.2
GDTOOLKIT_VERSION=4.5.0

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is missing; install it (see README) and check PATH"; }
need godot
need gdlint
need gdformat
need python3
printf '%s\n' "tool: $(command -v python3) $(python3 --version 2>&1)"
actual=$(godot --version </dev/null 2>&1) || fail "cannot read godot version: $actual"
printf '%s\n' "tool: $(command -v godot) $actual"
case "$actual" in "$GODOT_VERSION.stable"*) ;; *) fail "godot must be $GODOT_VERSION (found: $actual)" ;; esac
for tool in gdlint gdformat; do
    actual=$("$tool" --version </dev/null 2>&1) || fail "cannot read $tool version: $actual"
    printf '%s\n' "tool: $(command -v "$tool") $actual"
    [ "$actual" = "$tool $GDTOOLKIT_VERSION" ] || fail "$tool must be $GDTOOLKIT_VERSION (found: $actual)"
done
find src tests -type f -name '*.gd' | grep -q . || fail 'no GDScript under src/ or tests/'

# Godot exits 0 on parse/type errors and keeps running after runtime script errors,
# so the output is part of the verdict.
godot_run() {
    log=$(mktemp)
    status=0
    godot --headless --path . "$@" >"$log" 2>&1 || status=$?
    cat "$log"
    if [ "$status" -ne 0 ] || grep -E 'SCRIPT ERROR|Parse Error|Failed to load script' "$log" >/dev/null; then
        rm -f "$log"
        return 1
    fi
    rm -f "$log"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) gdformat --check src tests scripts ;;
        lint) gdlint src tests scripts ;;
        # Layer rules chosen from README「アーキテクチャ」; missing architecture.json fails.
        architecture) python3 scripts/check_architecture.py architecture.json ;;
        typecheck)
            godot_run --import || fail 'godot import failed'
            find src tests scripts -type f -name '*.gd' | sort | while IFS= read -r file; do
                godot_run --check-only --script "$file" || fail "typecheck failed: $file"
            done
            ;;
        test)
            godot_run --import || fail 'godot import failed'
            godot_run --script scripts/test_runner.gd || fail 'tests failed'
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint architecture typecheck test; do run_stage "$step"; done
else
    run_stage "$stage"
fi
