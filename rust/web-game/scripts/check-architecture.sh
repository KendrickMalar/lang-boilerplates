#!/bin/sh
# Dependency-direction check for the architecture chosen in architecture/ (copied from the
# leaf's architecture/<choice>/). Called by the deps stage of scripts/check.sh.
#   architecture/layers.conf: lines `<crate> uses <workspace crates...>` (the only workspace
#     crates it may depend on directly) and `<crate> never <crates...>` (crates that must not
#     appear anywhere in its normal/build dependency tree). Every workspace member needs a
#     `uses` line, even an empty one.
#   architecture/deny.toml: cargo-deny `[bans]` wrappers (which crates may use a crate directly).
# Dev-dependencies are not checked. Never installs tools or edits files.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
conf=architecture/layers.conf
bans=architecture/deny.toml
if [ ! -f "$conf" ]; then
    printf '%s\n' "architecture: skipped (no $conf)"
    exit 0
fi
[ -f "$bans" ] || fail "missing $bans (copy it together with $conf)"
cargo=${CARGO:-cargo}
[ "$#" -le 1 ] || fail 'usage: check-architecture.sh [cargo-deny path]'
deny=${1:-cargo-deny}

"$deny" deny --offline --config "$bans" check bans

# One line per tree node: <depth><name> v<version> ... (no dedupe, so every subtree is complete).
tree=$("$cargo" tree --workspace --locked --all-features --target all -e normal,build \
    --no-dedupe --prefix depth --format '{p}') || fail 'cargo tree failed'

printf '%s\n' "$tree" | awk -v conf="$conf" '
    BEGIN {
        while ((getline line < conf) > 0) {
            sub(/#.*/, "", line)
            n = split(line, f, /[[:space:]]+/)
            start = (f[1] == "") ? 2 : 1
            if (n < start) continue
            crate = f[start]; key = f[start + 1]
            if (key == "uses") listed[crate] = 1
            else if (key != "never") { printf "error: architecture: %s: unknown key `%s` (uses|never)\n", conf, key > "/dev/stderr"; bad = 1; continue }
            for (i = start + 2; i <= n; i++) if (f[i] != "") rule[key, crate, f[i]] = 1
        }
        close(conf)
    }
    # Skip blank separators and section headers such as [build-dependencies].
    !/^[0-9]/ { next }
    {
        match($0, /^[0-9]+/)
        depth = substr($0, 1, RLENGTH) + 0
        rest = substr($0, RLENGTH + 1)
        split(rest, w, " ")
        name = w[1]
        path[depth] = name
        if (depth == 0) { top = name; member[name] = 1; next }
        if (depth == 1) direct[top, name] = 1
        if ((("never", top, name) in rule) && !seen[top, name]++) {
            chain = path[0]
            for (i = 1; i <= depth; i++) chain = chain " -> " path[i]
            printf "error: architecture: %s must not depend on %s (%s)\n", top, name, chain > "/dev/stderr"
            bad = 1
        }
    }
    END {
        for (m in member) if (!(m in listed)) {
            printf "error: architecture: workspace crate %s has no `%s uses ...` line in %s\n", m, m, conf > "/dev/stderr"
            bad = 1
        }
        for (key in direct) {
            split(key, p, SUBSEP)
            if ((p[2] in member) && (p[1] in listed) && !(("uses", p[1], p[2]) in rule)) {
                printf "error: architecture: %s must not depend on workspace crate %s directly\n", p[1], p[2] > "/dev/stderr"
                bad = 1
            }
        }
        exit bad
    }
' || fail "dependency direction violates $conf"
printf '%s\n' "architecture: ok ($conf, $bans)"
