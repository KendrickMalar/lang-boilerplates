# Rust ゲームサーバー3種の品質設定 — 設計

> 作成日・最終更新: 2026-10-30
> 出所: ユーザーとの質疑（2026-10-30）、調査レポート `reports/Rust ゲームサーバー構成調査.md`（main checkout の Git 管理外。調査メモは `research_notes/Rust ゲームサーバー構成調査/`）、既存 `rust/tauri` leaf。
> 目的: スマホゲーム向けの Rust サーバーを作るときに、ゲームの種類に合った「厳しい品質設定」をコピーして使えるようにします。

## 目次

1. 要約と決定事項
2. 配置・コピー契約
3. 共通の品質設定
4. 種類ごとの差分
5. チェックと Git フック
6. 合格基準・検証範囲
7. 次のアクション
8. リスク・残論点
9. 参考元と決定ログ

## 1. 要約と決定事項

`rust/` の下に、ゲームの種類ごとの leaf を3つ追加します。リアルタイム対戦用の `game-realtime`、ルーム制の `game-room`、ソシャゲ型 API の `game-social` です。中身は品質設定だけで、製品の依存（axum、sqlx など）は入れません。3つとも同じ「最大級に厳しい」共通設定を持ち、種類ごとに禁止 API・ban する crate・release 設定を足します。

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| leaf の数 | **種類ごとに3つ** | ユーザー選択（2026-10-30）。レポートの推奨（1つ）から変更。1 leaf＝1用途で自己完結する既存の型に合う。 |
| 中身 | **品質設定のみ** | ユーザー選択。製品 source・依存・Cargo.lock は配布しない（tauri leaf と同じ）。 |
| 厳しさ | **最大級** | ユーザー選択。pedantic・nursery・cargo を deny、主要な restriction lint を deny、警告0。 |
| toolchain | **1.99.1（新 leaf のみ）** | ユーザー選択。sqlx 0.9（MSRV 1.94）・lightyear（1.97.1）の最新版が使える。tauri の 1.92.0 は変えない。 |
| 種類ごとの差 | **禁止 API・ban・release 設定で差をつける** | ユーザーが案を承認（4章）。 |
| カバレッジ | **行 90% 以上を push 前に強制** | ユーザー選択。cargo-llvm-cov を使う。 |
| ライセンス | **小さな明示リスト** | MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause、ISC、Unicode-3.0、Zlib のみ。ほかは利用側が追加する。 |
| 構成 | **virtual workspace（`crates/*`）** | 1 crate のサーバーで終わらないため（レポート4章）。tauri leaf の単体 crate とは違う。 |
| ツール導入 | **check.sh は導入しない。版が違えば止まる** | 既存 leaf と同じ。保守検証のための導入は、この Mac に固定版で入れることをユーザーが承認済み（2026-10-30）。 |

## 2. 配置・コピー契約

3つの leaf は同じファイル構成です。

```text
rust/
  README.md                  入口（3 leaf の使い分けを追記）
  game-realtime/ game-room/ game-social/
    README.md                配布ファイル、コピー先、導入、チェック、フック、検証範囲、推奨スタック
    LICENSE / .editorconfig / .gitignore / .node-version
    rust-toolchain.toml
    rustfmt.toml
    clippy.toml
    deny.toml
    Cargo.toml               virtual manifest（[workspace]・[workspace.package]・[workspace.lints]・[profile.*]）
    .config/nextest.toml
    .cargo/config.toml
    scripts/check.sh
    check-commit.mjs         tauri leaf と同じ内容
    package.json / pnpm-workspace.yaml   Husky 9.1.7
    .husky/pre-commit / .husky/pre-push
```

- leaf は親や兄弟に依存しません。そのフォルダだけをコピーすれば動きます。
- 製品 source・crate・Cargo.lock・fixture は配布しません。利用側は `crates/<名前>/` に crate を作り、`[lints] workspace = true` を書きます。
- 3種類を1つのサーバーで併用する場合は、いちばん厳しい `game-realtime` を土台にし、他の leaf の禁止 API を足す手順を README に書きます（自動統合はしない）。
- `check-commit.mjs` は tauri leaf と同じ内容にします。共通化はせず、各 leaf にコピーを置きます（自己完結のため）。
- リポジトリ直下 README の「範囲」と `rust/README.md` に3行を追加します。

## 3. 共通の品質設定

### 3.1 版の固定

| ツール | 版 | 確認方法（check.sh の事前確認） |
| --- | --- | --- |
| Rust | 1.99.1（rustfmt・clippy・llvm-tools） | tauri leaf と同じ `rustup toolchain list` → full 名で `rustup which` |
| cargo-nextest | 0.9.150 | `cargo nextest --version` |
| cargo-deny | 0.20.2 | `cargo deny --version` |
| cargo-shear | 1.14.0 | `cargo shear --version` |
| cargo-llvm-cov | 0.9.1 | `cargo llvm-cov --version` |
| Husky | 9.1.7 | package.json |

版はレポートの調査時点（2026-10-30）の最新です。実装時に crates.io で再確認し、新しい版があればそれを固定して入れ、この表を更新します（ユーザー承認済み、2026-10-30）。

### 3.2 Cargo.toml（virtual manifest）

- `resolver = "3"` を明示します（virtual manifest では edition から推論されない）。
- `[workspace.package]`: `edition = "2024"`、`rust-version = "1.99"`、`publish = false`。
- `[workspace.lints.rust]`: `unsafe_code = "forbid"`、`missing_docs = "deny"`、`unused_must_use = "deny"`、`unreachable_pub = "deny"`、`unused_qualifications = "deny"`、`rust_2018_idioms = "deny"`（group、priority -1）。
- `[workspace.lints.clippy]`:
  - group: `all`・`pedantic`・`nursery`・`cargo` を `deny`（priority -1）。
  - restriction から個別に deny: `unwrap_used`、`expect_used`、`panic`、`todo`、`unimplemented`、`unreachable`、`dbg_macro`、`print_stdout`、`print_stderr`、`exit`、`get_unwrap`、`allow_attributes`、`allow_attributes_without_reason`、`undocumented_unsafe_blocks`、`mem_forget`、`string_slice`、`rc_mutex`、`lossy_float_literal`。
  - tauri leaf の3項目（`redundant_clone`、`assigning_clones`、`or_fun_call`）も含めます。
  - `cargo` group の `multiple_crate_versions` は、依存が増えると避けられないことがあります。deny のまま置き、外すときは理由つきで README に書きます。
- `[profile.release]`: `overflow-checks = true`、`debug = "line-tables-only"`、`panic = "unwind"`（サーバーは panic を受け止めて続けるため）。
- `[profile.dev]`: 既定のまま。

### 3.3 clippy.toml

- test 内だけ `unwrap`・`expect`・`panic`・`print` を許可します（`allow-unwrap-in-tests` など）。
- `disallowed-methods` / `disallowed-types` は種類ごとの差分（4章）。依存に無いパスは `allow-invalid = true` を付け、依存を入れる前でも警告にならないようにします（実装時に Clippy 1.99 での挙動を確かめる）。
- 共通の禁止: `std::thread::sleep`（async の中で止まる）、`std::process::exit`。

### 3.4 rustfmt.toml

tauri leaf と同じ stable 項目（幅100・4スペース・LF・edition 2024・reorder_imports）。nightly 限定の項目は入れません。

### 3.5 deny.toml

- `[graph] all-features = true`。`targets` は書きません（利用側のデプロイ先で決める。README で例示）。
- `[advisories]`: unmaintained も含めて拒否。yanked も拒否。
- `[licenses]`: 1章の明示リスト。`confidence-threshold = 0.93`。
- `[bans]`: `multiple-versions = "deny"`、`wildcards = "deny"`。共通の ban: `bincode`（RUSTSEC-2025-0141）、`fred`、`poem`、`openssl`、`openssl-sys`。
- `[sources]`: crates.io 以外の registry と git 依存を拒否。

### 3.6 .config/nextest.toml

`default` と `ci` の profile。`fail-fast`、`slow-timeout`、0件のテストは失敗（`--no-tests=fail` を check.sh で明示）。doctest は nextest で動かないので別段で `cargo test --doc` を回します。

## 4. 種類ごとの差分

| leaf | 追加の lint（deny） | disallowed（clippy.toml） | deny.toml の追加 ban | release |
| --- | --- | --- | --- | --- |
| game-realtime | `arithmetic_side_effects`、`cast_possible_truncation`・`cast_sign_loss`・`cast_precision_loss`・`cast_possible_wrap`・`cast_lossless`、`as_conversions`、`indexing_slicing`、`float_cmp`、`float_arithmetic` は対象外（ゲームで使うため） | `std::time::SystemTime::now`、`std::time::Instant::now`（tick の時刻は引数で渡す）、`disallowed-types` で `std::hash::RandomState`・`std::collections::hash_map::RandomState`・`std::collections::HashMap`・`std::collections::HashSet`（既定 hasher は実行ごとに順序が変わる。`new`・`default`・`collect` すべてを止める。固定 hasher か `BTreeMap` を使う） | `laminar`（2021 で停止） | `lto = "fat"`、`codegen-units = 1` |
| game-room | `await_holding_lock`、`await_holding_refcell_ref`、`await_holding_invalid_type`、`large_futures` | `tokio::sync::mpsc::unbounded_channel`・`futures::channel::mpsc::unbounded`（背圧なし） | `actix`（アクター。2024 で停止） | 共通のまま |
| game-social | `await_holding_lock`、`await_holding_refcell_ref` | `sqlx::query`・`sqlx::query_as`（非マクロ。生 SQL 文字列を避けマクロで型検査）、`reqwest::Client::new`（timeout なし） | `native-tls`（rustls に限定） | 共通のまま |

- realtime の `Instant::now` 禁止は厳しい選択です（考察）。tick ループの入口1か所だけ、理由つき `#[expect]` で許す使い方を README に書きます。
- `float_arithmetic` はゲームの物理で必須なので、どの leaf でも入れません（筆者の判断）。
- room で `tokio::spawn` は禁止しません。代わりの `tokio::task::Builder` は `--cfg tokio_unstable` が要り、leaf から全依存の rustflags を変えることになるためです（筆者の判断、builder check を受けて変更）。
- social の sqlx マクロは compile 時に DB か `.sqlx/` が要ります。game-social の check.sh は `SQLX_OFFLINE=true` を既定にし、`cargo sqlx prepare` で作った `.sqlx/` の commit を README で必須にします（筆者の判断）。sqlx をまだ使っていないときは何もしません。

## 5. チェックと Git フック

`scripts/check.sh <stage>`（`format|lint|deps|test|coverage|build|commit|push|all`）。最初の失敗で止まります。tool 不足・版違い・source なし・テスト0件は失敗です。

| 段 | 中身 | ネットワーク |
| --- | --- | --- |
| format | `cargo fmt --all --check` | なし |
| lint | `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`、全 member が `[lints] workspace = true` を持つかの検査 | なし |
| deps | `cargo shear`、`cargo deny --offline check bans licenses sources` | なし |
| test | `cargo nextest run --workspace --locked --no-tests=fail`、`cargo test --doc --workspace --locked` | なし |
| coverage | `cargo llvm-cov nextest --workspace --locked --fail-under-lines 90` | なし |
| advisories | `cargo deny check advisories`（RustSec DB を取得） | **あり** |
| build | `cargo build --workspace --locked --release` | なし |

- pre-commit: `check-commit.mjs` → format・lint・deps・test。
- pre-push: `check-commit.mjs push` → 上記＋coverage・advisories・build。
- 取得先（RustSec の GitHub）を README に明記します。
- 自動 format・自動 stage・tool の自動導入はしません（既存方針）。

## 6. 合格基準・検証範囲

- 静的検査（Python、`tests/native/`）: 3 leaf の配布ファイル一覧、toolchain・lint・deny.toml の値、種類ごとの差分、tauri leaf と check-commit.mjs が一致すること。`pnpm test:native:static` に入れます。
- Husky 検査: `tests/all-language-husky.test.mjs` の leaves に3つを追加します。
- 実ツール検証（macOS、明示実行）: 最小 fixture crate を `.verification/` に作り、各 leaf で次を確かめます。tokio・sqlx・reqwest などの禁止 API は、同じパスを持つ path 依存の偽 crate で代用し、ネットワークを使いません（筆者の判断）。本物の crate での確認は範囲外と明記します。
  - 正常系: 全段が成功（exit 0）。
  - 異常系: unwrap、print、unsafe、禁止 API（種類ごと）、未使用依存、ban した crate、テスト0件、カバレッジ90%未満が、それぞれ非0。
  - ban の検査は依存の取得を伴うため、取得する crate と保存先を実装計画に書きます。
- 実行しないもの: Windows/Linux、CI、本物のサーバー依存（axum 等）での build。
- `scripts/check.ps1` は配布しません。macOS/Linux の POSIX shell のみ対象と README に書きます（筆者の判断）。

## 7. 次のアクション

- [ ] 本設計書のユーザーレビュー
- [ ] 実装計画の作成
- [ ] ツール導入（1.99.1、nextest、deny、shear、llvm-cov。承認済み）
- [ ] 実装（静的検査は TDD）
- [ ] 実ツール検証
- [ ] main へ統合
- [ ] scaffold-profiles の `basic-design.md` の言語表に、Rust 3 leaf の使い分けの注記を追加（同リポジトリの worktree で。lang-boilerplates の main へ入れたあと。`dist/` 再生成とテストまで）

## 8. リスク・残論点

| リスク | 影響 | 対策 |
| --- | --- | --- |
| pedantic・nursery・cargo の deny で、依存を入れた直後に大量に落ちる | 導入初日に止まる | README に「外すなら理由つき `#[expect]` か workspace で allow」と手順を書く |
| `multiple_crate_versions` / `multiple-versions` は依存次第で避けられない | 永続的に落ちる | 外し方と記録の仕方を README に書く |
| `allow-invalid` が無い・挙動が違う | 依存なしで disallowed が警告になる | 実装の最初に Clippy 1.99.1 で確かめる |
| nursery は誤検知がある | 正しいコードが落ちる | `#[expect(…, reason = …)]` を許す |
| 行 90% が小さな crate で厳しすぎる | push できない | 利用側が下限を変える場所を README に書く |
| advisories がネットワークに依存 | 外出先で push できない | 失敗時の原因表示を check.sh に入れる |

残る空白: なし（scaffold-profiles への登録は 7章のアクションに入れた）。

## 9. 参考元と決定ログ

- 調査レポート（2026-10-30）: ライブラリ、bincode の保守終了、ツール版、品質ゲートの段の分担。
- 既存 `rust/tauri`: toolchain 確認・フック・check-commit.mjs の型。
- 決定ログ:
  - 2026-10-30: 3 leaf・品質設定のみ・最大級・1.99.1・種類ごとの差分案・行 90%・明示ライセンス・ツール導入をユーザーが選択。
  - 2026-10-30: 実装時の最新版の導入と、scaffold-profiles への登録をユーザーが選択。
  - 2026-10-30（筆者の判断、builder check を受けて）: room の `tokio::spawn` 禁止を取り消し、realtime は `RandomState` 型ごと禁止、social は `SQLX_OFFLINE=true` を既定、依存つき禁止 API は偽 crate で検証、`check.ps1` は配布しない。
  - 2026-10-30（筆者の判断、実装時）: Clippy 1.99.1 は暗黙の RandomState を検出しないため、realtime は HashMap・HashSet 型自体を禁止
