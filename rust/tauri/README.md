# Tauri desktop — Rust 品質・権限境界設定

自己完結した単体 `src-tauri` crate 用設定です。Rust **1.92.0** / edition **2024**、
Tauri **2.12.2** / tauri-build **2.7.1** を固定します。workspace は対象外です。
製品 Rust source、frontend、Cargo.lock、fixture/cache は配布しません。
設定は最小の権限候補です。任意の製品 command の安全性や WebView/E2E を保証しません。
frontend 接続・製品設定・command 登録/入力検査は利用側で完成させます。

## 導入（既存ファイルを保護）

プロジェクト root へ次を同じ相対位置で導入します（親/兄弟設定は不要）。

| コピー元 | コピー先 |
| --- | --- |
| [rust-toolchain.toml](rust-toolchain.toml) | `rust-toolchain.toml` |
| [rustfmt.toml](rustfmt.toml) | `rustfmt.toml` |
| [.editorconfig](.editorconfig) | `.editorconfig` |
| [.gitignore](.gitignore) | `.gitignore` |
| [.cargo/config.toml](.cargo/config.toml) | `.cargo/config.toml` |
| [src-tauri/Cargo.toml](src-tauri/Cargo.toml) | `src-tauri/Cargo.toml` |
| [src-tauri/build.rs](src-tauri/build.rs) | `src-tauri/build.rs` |
| [src-tauri/tauri.conf.json](src-tauri/tauri.conf.json) | `src-tauri/tauri.conf.json` |
| [src-tauri/capabilities/main.json](src-tauri/capabilities/main.json) | `src-tauri/capabilities/main.json` |
| [scripts/check.sh](scripts/check.sh) | `scripts/check.sh` |
| [scripts/check.ps1](scripts/check.ps1) | `scripts/check.ps1` |
| [.husky/pre-commit](.husky/pre-commit) | `.husky/pre-commit` |
| [.husky/pre-push](.husky/pre-push) | `.husky/pre-push` |
| [LICENSE](LICENSE) | `LICENSE.lang-boilerplates` |
| この README | 参照用。製品 README を上書きしない |

コピー前に既存ファイル・symlink・manifest・Git hooksPath/フックを読み取り、差分を提示して
承認を得てください。無条件の一括コピーは行いません。既存 Cargo.toml 等は差分統合します。
製品名・crate 名を合わせ、利用側に非空の `src-tauri/src/main.rs` と `src-tauri/src/lib.rs`、
実際に実行される Rust test を用意してください。製品のライセンスは変更しません。
Git hook の導入/有効化や global 設定変更はこのチェックでは行いません。

## tool と lock

POSIX shell または **PowerShell 7+**、既存 **rustup 1.28.2 以上** と named **1.92.0** toolchain、rustfmt/Clippy が必要です。
チェックはまず `rustup toolchain list` で exact installed 名を確認し、
その full 名で `rustup which --toolchain …` を呼び、tool path/版を出力します。
最初の rustup 呼出し前から process-local `RUSTUP_AUTO_INSTALL=0` を適用します。
自動取得防止の実測は rustup 1.28.2 のみです。他版は個別に不足tool/component検証が必要です。
不足時に自動 bootstrap/download、default stable への切替、fix/clean は行いません。
tool 取得は利用側で範囲を確認し、別途承認して実行してください。

依存の取得も明示的に承認してから、プロジェクト root で次を実行します。

```sh
cargo +1.92.0 generate-lockfile --manifest-path src-tauri/Cargo.toml
cargo +1.92.0 metadata --locked --format-version 1 --manifest-path src-tauri/Cargo.toml
```

解決した全推移依存の `rust_version` を確認し、1.92 超過や未知依存では停止して相談します。
MSRV 未宣言は無条件の合格ではありません。package 名/版/source と未宣言一覧を固定 Cargo.lock の
SHA256 に結び付け、対象 macOS・Rust1.92.0 の同 lock に対する実 build と非空 test の成功を
記録する条件でのみ許容します。新しい未知依存・版/source変更・lock変更は停止し、再承認を要求します。
直接依存の MSRV だけで全体の互換性を宣言しません。Cargo.lock をレビューして製品 Git に保存します。
macOS で選択されなかった platform graph（Windows/Linux 等）の互換性は、この記録では保証しません。
`.cargo/config.toml` は互換版への resolver fallback のみで、版不整合を検証済みにしません。

## チェック

```sh
sh scripts/check.sh all
sh scripts/check.sh format # format|lint|test|build|all
```

```powershell
pwsh -NoProfile -File scripts/check.ps1 -Stage all
```

順序は `cargo fmt --manifest-path … --check` →
`cargo clippy --manifest-path … --locked --all-targets -- -D warnings` →
`cargo test --manifest-path … --locked` → `cargo build --manifest-path … --locked`。
最初の失敗で停止します（成功0、不合格非0）。test はまず一覧を検査し、実実行で0件/全ignoredも拒否します。
manifest/source/lock/tool 不足は失敗します。build は利用側 source 次第です。
空の main/backend unit test の成功だけでは native app を検証できません。
利用側 source が `tauri::generate_context!()` と runtime builder に設定を接続し、
`custom-protocol` feature を有効にした frontend 埋込み build を別途実行してください。
frontendDist 不足が非0になることも確認します。release 最適化/all-features は自動採用しません。

unsafe/未処理 must-use は deny、Clippy all は warn (priority -1)、
unwrap/expect/todo/dbg は deny、チェックでは全警告を不合格にします。
stable rustfmt の幅100・4スペース・LF・edition2024を使用します。

### 個別に追加した Clippy 検査

全 pedantic/nursery/restriction グループは有効にしません。既存の安全検査に、次の3項目だけを追加しています。

| 設定 | 検出するもの | 修正の例 |
| --- | --- | --- |
| `redundant_clone` | 元の値をもう使わないのに行う clone | 所有権を移す |
| `assigning_clones` | 既存のバッファへ clone 結果を代入 | `clone_from` / `clone_into` を検討する |
| `or_fun_call` | 不要でも先に実行される代替値の生成 | `unwrap_or_else` などへ変える |

[Tauri の実設定（固定 commit）](https://github.com/tauri-apps/tauri/blob/94ffd77664759f38111bde3e85802841da80c3eb/Cargo.toml)でも使われている項目です。
レベルは `warn`、品質チェックでは既存の `-D warnings` により不合格になります。
[Clippy のグループ選定の注意](https://doc.rust-lang.org/stable/clippy/lints.html)に従い、restriction の一括有効化や製品固有の禁止APIは持ち込みません。
コンパイラ設定と stable rustfmt の見た目は据え置きです。

caller の `RUSTUP_HOME`、`CARGO_HOME`、`CARGO_TARGET_DIR` を尊重します。
隔離検証ではプロジェクトの `.verification/native/rust/` 下へ HOME/cache/target を指定してください。
環境変数はコマンド単位で指定し、global Rustup/Git/shell 設定を変更しません。

## frontend と command ACL の接続（製品側で必須）

`tauri.conf.json` の `productName`/version/`com.example.native-app` は例示値です。
製品固有の identifier、main window label/title と capability の windows を揃えてください。
`frontendDist: ../dist` は src-tauri からの相対パス、`devUrl: http://localhost:1420` は
ローカル開発候補です。実 frontend 出力/開発 server に合わせて変更し、到達性を確認します。
frontend install/build command は自動実行しません。TypeScript 設定は含めません。
CSP は self と IPC 接続のみの初期候補です。製品の asset/通信先と開発環境を確認し、必要な
origin だけを検討してください。CSP と ACL は異なる境界で、片方だけで入力の安全性を保証しません。
`bundle.active: false` は配布/署名を行わない初期値です。署名・公開・モバイルは対象外です。

capability `main` は config から明示選択され、local/main window/desktop platforms のみに
`core:window:allow-title`（title 読取り）を与えます。remote、全window wildcard、広い
filesystem/shell/process/updater は許可しません。不要なら title permission も除いてください。

**custom Rust app command は plugin command と違い、AppManifest 未接続時にはローカルから
既定で広く使用可能です。空の command リストは安全完成ではありません。**
製品 source を用意したら、次の全てをレビューしてください。

1. `build.rs` の `AppManifest::new().commands(&[])` に全 custom command 名を列挙する。
   runtime の `invoke_handler(tauri::generate_handler![...])` と登録を一致させる。
2. 自動生成される `allow-<command-name>` permission（snake_case は kebab-case）を
   必要な window の capability にだけ追加する。permission と command を混同しない。
   過去の自動生成 permission も確認する。JSON を置いただけでは保護できない。
3. command 実装の引数型/値、path 正規化、scope、権限、エラー伝搬を製品側で検査する。
   command 登録/permission は input/path/scope validation を代替しない。
4. 許可/未許可 command、別window、remote origin の IPC 実結果をそれぞれ検査する。
   設定/permissions を変えたら build して再検証する。

保守 fixture は製品と分離して2個の app command を登録し、1個だけを許可します。
同じ main の core title は許可、core close は拒否されることを実 IPC dispatcher で確認します。
AppManifest と app permission を外すと custom command が通る対照試験も行います。
これは Tauri **mock runtime** 上の backend/ACL 検証であり native WebView/E2E ではありません。
静的 frontend/生成 icon を用いた macOS native Cargo build は別結果です。
UI 起動・browser の CSP 実効検証・配布 bundle/署名は行いません。

## 検証範囲・参考元

macOS の実 Cargo fixture 検証を対象とします。**Windows/Linux native 実行は未実施**です。
PowerShell は未実行（parser 不在、手動確認のみ）で、macOS 成功を他 OS の成功に一般化しません。
保守 fixture は配布せず、製品 source や frontend を勝手に生成しません。

### リポジトリ保守検証（製品 check とは別）

Python fixture helper は `.verification/native/rust/approved-resolution/` の承認済み固定
`Cargo.lock` と `approval.json`（package 名/版/source/MSRV、lock hash、実 tool/OS/arch、
同 lock/source の実 build/test command/exit/出力を参照）を必要とします。
これらは Git 管理外であり、配布 leaf へ含めません。fresh clone で記録がなければ非0で停止し、
初回の依存取得・解決集合の審査・実検証・record 作成を別途承認してもらう必要があります。
毎回 lock を再解決したり、未知集合を自動承認したりしません。
固定 lock をコピー後、offline/locked metadata と承認集合を照合し、MSRV未宣言があれば
fixture 固有 target で実 build/test を再実行してから返します。
同一 test class は自身の同一 crate path/target のみを再利用し、各 test 前に所有 source/config/lock を
baseline bytes に復元・検査します（旧mtimeは復元しません）。異なる fixture の target は共有しません。
ignored/失敗test/不正source・config から正常実testへ戻る順序回帰も検査します。
各 Cargo case の一意な log/JSON receipt に source/config/lock hash、target、command/exit/test件数を保存します。
各 fixture の `dependency-evidence.json` に lock/source hash、未宣言一覧、tool/OS/arch、
target、command/exit/出力を紐付けます。失敗・0件・全ignored・未実施は許容条件を満たしません。
製品 `scripts/check.*` はこの保守用記録に依存せず、leaf の自己完結性を維持します。

- [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri tests](https://v2.tauri.app/develop/tests/)
- [Cargo lint 設定](https://doc.rust-lang.org/cargo/reference/manifest.html#the-lints-section)
- [Clippy](https://doc.rust-lang.org/clippy/usage.html)
- [Tauri 公式固定 snapshot](https://github.com/tauri-apps/tauri/tree/7fcd8a743497f1895b999bb8c8d9c1241662a476)

本設定はこのリポジトリの MIT ライセンスです。第三者製品の source/config を移植していません。
Tauri その他依存のライセンスは製品の解決結果に対して別途確認してください。

## Husky による Git フック（必須・明示有効化）

Node **24.15以上の24系または26以上**（25は対象外）、pnpm **12.6.0**、Husky **9.1.7** が必要です。
製品リポジトリの Git root に [package.json](package.json)、[pnpm-workspace.yaml](pnpm-workspace.yaml)、
[.node-version](.node-version)、[check-commit.mjs](check-commit.mjs)、
[.husky/pre-commit](.husky/pre-commit)・[.husky/pre-push](.husky/pre-push) を置きます。
既存 package.json / lock / Git 設定は差分統合し、上書きしません。コピー/install/check は hooksPath を変更しません。

依存導入と有効化は別手順です。対象・保存先・副作用の別承認後、Git root で実行します。

```sh
pnpm install --ignore-scripts --engine-strict
# 初回生成した pnpm-lock.yaml はレビューし、Git に保存する。
# lock がある以降は --frozen-lockfile を追加する。
git config --show-origin --get-all core.hooksPath
git rev-parse --git-path hooks
```

設定未定義の config コマンドは exit 1 です。既存フック・global hooksPath・symlink があれば停止して相談し、
既存フックを無断で隠したり置き換えたりしません。何もない場合だけ、承認された Git root で明示有効化します。

```sh
pnpm exec husky
git config --local --get core.hooksPath # .husky/_
```

既存 global dispatcher が Git共通ディレクトリの hooks を呼ぶ場合は、`pnpm exec husky` を実行せず、
既存設定を維持した bridge を別途設計します。bridge は現在の worktree の Git root へ移動し、
`node_modules/.bin` を PATH に加え、`sh .husky/pre-commit` / `sh .husky/pre-push "$@"` を呼びます。
push の stdin はそのまま引き継ぎます。共有 hooks・global フック・他 worktree の影響を確認し、
既存ファイル・symlink の上書きや main worktree への固定参照はしません。

commit 前は `node check-commit.mjs`、push 前は `node check-commit.mjs push` が全体検査を実行します。
通常は `pnpm run check` → `sh scripts/check.sh all` です。Roblox は `check:git` があれば
`pnpm run check:git commit|push` → 既存 Luau guard → 全体検査へ渡します。
検査失敗・tool不足・0件testを成功扱いにしません。commit は未stage・未追跡・隠すindex flag・
検査中のstage内容変更も拒否します。自動 stash / format / stage / 復元はしません。
pnpm は `verifyDepsBeforeRun: error` により、検査時の自動 install を拒否します。

全体検査に必要な tool / lock / source / test と環境変数を IDE の Git にも用意してください。
Simulator起動やapp配置・依存取得・ビルドなどの副作用も事前に範囲を確認します。
正常 commit と、不正 commit（HEAD 不変）・ローカル bare remote への不正 push（remote ref 不変）を検証します。
設定コピーや直接 check の成功だけでフック有効化済みとは扱いません。GitHub への試験 push はしません。
ローカルフックは未導入端末や明示スキップを強制的に防げません。CI・必須チェックは別要件です。

### 複数言語を同居させる場合

Husky は Git root に1つだけ配置します。各 leaf の言語設定・scripts は `game/` / `art/` などへ置き、
上記の Node / Husky 管理ファイルは root に統合します。子ディレクトリで Husky を有効化しません。
子の `node_modules/`・ビルド生成物も Git に入らないよう ignore を統合します。
例えば Godot と Blender の root package.json の `scripts.check` は次の値にします。

```json
"check": "sh game/scripts/check.sh all && sh art/scripts/check.sh all"
```

各 check.sh は自身の leaf に移動します。どちらかが失敗すれば両フックとも非0になります。
Tauri + TypeScript では root の `check` に backend と frontend の全体検査を漏れなく登録します。
frontend側 package.json の check 名と root の集約 check 名を分け、相互呼び出しの再帰を避けます。
Roblox の Git root / project root の不一致は既存 guard の対象外なので、guard を外して混在対応しません。
