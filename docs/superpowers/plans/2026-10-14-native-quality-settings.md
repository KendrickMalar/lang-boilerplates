# Native quality settings implementation plan

> For agentic workers: use superpowers:executing-plans. Implement each task with RED→GREEN verification.

**Goal:** Strengthen compiler/lint/formatter settings for Rust, Swift and Luau without blanket lint groups.
**Architecture:** Keep each copyable leaf independent; add real-tool acceptance tests and document provenance.
**Tech Stack:** Rust 1.92/Clippy, SwiftLint 0.65.1/Xcode swift-format, luau-lsp 1.69.0/Selene 0.32.0.
**Spec:** User-approved in-chat design, 2026-10-14.

## Global constraints
- TypeScript, tool versions, dependencies, CI and product source unchanged.
- No installation, push, publication, merge or cleanup. User approved installation exemption for this task.
- Dedicated feature worktree; preserve existing worktrees and main's tests/native/__pycache__/.
- Preserve formatter appearance: Rust/Swift 4 spaces, 100 columns; Luau tabs, 120 columns.

## Review focus
- Removing any selected lint must make its violation test fail.
- Swift formatted multiline collections and long strings must pass both tools.
- Swift macOS/iOS leaves must enforce identical lint behavior.
- Luau lint-only defects must produce nonzero exit; normal code must pass.
- No tool bootstrap, user configuration changes or false zero-test success.

## Task 1: Rust
- [ ] Add tests/native/test_quality_settings.py Rust cases: redundant_clone, assigning_clones, or_fun_call; fixed compiler, copied lint tables, isolated dependency-free crate; each defect nonzero with named diagnostic, corrected case exit 0.
- [ ] Run against old settings; observe missing-lint failures.
- [ ] Add three individual warn-level lints to rust/tauri/src-tauri/Cargo.toml; check.sh already uses -D warnings. No pedantic/nursery/restriction groups.
- [ ] Document rationale and fixed Tauri provenance in rust/tauri/README.md; run tests.

## Task 2: Swift
- [ ] Add actual SwiftLint cases for identical_operands, discarded_notification_center_observer, unhandled_throwing_task, balanced_xctest_lifecycle, empty_xctest_method; violations must fail with matching rule ID; corrected cases pass.
- [ ] Add formatter→lint cases for multiline collections, long strings and idempotent formatting for both leaves; verify RED.
- [ ] Add five opt-in rules to swift/{macos,ios}/.swiftlint.yml. Disable trailing_comma and line_length, owned by swift-format. Keep current formatter files and compiler settings.
- [ ] Update existing static assertions allowing these two documented exceptions; update both READMEs. Verify actual tools and existing suites.

## Task 3: Luau
- [ ] Add pinned luau-lsp cases for unused local (lint-only): defect nonzero, normal/intentional underscore-unused code exit 0; verify RED.
- [ ] Add lintErrors=true to roblox/rojo/.luaurc; keep strict and default lint selection, do not enable '*'. Selene already fails on warnings; keep Selene/StyLua unchanged.
- [ ] Update existing static config expectation and README with pinned upstream exit behavior; run new tests and existing suite.

## Verification
- [ ] Run new real-tool suite, native static suite and relevant existing native suites without installation.
- [ ] Use existing approved seed/caches read-only; copy only required seeds into worktree. Missing prerequisites stop that suite and are reported.
- [ ] Run TypeScript static/full suite if prerequisites permit without installs; report omissions.
- [ ] Diff review, git diff --check; report exact outputs and unverified ranges. No commit/push unless separately requested.

## Unresolved questions
None. Unexpected missing tools or required installs are blockers, not permission to install.

## Execution evidence
- Implementation applied in feat/native-quality-settings, based on 27e56e8. No commits, merge, push or installation.
- New real-tool tests: pre-change 18 rejecting/compatibility subcases failed as expected; post-change 4 grouped tests passed. Fixed Rust1.92, SwiftLint0.65.1, selected Xcode swift-format and luau-lsp1.69 exercised.
- Combined quality/native static verification: 23 tests, OK. TypeScript structure/readme checks: 4 passed, 0 failed.
- Existing Luau regression: 24 tests, OK; log .verification/roblox-regression.log.
- Existing macOS Swift app regression: 10 tests, OK; log .verification/macos-regression.log.
- Full Tauri suite omitted: approved-resolution prerequisite absent. TypeScript dependency suites omitted: node_modules absent and installations excluded. iOS app/Simulator suite not run; both iOS/macOS lint configurations were exercised.
- git diff --check: exit 0.
- Independent review: workflow f63c7676-918a-48e7-9157-a59b46e4ee37, child 3ed34a2f-30b9-4158-bdf6-32bd8c993f2f; completed, no Critical/Important/Minor findings. Reviewer did not rerun tests; parent owns execution evidence.
- First reviewer workflow bdfc2bd6-fc26-4aa2-aa47-43d426020164 timed out at 180s; child stopped and resume rejected. Same-role read-only retry above completed. No CLI/protocol fallback.
