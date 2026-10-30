# Rust ゲームサーバー3 leaf 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `rust/game-realtime`・`rust/game-room`・`rust/game-social` の3つの品質設定 leaf を追加し、macOS の実ツールで正常系・異常系を確かめます。

**Architecture:** まず `game-realtime` で共通設定と `scripts/check.sh` を完成させ、実ツールで検証します。次に room と social を同じ構成で作り、種類ごとの差分（lint・禁止 API・ban・release）だけを変えます。検証は Git 管理外の `.verification/native/rust-game/` に隔離した RUSTUP_HOME・CARGO_HOME・tools で行い、global 設定を変えません。

**Tech Stack:** Rust 1.99.1（edition 2024、resolver 3）、Clippy、rustfmt、cargo-nextest、cargo-deny、cargo-shear、cargo-llvm-cov、POSIX shell、Husky 9.1.7、Node（check-commit.mjs）、Python 3.11+ unittest

**Spec:** `docs/superpowers/specs/2026-10-30-rust-game-servers-design.md`（ユーザー承認済み、2026-10-30）

## Global Constraints

- 配布は設定・README・LICENSE・check 補助・Husky 一式だけ。`.rs`・Cargo.lock・fixture・cache を leaf に置かない。
- 各 leaf は自己完結。親・兄弟のファイルを参照しない。README の相対リンクは leaf 内で完結する。
- Rust は 1.99.1（実装開始時に最新 stable を確認し、新しければそれに置き換えて spec 3.1 の表も更新。ユーザー承認済み）。`rust-version = "1.99"`、edition 2024、`resolver = "3"`。
- tool の版も同様に最新を確認して固定する: cargo-nextest 0.9.150、cargo-deny 0.20.2、cargo-shear 1.14.0、cargo-llvm-cov 0.9.1（調査時点）。
- 導入は `.verification/native/rust-game/{rustup,cargo,tools}` のみ。`~/.rustup`・`~/.cargo`・global Git 設定を変えない。
- check.sh は tool を導入しない・自動 fix しない・自動 stage しない。不足・版違い・source なし・テスト0件・lock なしは非0。
- ライセンス許可: MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause、ISC、Unicode-3.0、Zlib のみ。
- カバレッジ下限は行 90%（`--fail-under-lines 90`）。
- 既存 `rust/tauri` の内容と挙動は変えない。
- commit は feature branch `feat/rust-game-servers` のみ。AI 帰属行を付けない。

## Review Focus

1. 依存を1つも持たない利用直後の workspace で、`allow-invalid` の付いた禁止パスが警告を出さず check が通る（Task 2 `test_clean_workspace_without_dependencies_passes`）。
2. `[lints] workspace = true` を書き忘れた member crate が lint を素通りしない（Task 2 `test_member_without_workspace_lints_rejected`）。
3. test 内の `unwrap` は通り、本体の `unwrap` は落ちる（Task 2 `test_unwrap_allowed_only_in_tests`）。
4. ネットワーク切断時に pre-push の advisories 失敗が「取得できない」と分かる文言で止まる（Task 3 `test_advisories_offline_failure_is_explained`）。
5. sqlx を使っていない game-social で `.sqlx/` がなくても check が通る（Task 4 `test_social_without_sqlx_passes`）。

---

### Task 1: 隔離した検証環境とツール導入

**Files:**
- Create: `tests/native/rust_game_helpers.py`
- Test: `tests/native/test_rust_game_env.py`

**Interfaces:**
- Produces: `CACHE = ROOT / ".verification/native/rust-game"`、`LEAVES = ("game-realtime", "game-room", "game-social")`
- Produces: `game_env(cwd: Path) -> dict[str, str]`（HOME=`cwd/home`、RUSTUP_HOME=`CACHE/rustup`、CARGO_HOME=`CACHE/cargo`、CARGO_TARGET_DIR=`CACHE/targets/<cwd.name>`、PATH 先頭に `CACHE/tools/bin`、`RUSTUP_AUTO_INSTALL=0`、`CARGO_NET_OFFLINE=true`）
- Produces: `copy_leaf(leaf: str, prefix: str) -> Path`（`CACHE/fixtures/<prefix>-XXXX/project` に leaf を複製）
- Produces: `run_game(command: list[str], cwd: Path, *, online: bool = False) -> CompletedProcess[str]`（`online=True` のときだけ `CARGO_NET_OFFLINE` を外す。ログと JSON を `CACHE/logs/` へ。rust_helpers.run_rust と同じ形式）

- [ ] **Step 1: 失敗するテストを書く** — `test_env_is_isolated`: `game_env` の RUSTUP_HOME・CARGO_HOME・HOME がすべて `CACHE` か fixture の下にあり、`~/.rustup`・`~/.cargo` を含まないこと。`test_toolchain_and_tools_present`: `run_game(["rustup","run",TOOLCHAIN,"rustc","--version"])` が `rustc 1.99.1 ` で始まり、`cargo nextest --version`・`cargo deny --version`・`cargo shear --version`・`cargo llvm-cov --version` の出力が Global Constraints の版を含むこと。`TOOLCHAIN` と各版はファイル先頭の定数にする。
- [ ] **Step 2: 失敗を確認** — `python3 -m unittest tests.native.test_rust_game_env -v` → helper 不在で FAIL。
- [ ] **Step 3: 最新版を確認** — `curl -s https://static.rust-lang.org/dist/channel-rust-stable.toml | head`、`curl -s https://crates.io/api/v1/crates/<name>` で4ツールの `max_stable_version` を取得し、新しければ定数と spec 3.1 を更新する。
- [ ] **Step 4: helper を実装し、隔離環境に導入する** — `RUSTUP_HOME`・`CARGO_HOME` を CACHE にして `rustup toolchain install <版> --profile minimal -c rustfmt,clippy,llvm-tools`。ツールは `cargo install --locked --root CACHE/tools <name>@<版>`。実行したコマンド・版・所要時間を `CACHE/install-record.json` に書く。
- [ ] **Step 5: 成功を確認** — 同じ unittest → PASS（2 tests）。
- [ ] **Step 6: Commit** — `git add tests/native/rust_game_helpers.py tests/native/test_rust_game_env.py && git commit -m "test: add isolated Rust game-server verification environment"`

### Task 2: game-realtime の共通設定と check.sh（format・lint・deps・test）

**Files:**
- Create: `rust/game-realtime/{README.md,LICENSE,.editorconfig,.gitignore,.node-version,rust-toolchain.toml,rustfmt.toml,clippy.toml,deny.toml,Cargo.toml,.config/nextest.toml,.cargo/config.toml,scripts/check.sh,check-commit.mjs,package.json,pnpm-workspace.yaml,.husky/pre-commit,.husky/pre-push}`
- Create: `tests/native/test_static_rust_game.py`、`tests/native/test_rust_game.py`

**Interfaces:**
- Consumes: Task 1 の `copy_leaf`、`run_game`
- Produces: `scripts/check.sh <format|lint|deps|test|coverage|advisories|build|commit|push>`。`commit` = format→lint→deps→test、`push` = commit＋coverage→advisories→build。最初の失敗で止まり、`stage: <名前>` を出力する。
- Produces（テスト用）: `write_crate(root: Path, name: str, lib: str, *, workspace_lints: bool = True, deps: str = "") -> None`（`crates/<name>/Cargo.toml` と `src/lib.rs` を作る。`test_rust_game.py` 内）

- [ ] **Step 1: 最初に Clippy 1.99.1 の `allow-invalid` を確かめる（spike）** — 隔離環境の一時 crate で、`clippy.toml` に `disallowed-methods = [{ path = "sqlx::query", allow-invalid = true }]` を置き、依存なしで `cargo clippy -- -D warnings` が0になるか見る。結果を `CACHE/spike-allow-invalid.log` に残す。0にならなければ作業を止めて報告する（spec 8章のリスク）。
- [ ] **Step 2: 静的テストを書く** — `test_static_rust_game.py` の `test_common_contract`（3 leaf で subTest。leaf 不在は skip せず FAIL）:
  - toolchain: `channel == "1.99.1"`、components が `{"rustfmt","clippy","llvm-tools"}`、profile `minimal`
  - Cargo.toml: `"package" not in manifest`、`workspace.resolver == "3"`、`workspace.members == ["crates/*"]`、`workspace.package.edition == "2024"`、`rust-version == "1.99"`、`publish is False`
  - lints.rust: `unsafe_code == "forbid"`、`missing_docs`・`unused_must_use`・`unreachable_pub`・`unused_qualifications` が `"deny"`、`rust_2018_idioms == {"level":"deny","priority":-1}`
  - lints.clippy: `all`・`pedantic`・`nursery`・`cargo` が `{"level":"deny","priority":-1}`、spec 3.2 の restriction 18項目と tauri の3項目がすべて `"deny"`
  - profile.release: `overflow-checks is True`、`debug == "line-tables-only"`、`panic == "unwind"`
  - clippy.toml: `allow-unwrap-in-tests`・`allow-expect-in-tests`・`allow-panic-in-tests`・`allow-print-in-tests` が true、`std::thread::sleep` と `std::process::exit` が disallowed-methods にある
  - deny.toml: `licenses.allow` が Global Constraints の7つと集合で一致、`bans.multiple-versions == "deny"`、`bans.wildcards == "deny"`、deny 名に `bincode`・`fred`・`poem`・`openssl`・`openssl-sys`、`sources.unknown-registry == "deny"`、`sources.unknown-git == "deny"`
  - rustfmt.toml は tauri と同じ5項目、`check-commit.mjs` は `rust/tauri/check-commit.mjs` とバイト一致
  - `.rs` と Cargo.lock が leaf に無い、README の相対リンクが実在
- [ ] **Step 3: 失敗を確認** — `python3 -m unittest tests.native.test_static_rust_game -v` → leaf 不在で FAIL。
- [ ] **Step 4: 設定ファイルを作る** — 値は Step 2 のとおり。`.gitignore`・`.editorconfig`・LICENSE・Husky 一式・`.node-version` は tauri からコピーし、`.gitignore` には `/.sqlx/` を入れない。`.cargo/config.toml` は tauri と同じ `incompatible-rust-versions = "fallback"` のみ。`.config/nextest.toml` は `[profile.default] fail-fast = true, slow-timeout = { period = "60s", terminate-after = 2 }` と `[profile.ci]`（`fail-fast = false`）。
- [ ] **Step 5: 静的テストの成功を確認** — 同じ unittest → realtime 分 PASS（room・social は Task 4 まで FAIL のままでよい。Task 4 完了時に全 PASS）。
- [ ] **Step 6: 実ツールテストを書く** — `test_rust_game.py` の `RealtimeCommitGateTests`。各テストは `copy_leaf("game-realtime", …)` に `write_crate(root, "core", <docs つき関数1つ＋#[test]1つ>)` と `generate-lockfile --offline` を行ってから `check.sh commit` を呼ぶ:
  - `test_clean_workspace_without_dependencies_passes`: exit 0、出力に `stage: format`・`stage: lint`・`stage: deps`・`stage: test` が順に出る
  - `test_unwrap_allowed_only_in_tests`: `#[test]` 内の unwrap は exit 0、本体の unwrap は非0で stderr に `unwrap_used`
  - 非0とその診断名を確かめるもの（1テスト1件）: `test_print_rejected`（`print_stdout`）、`test_missing_docs_rejected`（`missing_docs`）、`test_unsafe_rejected`（`unsafe_code`）、`test_pedantic_rejected`（`must_use_candidate`）、`test_thread_sleep_rejected`（`disallowed_methods`）、`test_format_rejected`（`stage: format` の後に非0）
  - `test_member_without_workspace_lints_rejected`: `workspace_lints=False` の crate で非0、stderr に `workspace = true`
  - `test_unused_dependency_rejected`: path 依存の偽 crate を使わずに宣言 → `cargo shear` で非0
  - `test_zero_tests_rejected`: `#[test]` なし → 非0
  - `test_missing_lock_or_tool_rejected`: Cargo.lock 削除で非0、PATH から tools/bin を外すと `cargo-nextest` 不足の文言で非0
  - `test_failure_stops_later_stages`: lint で落ちたとき出力に `stage: test` が無い
- [ ] **Step 7: 失敗を確認** — `python3 -m unittest tests.native.test_rust_game.RealtimeCommitGateTests -v` → check.sh 不在で FAIL。
- [ ] **Step 8: check.sh を実装する** — tauri の check.sh の toolchain 選択（`rustup toolchain list` → full 名 → `rustup which`、rustup 1.28.2 以上、`RUSTUP_AUTO_INSTALL=0`）を版だけ変えて使う。`cargo-nextest`・`cargo-deny`・`cargo-shear` は `command -v` で探し、`--version` が固定版でなければ fail。各段のコマンドは spec 5章の表どおり。lint 段では `cargo metadata --no-deps --format-version 1` の各 member の manifest に `[lints]` と `workspace = true` があるかを awk で確かめる。Cargo.lock なしは fail。
- [ ] **Step 9: 成功を確認** — 同じ unittest → 全 PASS。ログは `CACHE/logs/` に残る。
- [ ] **Step 10: README を書く** — tauri README の章立て（導入表／tool と lock／チェック／検証範囲）に合わせる。加えて「厳しい lint を外すときは `#[expect(lint, reason = "…")]`」「`multiple_crate_versions` の外し方」「カバレッジ下限の変更場所」「推奨スタック（レポート2章の表を要約）」「macOS/Linux の POSIX shell のみ、check.ps1 なし」を書く。
- [ ] **Step 11: Commit** — `git add rust/game-realtime tests/native/test_static_rust_game.py tests/native/test_rust_game.py && git commit -m "feat: add strict Rust realtime game-server quality settings"`

### Task 3: push 段（coverage・advisories・build）と realtime の差分

**Files:**
- Modify: `rust/game-realtime/{Cargo.toml,clippy.toml,deny.toml,scripts/check.sh,README.md}`
- Modify: `tests/native/test_static_rust_game.py`、`tests/native/test_rust_game.py`

**Interfaces:**
- Consumes: Task 2 の `write_crate`、check.sh の段
- Produces: `RealtimePushGateTests`、`RealtimeRuleTests`

- [ ] **Step 1: 静的テストを足す** — `test_realtime_rules`: lints.clippy に `arithmetic_side_effects`・`cast_possible_truncation`・`cast_sign_loss`・`cast_precision_loss`・`cast_possible_wrap`・`cast_lossless`・`as_conversions`・`indexing_slicing`・`float_cmp` が `"deny"`、`float_arithmetic` は無い。clippy.toml の disallowed-methods に `std::time::SystemTime::now`・`std::time::Instant::now`、disallowed-types に `std::hash::RandomState`・`std::collections::hash_map::RandomState`・`std::collections::HashMap`・`std::collections::HashSet`。deny.toml の deny に `laminar`。profile.release に `lto == "fat"`、`codegen-units == 1`。
- [ ] **Step 2: 実ツールテストを書く** —
  - `RealtimePushGateTests.test_push_passes_with_full_coverage`: exit 0、`stage: coverage`・`stage: advisories`・`stage: build` が出る（`run_game(..., online=True)`。RustSec DB の取得先 `https://github.com/rustsec/advisory-db` を記録）
  - `test_coverage_below_90_rejected`: テストしない関数を足して行カバレッジを 90% 未満にする → 非0、stderr に `fail-under-lines` か `90`
  - `test_advisories_offline_failure_is_explained`: `CARGO_NET_OFFLINE=true` のまま push → 非0、stderr に `advisory database could not be fetched (network required)`（check.sh が出す文言）
  - `RealtimeRuleTests`（1テスト1件、非0と診断名）: `test_unchecked_add_rejected`（`arithmetic_side_effects`）、`test_as_cast_rejected`（`as_conversions`）、`test_indexing_rejected`（`indexing_slicing`）、`test_instant_now_rejected`（`disallowed_methods`）、`test_hashmap_new_rejected` と `test_hashmap_collect_rejected`（`disallowed_types`）、`test_instant_now_with_expect_reason_passes`（`#[expect(clippy::disallowed_methods, reason = "tick の入口")]` で exit 0）
- [ ] **Step 3: 失敗を確認** — `python3 -m unittest tests.native.test_static_rust_game tests.native.test_rust_game -v` → 新しい項目が FAIL。
- [ ] **Step 4: 実装** — 設定は Step 1 の値。check.sh の coverage 段は `cargo llvm-cov nextest --workspace --locked --no-tests=fail --fail-under-lines 90`。advisories 段は `cargo deny check advisories` の失敗出力に `failed to fetch`／`network` を含むとき、上の文言を stderr に足して非0。build 段は `cargo build --workspace --locked --release`。
- [ ] **Step 5: 成功を確認** — 同じコマンド → 全 PASS。
- [ ] **Step 6: Commit** — `git commit -am "feat: add push gates and realtime rules"`（新規ファイルがあれば add する）

### Task 4: game-room と game-social

**Files:**
- Create: `rust/game-room/`・`rust/game-social/`（Task 2 と同じファイル一覧）
- Modify: `tests/native/rust_game_helpers.py`、`tests/native/test_static_rust_game.py`、`tests/native/test_rust_game.py`

**Interfaces:**
- Produces: `write_fake_crate(root: Path, name: str, lib: str) -> str`（`vendor/<name>/` に `publish = false` の crate を作り、`[dependencies]` に入れる1行 `name = { path = "../../vendor/<name>" }` を返す。偽 crate は member に含めない＝`workspace.exclude = ["vendor"]` をテスト内で足す）
- 偽 crate の中身: `tokio`（`pub mod sync { pub mod mpsc { pub fn unbounded_channel() {} } }`）、`futures`（`pub mod channel { pub mod mpsc { pub fn unbounded() {} } }`）、`sqlx`（`pub fn query(_: &str) {}`、`pub fn query_as(_: &str) {}`）、`reqwest`（`pub struct Client; impl Client { pub fn new() -> Self { Self } }`）

- [ ] **Step 1: 静的テストを足す** — `test_common_contract` が3 leaf すべてで通ること（共通ファイルは realtime とバイト一致。ただし Cargo.toml・clippy.toml・deny.toml・README.md・scripts/check.sh は除く）。`test_room_rules`: `await_holding_lock`・`await_holding_refcell_ref`・`await_holding_invalid_type`・`large_futures` が deny、disallowed-methods に `tokio::sync::mpsc::unbounded_channel`・`futures::channel::mpsc::unbounded`、deny.toml に `actix`、realtime 固有の lint・release 設定が無い。`test_social_rules`: `await_holding_lock`・`await_holding_refcell_ref` が deny、disallowed-methods に `sqlx::query`・`sqlx::query_as`・`reqwest::Client::new`、deny.toml に `native-tls`。
- [ ] **Step 2: 実ツールテストを書く** — `RoomRuleTests.test_unbounded_channel_rejected`・`test_futures_unbounded_rejected`（偽 crate、`disallowed_methods`）、`SocialRuleTests.test_raw_sqlx_query_rejected`・`test_reqwest_client_new_rejected`（同）、`test_social_without_sqlx_passes`（依存なしで `check.sh commit` が0、`.sqlx/` 不要）、`test_social_sets_sqlx_offline`（check.sh が `SQLX_OFFLINE=true` を出力の環境表示に含める）、`test_room_and_social_clean_commit_passes`。ban の実検証: `test_banned_crate_rejected` を3 leaf で subTest — 偽 crate 名を `bincode` にして deps 段が非0、stderr に `banned`。
- [ ] **Step 3: 失敗を確認** — `python3 -m unittest tests.native.test_static_rust_game tests.native.test_rust_game -v` → room・social の項目が FAIL。
- [ ] **Step 4: 実装** — realtime を複製し、共通設定から realtime 固有の項目（Task 3 Step 1）を除いて、spec 4章の room・social の差分を足す。social の check.sh だけ、環境の準備で `SQLX_OFFLINE=${SQLX_OFFLINE:-true}` を export し、表示する。README は種類ごとの「推奨スタック」と、social の `cargo sqlx prepare` と `.sqlx/` commit の手順を書く。
- [ ] **Step 5: 成功を確認** — 同じコマンド → 全 PASS。
- [ ] **Step 6: Commit** — `git add rust/game-room rust/game-social tests/native && git commit -m "feat: add strict Rust room and social game-server quality settings"`

### Task 5: カタログ・Husky・README への登録

**Files:**
- Modify: `rust/README.md`、`README.md`（「範囲」の Rust 行と「Native の保守検証」）、`package.json`（scripts）
- Modify: `tests/native/test_catalog.py`、`tests/all-language-husky.test.mjs`

**Interfaces:**
- Produces: `pnpm test:native:rust-game` = `python3 -m tests.native.test_catalog tests.native.test_rust_game_env tests.native.test_rust_game`。`test:native:static` に `tests.native.test_static_rust_game` を足す。

- [ ] **Step 1: テストを足す** — `test_catalog.py`: `RUST_GAME_FILES`（Task 2 のファイル一覧）を定義し、`test_root_language_leaf_navigation` の rust を `['tauri','game-realtime','game-room','game-social']` に、`test_independent_copy_exact_inventory_and_local_references` に3 leaf を追加。`all-language-husky.test.mjs`: `leaves` に3つを追加（このテストの native 代替コマンドが `scripts/check.sh` を置き換える方式に3 leaf が乗るか、最初に読んで確かめる）。
- [ ] **Step 2: 失敗を確認** — `pnpm test:native:static` と `pnpm test:husky` → README 未登録で FAIL。
- [ ] **Step 3: README と package.json を更新** — `rust/README.md` に3 leaf の1行説明と使い分け（併用時は realtime を土台にする）。直下 README の「範囲」の Rust 行に3 leaf を追記し、「Native の保守検証」に `pnpm test:native:rust-game` を足す。
- [ ] **Step 4: 全体の成功を確認** — `pnpm test`、`pnpm test:native:static`、`pnpm test:husky`、`pnpm test:native:rust-game`、既存の `pnpm test:native:quality` がすべて exit 0。出力を保存する。
- [ ] **Step 5: Commit** — `git add -A rust README.md package.json tests && git commit -m "docs: register Rust game-server leaves"`

### Task 6: main への統合と scaffold-profiles への登録

**Files:**
- Modify（別リポジトリ）: `~/Code/scaffold-profiles/src/profile/skills/scaffold/references/basic-design.md`（パスは実物で確認）

- [ ] **Step 1: main を取り込む** — `git fetch origin main && git merge origin/main`。衝突があれば解消し、Task 5 Step 4 を再実行。
- [ ] **Step 2: レビュー** — whole-branch の code review を受け、指摘を直す。
- [ ] **Step 3: main へ統合（ユーザー確認のうえ）** — main worktree で `git merge --no-ff feat/rust-game-servers`。push は別途確認。
- [ ] **Step 4: scaffold-profiles を更新** — 同リポジトリで worktree を作り、言語表の Rust 行に「ゲームサーバーは `rust/game-realtime`・`game-room`・`game-social` から種類で選ぶ。Rust 1.99.1 と nextest・deny・shear・llvm-cov の導入はこの工程で承認を得て記録する」を足す。同リポジトリの手順で `dist/` を再生成し、テストを通して commit。
