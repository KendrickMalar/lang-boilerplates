# One target + folder rules: sourced by `scripts/check.sh architecture`.
# Copy to scripts/check-architecture.sh and set NATIVE_APP_ARCHITECTURE=single-target.
# One module cannot hide types, so SwiftLint import rules are the enforcement;
# the lint stage runs them too, this stage fails if they were dropped.
expected_architecture=single-target
[ "$NATIVE_APP_ARCHITECTURE" = "$expected_architecture" ] ||
    fail "scripts/check-architecture.sh is for $expected_architecture, not $NATIVE_APP_ARCHITECTURE"
printf 'architecture: %s (%s)\n' "$expected_architecture" "$NATIVE_APP_SOURCE_DIR"
grep -q '^custom_rules:$' .swiftlint.yml || fail 'missing SwiftLint architecture rule: custom_rules'
set --
for rule in arch_models_no_ui arch_services_no_ui; do
    grep -q "^  $rule:\$" .swiftlint.yml ||
        fail "missing SwiftLint architecture rule: $rule (merge architecture/$expected_architecture/swiftlint-rules.yml)"
    set -- "$@" --only-rule "$rule"
done
"$SWIFTLINT_BIN" lint --strict --no-cache --config .swiftlint.yml "$@" "$NATIVE_APP_SOURCE_DIR"
