# カバレッジ下限を commit 時に検査する Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rust ゲームサーバー3つと TypeScript 4テンプレートで、カバレッジ下限を pre-commit（と pre-push）で検査する。

**Architecture:** Rust は `scripts/check.sh` の `commit` 段に `coverage` を入れ、`test` 段を統合（テスト1回）。TS は `vitest.config.ts` で coverage を常時有効化 → 既存 `pnpm test` → `pnpm check` → pre-commit/pre-push にそのまま乗る。

**Tech Stack:** cargo-llvm-cov 0.9.1 + nextest 0.9.150 / Vitest 5.0.3 + `@vitest/coverage-v8` 5.0.3、Husky 9.1.7

**Spec:** 本会話での決定（下記 Global Constraints）

## Context

- 現状: Rust の coverage は push 時のみ（`check.sh push`）。TS はカバレッジ計測なし。
- 要望: Rust・TS とも commit 時に下限を検査。

## Global Constraints

- 作業は worktree `feat/coverage-on-commit` で行う。main 直編集しない
- Rust 対象: `rust/game-room` / `game-realtime` / `game-social` のみ。`rust/tauri` は対象外
- Rust 下限: 行カバレッジ 90%（`line_floor=90`、`--fail-under-lines`）。指標は lines のみ維持
- Rust commit 段: `format lint deps coverage`（`test` 段は commit/push から外し、coverage 段で nextest＋doctest を1回）。`test` 段は単独実行用に残す
- Rust push/all 段: `format lint deps coverage advisories build`
- TS 対象: `typescript/library` / `node` / `web` / `web-game-3d`
- TS 下限: lines / branches / functions / statements すべて 90
- TS 集計対象: `src/**` 全体（未 import ファイルも 0% で数える）。テストできない箇所は利用者が `/* v8 ignore ... */` で明示的に外す
- TS provider: v8。`@vitest/coverage-v8` は vitest と同じ 5.0.3 に固定
- `game-social` の check.sh は SQLX 行以外 realtime と完全一致を保つ（`test_push_stages_identical_in_all_leaves`）
- Co-Authored-By 等の AI 帰属行を付けない

## Review Focus

1. 失敗テストが coverage 段で落ちたとき、「下限割れ」と誤表示しない（既存 `test_failing_test_under_coverage_is_not_a_threshold_miss` を commit でも確認）
2. Rust でテスト0件の commit が coverage 段で `no tests to run` により止まる
3. TS で `src` 内の colocated test（`src/**/*.test.ts`）が集計対象に入らず、下限を不当に下げない
4. TS で src に未テストのファイルが1つ増えると `pnpm test`（＝ commit）が下限エラーで止まる
5. web-game-3d の検証用ゲーム（ブラウザ入口のみ src）が ignore コメントで通り、集計対象0件でも誤って失敗/素通りしない

---

### Task 1: Rust — commit 段に coverage を統合

**Files:**
- Modify: `rust/game-realtime/scripts/check.sh`（room・social にも同一変更をコピー）
- Modify: `rust/game-{room,realtime,social}/README.md`（「チェック」節・段の表・hook の説明）
- Modify: `rust/README.md`（commit/push の説明があれば）
- Test: `tests/native/test_rust_game.py`、`tests/native/test_static_rust_game.py`

**Interfaces:**
- Produces: `check.sh commit` の出力順 `stage: format` → `lint` → `deps` → `coverage`。`run_doctests()` 関数（test 段と coverage 段で共用）

- [ ] **Step 1: テストを先に直す**
  - `RealtimeCommitGateTests.test_clean_workspace_without_dependencies_passes`: 段順 `("format","lint","deps","coverage")`、`stage: test` が出ないこと
  - `test_zero_tests_rejected`: `stage: coverage` と `no tests to run`
  - `test_unused_dependency_rejected` / `test_failure_stops_later_stages`: `assertNotIn("stage: coverage")`
  - `RoomAndSocialTests.test_room_and_social_clean_commit_passes`: 段名 `coverage`
  - `PUSH_STAGES = ["format","lint","deps","coverage","advisories","build"]`
  - 新規 `test_commit_rejects_coverage_below_90`: 未テスト関数入り lib（既存の coverage 下限テストの fixture を再利用）で `commit` が非0、stderr に `error: line coverage below 90% (--fail-under-lines 90)`
  - static: README に `sh scripts/check.sh commit   # format → lint → deps → coverage` 相当の文言
- [ ] **Step 2: 失敗を確認** — `pnpm test:native:rust-game` / `pnpm test:native:static` → 上記が FAIL
- [ ] **Step 3: check.sh 変更**
  - `commit) stages='format lint deps coverage'`、`push|all) stages='format lint deps coverage advisories build'`
  - doctest 部分を `run_doctests()` に切り出し、`test` 段と `check_coverage` 成功後の両方で呼ぶ
  - README の表・コマンド例・「push 前に…」の記述を更新。下限の理由欄に「commit 時に検査」と追記
  - room/social へ同一内容を反映（social は SQLX 行を保持）
- [ ] **Step 4: 通過確認** — `pnpm test:native:static` と `pnpm test:native:rust-game` が PASS（rust-game は advisories のためネットワーク要）
- [ ] **Step 5: Commit** — `feat: run Rust coverage gate on commit`

### Task 2: TypeScript — Vitest カバレッジ下限 90%

**Files:**
- Modify: `typescript/{library,node,web,web-game-3d}/vitest.config.ts`
- Modify: `typescript/*/package.json`（devDependencies に `"@vitest/coverage-v8": "5.0.3"`）
- Modify: ルート `package.json`（同じ devDependency を追加）＋ `pnpm-lock.yaml`（`pnpm install` で更新）
- Modify: `typescript/*/README.md`（`pnpm test` 行・品質ゲート節に下限と ignore の書き方）
- Modify: `tests/game3d-fixture.mjs`（`src/index.ts` 先頭に v8 ignore コメント）
- Create: `tests/coverage.test.mjs`（ルート `package.json` の `test:integration` に追加）
- Modify: `tests/common.test.mjs`（静的検査）、必要なら `tests/readme.test.mjs`

**Interfaces:**
- Produces: `vitest.config.ts` の `test.coverage = { enabled: true, provider: "v8", include: ["src/**/*.{ts,mts,cts,tsx}"], reporter: ["text"], thresholds: { lines: 90, branches: 90, functions: 90, statements: 90 } }`。`test.include` に一致する src 内テストは集計外（Vitest 既定で外れなければ `exclude` に同じ glob を明記）

- [ ] **Step 1: テストを先に書く**
  - `common.test.mjs`: 4テンプレートとも devDependency `@vitest/coverage-v8` = `5.0.3`、vitest.config に上記 thresholds 4つ=90 と `include` が src
  - `coverage.test.mjs`（4テンプレート各々、`copyPreset` 使用）:
    - 既定 sample で `pnpm test` 成功（100%）
    - `src/extra.ts` に未テスト関数を追加 → `pnpm test` 非0、出力が `/does not meet (global )?threshold \(90%\)/` に一致
    - library: `src/index.test.ts` を置いても通る（colocated test が集計外）
    - library: commit gate（`node check-commit.mjs` 経由の既存ヘルパー）で上記未テストファイルを stage → 拒否
- [ ] **Step 2: 失敗を確認** — `node --test tests/common.test.mjs tests/coverage.test.mjs` → FAIL
- [ ] **Step 3: 実装** — 上記 config・依存・README・fixture 更新。ignore コメントの書式は Vitest 5.0.3 の v8 provider で実際に効くものを確認して採用（`/* v8 ignore file -- @preserve */` を第一候補）。`pnpm install` でルート lock 更新（`minimumReleaseAge` を満たすこと）
- [ ] **Step 4: 通過確認** — `pnpm test`（static＋integration 全体）が PASS。特に `game3d-integration` と `strict-lint`
- [ ] **Step 5: Commit** — `feat: enforce 90% Vitest coverage in TypeScript presets`

### Task 3: 仕上げ

- [ ] `git fetch origin main && git merge origin/main`、`pnpm test` と `pnpm test:native:static` 再実行、出力を添えて報告
- [ ] 計画書を `docs/superpowers/plans/2026-11-01-coverage-on-commit.md` として worktree に保存・コミット

## 検証（end-to-end）

- Rust: `pnpm test:native:rust-game`、`pnpm test:native:static`
- TS: `pnpm test`
- 手動: library を一時ディレクトリへ copy → Husky 有効化 → 未テスト関数を commit → 下限エラーで拒否されること

## 未解決の質問

- なし（Exa のクレジット切れのため Web 調査は未実施。Vitest 仕様はローカルの 5.0.3 型定義で確認: `coverage.include` 既定は「テストが読んだファイルのみ」）
