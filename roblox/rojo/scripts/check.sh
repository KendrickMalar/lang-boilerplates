#!/bin/sh
# Rojo project checks. Never installs tools/packages or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|typecheck|test|build|all]'
case "$stage" in format|lint|typecheck|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
DEFS_URL='https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/1.69.0/scripts/globalTypes.d.luau'
DEFS_SHA256='7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2'
DEFS=.luau-lsp-cache/globalTypes-1.69.0.d.luau

[ -s rokit.toml ] || fail 'missing rokit.toml'
# Every non-comment line under [tools] must be a plain pin; anything else would skip a check.
pins=$(awk '
    /^[[:space:]]*(#|$)/ { next }
    /^\[/ { tools = ($0 == "[tools]"); next }
    !tools { next }
    /^[a-z0-9_-]+ = "[^"]+\/[^"@]+@[^"]+"$/ {
        split($0, q, "\""); n = split(q[2], v, "@"); print $1, v[n]; next
    }
    { bad = 1; print "!" $0 }
    END { exit bad }
' rokit.toml) || fail "cannot parse rokit.toml [tools] line: $(printf '%s\n' "$pins" | sed -n 's/^!//p' | head -n 1)"
[ -n "$pins" ] || fail 'rokit.toml pins no tools'
while read -r tool version; do
    command -v "$tool" >/dev/null 2>&1 || fail "$tool is missing; run rokit install and put ~/.rokit/bin first on PATH"
    actual=$("$tool" --version </dev/null 2>&1) || fail "cannot read $tool version: $actual"
    printf '%s\n' "tool: $(command -v "$tool") $actual"
    case " $actual " in
        *[!0-9.]"$version"[!0-9.]*) ;;
        *) fail "$tool must be $version (found: $actual); run rokit install and check PATH order" ;;
    esac
done <<EOF
$pins
EOF

find src -type f -name '*.luau' | grep -q . || fail 'no Luau source under src/'
[ -s roblox.yml ] || fail 'missing roblox.yml; run selene generate-roblox-std and commit it'
# Only [dependencies] (Packages/) is wired into Rojo; comments and indentation are ignored.
wally_tables=$(awk '
    { sub(/#.*/, ""); gsub(/^[[:space:]]+|[[:space:]]+$/, "") }
    /^\[/ { table = $0; next }
    table ~ /^\[(server-|dev-)?dependencies\]$/ && /^[A-Za-z0-9_-]+[[:space:]]*=/ { print table }
' wally.toml | sort -u)
case "$wally_tables" in
    *server-dependencies*|*dev-dependencies*)
        fail 'this setup supports only [dependencies] (Packages/); move server/dev dependencies or extend default.project.json and .gitignore' ;;
esac
if [ -n "$wally_tables" ] && [ ! -d Packages ]; then
    fail 'wally.toml declares dependencies but Packages/ is missing; run wally install'
fi

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{ print $1 }'
}
ensure_defs() {
    if [ ! -f "$DEFS" ]; then
        command -v curl >/dev/null 2>&1 || fail 'curl is required to fetch Roblox type definitions'
        mkdir -p .luau-lsp-cache
        tmp="$DEFS.tmp.$$"
        curl -fsSL -o "$tmp" "$DEFS_URL" || { rm -f "$tmp"; fail "cannot download $DEFS_URL"; }
        [ "$(sha256 "$tmp")" = "$DEFS_SHA256" ] || { rm -f "$tmp"; fail 'downloaded type definitions SHA256 mismatch'; }
        mv "$tmp" "$DEFS"
    fi
    [ "$(sha256 "$DEFS")" = "$DEFS_SHA256" ] || fail "type definitions SHA256 mismatch: $DEFS (delete it to refetch)"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) stylua --check src tests scripts ;;
        lint) selene src tests scripts ;;
        typecheck)
            ensure_defs
            rojo sourcemap default.project.json --output sourcemap.json
            luau-lsp analyze --platform=roblox --sourcemap=sourcemap.json \
                --definitions=@roblox="$DEFS" --ignore='Packages/**' src tests
            ;;
        test) lune run scripts/test.luau ;;
        build)
            out=$(mktemp -d)
            if ! rojo build default.project.json --output "$out/place.rbxl"; then rm -rf "$out"; exit 1; fi
            [ -s "$out/place.rbxl" ] || { rm -rf "$out"; fail 'rojo build produced no place file'; }
            rm -rf "$out"
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint typecheck test build; do run_stage "$step"; done
else
    run_stage "$stage"
fi
