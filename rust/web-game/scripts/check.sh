#!/bin/sh
# Virtual workspace (crates/*). Never install tools, auto-fix, auto-stage, or mutate global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
[ "$#" -eq 1 ] || fail 'usage: check.sh <format|lint|deps|test|coverage|advisories|build|commit|push|all>'
stage=$1
case "$stage" in
    format|lint|deps|test|coverage|advisories|build) stages=$stage ;;
    # coverage runs the tests (nextest under llvm-cov) and then the doctests, once.
    commit) stages='format lint deps coverage' ;;
    # advisories is the only stage that needs network (RustSec advisory DB).
    push|all) stages='format lint deps coverage advisories build' ;;
    *) fail "unknown stage: $stage" ;;
esac
[ -f rust-toolchain.toml ] || fail 'missing rust-toolchain.toml'
grep -Eq '^channel = "1\.99\.1"$' rust-toolchain.toml || fail 'requires pinned Rust 1.99.1'
RUSTUP_AUTO_INSTALL=0
export RUSTUP_AUTO_INSTALL
# sqlx macros check queries against .sqlx/ (cargo sqlx prepare), not a live database.
SQLX_OFFLINE=${SQLX_OFFLINE:-true}
export SQLX_OFFLINE
printf '%s\n' "env: SQLX_OFFLINE=$SQLX_OFFLINE"
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
# Optional $3: subcommand the binary needs before --version (cargo-llvm-cov: llvm-cov).
pinned_tool() {
    path=$(command -v "$1" 2>/dev/null) || fail "$1 $2 must already be installed; no automatic installation"
    [ -x "$path" ] || fail "tool is not executable: $path"
    # Capture first so a non-zero exit from the tool itself is not hidden by a pipe.
    probe=$("$path" ${3:+"$3"} --version 2>&1) || fail "cannot read $1 version"
    first=$(printf '%s\n' "$probe" | sed -n 1p)
    pattern=$(printf '%s\n' "$2" | sed 's/\./\\./g')
    printf '%s\n' "$first" | grep -Eq "(^|[ :])$pattern( |\$)" || fail "requires $1 $2 (found: $first)"
    printf '%s\n' "$path"
}
case " $stages " in *' test '*|*' coverage '*)
    nextest=$(pinned_tool cargo-nextest 0.9.150)
    printf '%s\n' "tool: $nextest"
    ;;
esac
case " $stages " in *' deps '*|*' advisories '*)
    deny=$(pinned_tool cargo-deny 0.20.2)
    printf '%s\n' "tool: $deny"
    ;;
esac
case " $stages " in *' deps '*)
    shear=$(pinned_tool cargo-shear 1.14.0)
    printf '%s\n' "tool: $shear"
    ;;
esac
case " $stages " in *' coverage '*)
    llvm_cov=$(pinned_tool cargo-llvm-cov 0.9.1 llvm-cov)
    printf '%s\n' "tool: $llvm_cov"
    ;;
esac

[ -s Cargo.toml ] || fail 'missing workspace manifest: Cargo.toml'
sources=$(find crates -path '*/src/*' -name '*.rs' -type f -size +0 2>/dev/null | sed -n 1p)
[ -n "$sources" ] || fail 'no Rust source: add a crate under crates/<name>/src/'
[ -s Cargo.lock ] || fail 'missing Cargo.lock; generate and review it explicitly first'

metadata=$("$cargo" metadata --no-deps --locked --format-version 1) || fail 'cargo metadata failed'
manifests=$(printf '%s\n' "$metadata" | grep -o '"manifest_path":"[^"]*"' | sed 's/^"manifest_path":"//; s/"$//')
[ -n "$manifests" ] || fail 'no workspace members under crates/'

# Every workspace member must inherit [workspace.lints]. Cargo accepts three spellings:
#   [lints] workspace = true  |  lints.workspace = true  |  lints = { workspace = true }
# The last two are top-level keys, so they only count before the first [table] header.
check_member_lints() {
    printf '%s\n' "$manifests" | while IFS= read -r manifest; do
        awk '
            /^[[:space:]]*\[/ { section = $0; gsub(/[[:space:]]/, "", section) }
            section == "[lints]" && /^[[:space:]]*workspace[[:space:]]*=[[:space:]]*true[[:space:]]*(#.*)?$/ { ok = 1 }
            section == "" && /^[[:space:]]*lints[[:space:]]*\.[[:space:]]*workspace[[:space:]]*=[[:space:]]*true[[:space:]]*(#.*)?$/ { ok = 1 }
            section == "" && /^[[:space:]]*lints[[:space:]]*=[[:space:]]*\{[[:space:]]*workspace[[:space:]]*=[[:space:]]*true[[:space:]]*,?[[:space:]]*\}[[:space:]]*(#.*)?$/ { ok = 1 }
            END { exit !ok }
        ' "$manifest" || fail "member must set [lints] workspace = true: $manifest"
    done
}

# nextest cannot run doctests; `cargo test --doc` rejects binary-only workspaces.
run_doctests() {
    if printf '%s\n' "$metadata" | grep -Eq '"kind":\[[^]]*"(lib|rlib|proc-macro)"'; then
        "$cargo" test --doc --workspace --locked
    else
        printf '%s\n' 'doctests: skipped (no library targets)'
    fi
}

# Line coverage floor: change it only here and record why in the product README.
line_floor=90
check_coverage() {
    status=0
    report=$("$llvm_cov" llvm-cov nextest --workspace --locked --no-tests=fail --fail-under-lines "$line_floor") || status=$?
    printf '%s\n' "$report"
    [ "$status" -ne 0 ] || return 0
    # cargo-llvm-cov exits 1 under the floor without saying so; the report's TOTAL line
    # ($10 = line cover) tells a threshold miss apart from failing tests or missing tools.
    if printf '%s\n' "$report" | awk -v floor="$line_floor" '
        $1 == "TOTAL" && $10 ~ /^[0-9.]+%$/ { found = 1; below = ($10 + 0 < floor) }
        END { exit !(found && below) }
    '; then
        fail "line coverage below ${line_floor}% (--fail-under-lines $line_floor)"
    fi
    exit "$status"
}

# The RustSec advisory DB (https://github.com/rustsec/advisory-db) is fetched into
# $CARGO_HOME/advisory-dbs on every run; a stale cached copy is never used silently.
offline_advisories='advisory database could not be fetched (network required)'
check_advisories() {
    case "${CARGO_NET_OFFLINE:-}" in
        true|TRUE|True|1) fail "$offline_advisories: CARGO_NET_OFFLINE=$CARGO_NET_OFFLINE" ;;
    esac
    status=0
    output=$("$deny" deny check advisories 2>&1) || status=$?
    if [ "$status" -eq 0 ]; then
        printf '%s\n' "$output"
        return 0
    fi
    printf '%s\n' "$output" >&2
    # cargo-deny's own fetch error, not advisory text (which may mention "network").
    if printf '%s\n' "$output" | grep -Eq '\[ERROR\] failed to fetch advisory database'; then
        fail "$offline_advisories"
    fi
    fail "cargo deny check advisories failed (exit $status)"
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
            sh scripts/check-architecture.sh "$deny"
            ;;
        test)
            "$nextest" nextest run --workspace --locked --no-tests=fail
            run_doctests
            ;;
        coverage)
            check_coverage
            run_doctests
            ;;
        advisories) check_advisories ;;
        build) "$cargo" build --workspace --locked --release ;;
    esac
}
for step in $stages; do run_stage "$step"; done
