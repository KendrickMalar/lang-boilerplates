#!/bin/sh
# Virtual workspace (crates/*). Never install tools, auto-fix, auto-stage, or mutate global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
[ "$#" -eq 1 ] || fail 'usage: check.sh <format|lint|deps|test|commit>'
stage=$1
case "$stage" in
    format|lint|deps|test) stages=$stage ;;
    commit) stages='format lint deps test' ;;
    *) fail "unknown stage: $stage" ;;
esac
[ -f rust-toolchain.toml ] || fail 'missing rust-toolchain.toml'
grep -Eq '^channel = "1\.99\.1"$' rust-toolchain.toml || fail 'requires pinned Rust 1.99.1'
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
toolchain=$(printf '%s\n' "$installed" | awk '$1 ~ /^1\.99\.1-[[:alnum:]_]+-[[:alnum:]_]+-[[:alnum:]_-]+$/ { print $1; exit }')
[ -n "$toolchain" ] || fail 'Rust 1.99.1 must already be installed'
cargo=$(rustup which --toolchain "$toolchain" cargo) || fail 'Rust 1.99.1 must already be installed'
rustc=$(rustup which --toolchain "$toolchain" rustc) || fail 'rustc must already be installed'
fmt=$(rustup which --toolchain "$toolchain" cargo-fmt) || fail 'rustfmt must already be installed'
clippy=$(rustup which --toolchain "$toolchain" cargo-clippy) || fail 'Clippy must already be installed'
for tool in "$cargo" "$rustc" "$fmt" "$clippy"; do
    [ -x "$tool" ] || fail "tool is not executable: $tool"
done
PATH="$(dirname "$cargo"):$PATH"
RUSTUP_TOOLCHAIN=$toolchain
CARGO=$cargo
export PATH RUSTUP_TOOLCHAIN CARGO
printf '%s\n' "tool: $cargo" "tool: $rustc" "tool: $fmt" "tool: $clippy"
version=$("$rustc" --version)
printf '%s\n' "$version"
case "$version" in 'rustc 1.99.1 '*) ;; *) fail 'requires Rust 1.99.1' ;; esac
"$cargo" --version
"$fmt" --version
"$clippy" --version

# Cargo subcommands: found on PATH, exact pinned version, then called by absolute path.
pinned_tool() {
    path=$(command -v "$1" 2>/dev/null) || fail "$1 $2 must already be installed; no automatic installation"
    [ -x "$path" ] || fail "tool is not executable: $path"
    first=$("$path" --version 2>&1 | sed -n 1p) || fail "cannot read $1 version"
    pattern=$(printf '%s\n' "$2" | sed 's/\./\\./g')
    printf '%s\n' "$first" | grep -Eq "(^|[ :])$pattern( |\$)" || fail "requires $1 $2 (found: $first)"
    printf '%s\n' "$path"
}
case " $stages " in *' test '*)
    nextest=$(pinned_tool cargo-nextest 0.9.150)
    printf '%s\n' "tool: $nextest"
    ;;
esac
case " $stages " in *' deps '*)
    deny=$(pinned_tool cargo-deny 0.20.2)
    shear=$(pinned_tool cargo-shear 1.14.0)
    printf '%s\n' "tool: $deny" "tool: $shear"
    ;;
esac

[ -s Cargo.toml ] || fail 'missing workspace manifest: Cargo.toml'
sources=$(find crates -path '*/src/*' -name '*.rs' -type f -size +0 2>/dev/null | sed -n 1p)
[ -n "$sources" ] || fail 'no Rust source: add a crate under crates/<name>/src/'
[ -s Cargo.lock ] || fail 'missing Cargo.lock; generate and review it explicitly first'

metadata=$("$cargo" metadata --no-deps --locked --format-version 1) || fail 'cargo metadata failed'
manifests=$(printf '%s\n' "$metadata" | grep -o '"manifest_path":"[^"]*"' | sed 's/^"manifest_path":"//; s/"$//')
[ -n "$manifests" ] || fail 'no workspace members under crates/'

# Every workspace member must inherit [workspace.lints].
check_member_lints() {
    printf '%s\n' "$manifests" | while IFS= read -r manifest; do
        awk '
            /^[[:space:]]*\[/ { section = $0; gsub(/[[:space:]]/, "", section) }
            section == "[lints]" && /^[[:space:]]*workspace[[:space:]]*=[[:space:]]*true[[:space:]]*(#.*)?$/ { ok = 1 }
            END { exit !ok }
        ' "$manifest" || fail "member must set [lints] workspace = true: $manifest"
    done
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) "$cargo" fmt --all --check ;;
        lint)
            check_member_lints
            "$cargo" clippy --workspace --all-targets --all-features --locked -- -D warnings
            ;;
        deps)
            "$shear" shear
            "$deny" deny --offline check bans licenses sources
            ;;
        test)
            "$nextest" nextest run --workspace --locked --no-tests=fail
            # nextest cannot run doctests; `cargo test --doc` rejects binary-only workspaces.
            if printf '%s\n' "$metadata" | grep -Eq '"kind":\[[^]]*"(lib|rlib|proc-macro)"'; then
                "$cargo" test --doc --workspace --locked
            else
                printf '%s\n' 'doctests: skipped (no library targets)'
            fi
            ;;
    esac
}
for step in $stages; do run_stage "$step"; done
