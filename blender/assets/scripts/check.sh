#!/bin/sh
# Blender asset checks. Never installs tools or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|test|build|all]'
case "$stage" in format|lint|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
BLENDER_VERSION=5.2.2
RUFF_VERSION=0.17.0
GLTF_TRANSFORM_VERSION=4.5.1

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is missing; install it (see README) and check PATH"; }
need blender
need ruff
need gltf-transform
actual=$(blender --version </dev/null 2>&1 | head -n 1) || fail 'cannot read blender version'
printf '%s\n' "tool: $(command -v blender) $actual"
case "$actual" in "Blender $BLENDER_VERSION"|"Blender $BLENDER_VERSION "*) ;; *) fail "blender must be $BLENDER_VERSION (found: $actual)" ;; esac
actual=$(ruff --version </dev/null 2>&1) || fail "cannot read ruff version: $actual"
printf '%s\n' "tool: $(command -v ruff) $actual"
[ "$actual" = "ruff $RUFF_VERSION" ] || fail "ruff must be $RUFF_VERSION (found: $actual)"
actual=$(gltf-transform --version </dev/null 2>&1) || fail "cannot read gltf-transform version: $actual"
printf '%s\n' "tool: $(command -v gltf-transform) $actual"
[ "$actual" = "$GLTF_TRANSFORM_VERSION" ] || fail "gltf-transform must be $GLTF_TRANSFORM_VERSION (found: $actual)"

# Blender exits 0 when a --python script raises unless --python-exit-code is set.
run_blender() {
    script=$1
    shift
    blender -b --factory-startup --python-exit-code 1 --python "$script" -- "$@"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) ruff format --check models tests scripts ;;
        lint) ruff check models tests scripts ;;
        test) run_blender scripts/test.py || fail 'tests failed' ;;
        build)
            out=$(mktemp -d)
            if ! run_blender scripts/build.py --out "$out"; then rm -rf "$out"; fail 'build failed'; fi
            found=0
            for glb in "$out"/*.glb; do
                [ -f "$glb" ] || continue
                found=1
                if ! gltf-transform validate "$glb"; then rm -rf "$out"; fail "invalid glTF: $(basename "$glb")"; fi
            done
            rm -rf "$out"
            [ "$found" -eq 1 ] || fail 'build produced no .glb'
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint test build; do run_stage "$step"; done
else
    run_stage "$stage"
fi
