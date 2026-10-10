#!/bin/sh
# Single src-tauri crate only. Never install tools or mutate global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|test|build|all]'
case "$stage" in format|lint|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
[ -f rust-toolchain.toml ] || fail 'missing rust-toolchain.toml'
grep -Eq '^channel = "1\.92\.0"$' rust-toolchain.toml || fail 'requires pinned Rust 1.92.0'
RUSTUP_AUTO_INSTALL=0
export RUSTUP_AUTO_INSTALL
command -v rustup >/dev/null 2>&1 || fail 'rustup must already be installed; no automatic installation'
rustup_version=$(rustup --version) || fail 'cannot read rustup version'
printf '%s\n' "$rustup_version"
printf '%s\n' "$rustup_version" | awk '
    /^rustup [0-9]+\.[0-9]+\.[0-9]+ / {
        split($2, v, ".")
        if (v[1] > 1 || (v[1] == 1 && (v[2] > 28 || (v[2] == 28 && v[3] >= 2)))) ok = 1
    }
    END { exit !ok }
' || fail 'requires rustup 1.28.2 or newer (auto-install protection)'
# Inspect installed names first: even `rustup which` can bootstrap missing tools.
installed=$(rustup toolchain list) || fail 'cannot list installed toolchains'
toolchain=$(printf '%s\n' "$installed" | awk '$1 ~ /^1\.92\.0-[[:alnum:]_]+-[[:alnum:]_]+-[[:alnum:]_-]+$/ { print $1; exit }')
[ -n "$toolchain" ] || fail 'Rust 1.92.0 must already be installed'
cargo=$(rustup which --toolchain "$toolchain" cargo) || fail 'Rust 1.92.0 must already be installed'
rustc=$(rustup which --toolchain "$toolchain" rustc) || fail 'rustc must already be installed'
fmt=$(rustup which --toolchain "$toolchain" cargo-fmt) || fail 'rustfmt must already be installed'
clippy=$(rustup which --toolchain "$toolchain" cargo-clippy) || fail 'Clippy must already be installed'
for tool in "$cargo" "$rustc" "$fmt" "$clippy"; do
    [ -x "$tool" ] || fail "tool is not executable: $tool"
done
PATH="$(dirname "$cargo"):$PATH"
RUSTUP_TOOLCHAIN=$toolchain
export PATH RUSTUP_TOOLCHAIN
printf '%s\n' "tool: $cargo" "tool: $rustc" "tool: $fmt" "tool: $clippy"
version=$("$rustc" --version)
printf '%s\n' "$version"
case "$version" in 'rustc 1.92.0 '*) ;; *) fail 'requires Rust 1.92.0' ;; esac
"$cargo" --version
"$fmt" --version
"$clippy" --version
manifest=src-tauri/Cargo.toml
[ -s "$manifest" ] || fail 'missing manifest: src-tauri/Cargo.toml'
for source in src-tauri/src/main.rs src-tauri/src/lib.rs; do
    [ -f "$source" ] && grep -q '[^[:space:]]' "$source" || fail "missing or empty source: $source"
done
[ -s src-tauri/Cargo.lock ] || fail 'missing Cargo.lock; generate and review it explicitly first'
run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) "$cargo" fmt --manifest-path "$manifest" --check ;;
        lint) "$cargo" clippy --manifest-path "$manifest" --locked --all-targets -- -D warnings ;;
        test)
            if listing=$("$cargo" test --manifest-path "$manifest" --locked -- --list); then
                printf '%s\n' "$listing"
            else
                code=$?; printf '%s\n' "$listing"; exit "$code"
            fi
            printf '%s\n' "$listing" | grep -Eq ': test$' || fail 'no tests discovered'
            if output=$("$cargo" test --manifest-path "$manifest" --locked); then
                printf '%s\n' "$output"
            else
                code=$?; printf '%s\n' "$output"; exit "$code"
            fi
            printf '%s\n' "$output" | grep -Eq 'test result: ok\. [1-9][0-9]* passed;' || fail 'no tests executed'
            ;;
        build) "$cargo" build --manifest-path "$manifest" --locked ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint test build; do run_stage "$step"; done
else
    run_stage "$stage"
fi
