# Rust Tauri Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 単体src-tauri crate向けの自己完結Rust/Tauri desktop設定を用意し、macOSで実検証します。

**Architecture:** rust/tauriをproject rootへコピーし、frontendは利用側が接続します。保守用Python fixtureは製品sourceと静的frontendを生成し、Cargo/IPC/設定境界を実検証します。Swiftは別計画で実装します。

**Tech Stack:** Rust1.92.0候補、edition2024、tauri2.12.2、tauri-build2.7.1、rustfmt、Clippy、Python3、POSIX shell/PowerShell

**Spec:** `docs/superpowers/specs/2026-10-10-native-app-settings-design.md`（ユーザーレビュー承認済み）

## Global Constraints

- 配布は設定・README・LICENSE・build/check補助だけ。製品source・fixture/cache・画像・証明書・秘密情報を配布しません。
- 各用途を自己完結させ、READMEの相対リンクとコピー先を明示します。親・兄弟設定から補完しません。
- コードは専用feature worktree、1cwdにつきwriter1人。既存main/他worktree/ユーザー変更を上書きしません。
- 依存/tool取得・OS/global設定・署名/公開/main統合・push/Profile更新は実行直前に別承認。Rustupの自動導入を勝手に起動しません。
- fixtureとHOME/cache/target/DerivedDataはtask専用Git管理外領域。無許可で消さず、実出力・版・exitを保存します。
- 検証不合格・未検証をskip/ignore-exit/validation bypassで成功扱いにしません。コミットにAI帰属行を付けません。

- Rust基準は1.92.0、edition2024。crate直接MSRV1.90でも推移依存全体を保証しません。版不整合では停止して相談します。
- macOS実検証、Windows/Linuxは未実行とREADMEへ明記します。frontend設定・モバイルは対象外です。
- unsafe_code/unused_must_useをdeny、clippy::allをwarn（priority -1）、unwrap_used/expect_used/todo/dbg_macroをdeny。checkは-D warnings。
- stable fmtは幅100・4スペース・LF・edition2024。nightly-onlyやrestriction全groupは使いません。

## Review Focus

1. Cargo commandがrust-toolchainの不足で無許可downloadを起こさない（Task1）。
2. source/test/lockなしをCargoのexit0だけで合格にしない（Task1）。
3. capability JSONだけでcustom Rust commandを保護したと説明しない（Task2）。
4. frontend distがなくてもbackend unit testをアプリ全体合格にしない（Task2）。
5. existing files/symlink/hooksを導入手順が無条件に上書きしない（Task2、統合計画）。

### Task 1: Rust品質設定と実Cargo fixture

**Files:**
- Create: `rust/README.md`、`rust/tauri/README.md`、`rust/tauri/LICENSE`
- Create: `rust/tauri/rust-toolchain.toml`、`rust/tauri/rustfmt.toml`、`rust/tauri/.editorconfig`、`rust/tauri/.gitignore`、`rust/tauri/.cargo/config.toml`
- Create: `rust/tauri/src-tauri/Cargo.toml`、`rust/tauri/scripts/check.sh`、`rust/tauri/scripts/check.ps1`
- Test/Create: `tests/native/rust_helpers.py`、`tests/native/test_static_rust.py`、`tests/native/test_rust.py`

**Interfaces:**
- Produces: `copy_rust_fixture(*, frontend: bool = True) -> Path`、`run_rust(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]`（tests/native/rust_helpers.py）。
- Produces: `scripts/check.sh [format|lint|test|build|all]`、`scripts/check.ps1 -Stage <format|lint|test|build|all>`。成功0・不合格非0、最初の失敗で停止、stage/実tool版をstdoutへ記録。
- Manifest/sourceはproject rootのsrc-tauri、cacheは `.verification/native/rust/`。checkはcallerのCARGO_HOME/CARGO_TARGET_DIRを尊重し、global設定を変更しません。

- [ ] Step 1: static testで独立コピー後のmanifest解析とrule設定、相対参照実在をassertします。実fixtureテスト名は `test_clean_rust_check`（正常0）、`test_format_rejected`、`test_unwrap_rejected`、`test_unused_result_rejected`、`test_failure_stops_build`（意図した診断/非0・後続未実行）、`test_missing_source_test_lock_or_tool_rejected`（それぞれ非0）。
- [ ] Step 2: `python3 -m unittest discover -s tests/native -p 'test_static_rust.py' -v` を実行し、新設定欠落のREDを保存します。構文/テスト自体のerrorをfeature不在の証拠にしません。
- [ ] Step 3: 取得するRust exact toolchain/components/crate・cache範囲を提示して承認します。Rustupのnamed1.92不在は、現在stableの表示だけで利用可能と推定しません。選択版/metadataをtask領域へ保存し、無許可で1.95等へ変更しません。
- [ ] Step 4: manifestは単体crate、source entryは利用側src/main.rsとsrc/lib.rsを前提にし、sourceは配布しません。crateの解決/lockをfixtureで行い、推移rust-versionが基準を超えたら止めます。release最適化・all-featuresを自動採用しません。
- [ ] Step 5: checkのformatはmanifest-path指定でcargo fmt --check、lintはcargo clippy --locked --all-targets -- -D warnings、test/buildは--locked。test前にcargo testの一覧で実test存在を検査し、0件は拒否します。無許可のtoolchain/bootstrap・自動fix・cleanを行いません。
- [ ] Step 6: Mac上で `python3 -m unittest discover -s tests/native -p 'test_rust.py' -v` を実行し、正常/異常のexit・診断・ログを保存します。checkの失敗後にbuildが実行されないことを実結果で確認します。Windows/Linux用ps1は設定・構文を確認できた範囲だけ記録し、native実行成功とは言いません。
- [ ] Step 7: `feat: add Rust quality settings for Tauri` でlocal commitします。

### Task 2: Tauri設定・command ACL・native build

**Files:**
- Create: `rust/tauri/src-tauri/build.rs`、`rust/tauri/src-tauri/tauri.conf.json`、`rust/tauri/src-tauri/capabilities/main.json`
- Modify: `tests/native/rust_helpers.py`、`tests/native/test_static_rust.py`、`tests/native/test_rust.py`、`rust/tauri/README.md`

**Interfaces:**
- Consumes: Task1 copy/run/check API。Configはfrontend dist/dev URLとproduct/window identifierを利用側に確認させます。
- Produces: 読み取り/比較可能なJSON capability contractとTauri build helper。custom commandのAppManifest接続箇所を示し、任意commandの安全性を保証しません。

- [ ] Step 1: `test_capability_is_explicit_local_main_only`、`test_allowed_and_denied_ipc`、`test_custom_command_boundary_not_plugin_only`、`test_missing_frontend_native_build_rejected` を作ります。JSONだけの成功でなく、fixture commandの許可/未許可の実結果をassertします。
- [ ] Step 2: 新testのREDを記録します。必要なmacOS native依存が不足なら、無断導入せず不足と部分検証を報告します。
- [ ] Step 3: capabilityはmain identifier/window、desktop platforms、必要なcore permissionだけを初期候補にし、configで明示有効化します。windows:*、remote、fs/shell/process/updaterの広い許可や作者のURL/keyは含めません。
- [ ] Step 4: build.rsはResultでerrorを伝搬し、AppManifest::commands接続箇所を記載します。製品command名は空のまま安全完成と宣言せず、READMEで登録/permission/input/scope確認を必須にします。CSPとfrontend接続変数も利用側の判断として記載します。
- [ ] Step 5: fixtureのbackend testとnative buildを実行し、結果を分けます。mock runtimeはnative WebView/E2Eではないことをレポートに書きます。UI起動はこの計画の自動操作では行いません。
- [ ] Step 6: Rust全testを再実行し、`feat: add explicit Tauri configuration boundaries` でcommitします。未検証platformはREADME/受入れに残します。

## Handoff

統合計画 `2026-10-10-native-app-settings.md` へ、commit、static/runtime test出力、OS別合格/未実行、dependency/tool版と残リスクを渡します。Swift実装はこのRust計画のcopy/run APIへ依存しません。
