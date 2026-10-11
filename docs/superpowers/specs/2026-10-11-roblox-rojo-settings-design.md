# Roblox（Luau）Rojo プロジェクト用設定集 — 設計

> 作成日・最終更新: 2026-10-11
> 出所: ユーザーとの質疑（2026-10-11）、各ツールの GitHub Releases（2026-10-11 確認）、コミュニティ雛形の調査。
> 目的: Scaffold が言語別 README から、Rojo でファイル管理する Roblox ゲーム用の自己完結した設定セットを選び、導入できるようにします。

## 目次

1. 要約と決定事項
2. 配置・コピー契約
3. ツールと設定
4. チェックと Git フック
5. 合格基準・検証範囲
6. 次のアクション
7. リスク・残論点
8. 参考元と決定ログ

## 1. 要約と決定事項

`roblox/rojo/` に、Rojo でファイル管理する Roblox ゲーム向けの設定セットを追加します。整形・Lint・型チェック・Lune テスト・Rojo build を `scripts/check.sh` で直列に実行します。製品 source は配布せず、空のディレクトリ構成だけを置きます。macOS で実ツールを使って検証し、Studio 同期と Windows/Linux は未検証と明記します。

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| 開発方式 | **Rojo でファイル管理** | Git・Neovim・AI エージェントで編集しやすくするため。 |
| ツール管理 | **Rokit** | aftman の後継で、現在の主流です。手元に未導入のため導入は別承認です。 |
| 同梱ツール | **Rojo・StyLua・Selene・luau-lsp・Wally・Lune** | ユーザーが全項目を選択しました。 |
| 配布 | **設定と空ディレクトリのみ** | 既存 leaf と同じ方針です。サンプルコードは入れません。 |
| チェック方式 | **POSIX sh の `scripts/check.sh`** | 既存の Rust/Swift と形を揃えます。Lune スクリプト案・Luumen 案は不採用です。 |
| 検証 | **静的検査＋実ツールでの実行** | `test:native:roblox` を新設します。Rokit とツールの導入は実行前に別承認です。 |
| テスト対象 | **`require("./x")` 形式の純粋ロジックのみ** | Lune は `script.Parent` 形式の require を解決できないためです。 |

## 2. 配置・コピー契約

```text
roblox/
  README.md                 入口。leaf への案内
  rojo/
    README.md               全配布ファイル、コピー先、導入手順、手動チェック、フック有効化
    LICENSE / .editorconfig / .gitignore
    rokit.toml
    default.project.json
    wally.toml
    stylua.toml
    selene.toml
    .luaurc
    src/server/.gitkeep
    src/client/.gitkeep
    src/shared/.gitkeep
    tests/.gitkeep
    scripts/check.sh
    scripts/test.luau
    .githooks/pre-commit
    .githooks/pre-push
```

- リポジトリ直下の README の言語表と「範囲」に Roblox を追加します。
- leaf は親や兄弟に依存せず、このフォルダだけをコピーすれば動きます。
- コピー先の既存ファイルは上書きしません。手順は leaf README を正本とします。
- `.luau-lsp.json` は作りません。analyze の引数は `check.sh` に集約します（設計時の候補から削除。理由: CLI 引数で足り、設定の置き場所を1つにするため）。

## 3. ツールと設定

### 3.1 版の固定（rokit.toml）

| ツール | 版 | 備考 |
| --- | --- | --- |
| rojo-rbx/rojo | 7.7.1 | 2026-10-02 公開 |
| UpliftGames/wally | 0.3.2 | 0.4.0 はアルファのため見送り |
| Kampfkarren/selene | 0.32.0 | 2026-10-01 公開 |
| JohnnyMorganz/StyLua | 2.5.2 | |
| JohnnyMorganz/luau-lsp | 1.69.0 | |
| lune-org/lune | 0.10.5 | |

【確度：高】各 GitHub Releases で確認しました（2026-10-11）。

### 3.2 Rojo の対応関係（default.project.json）

| ファイル | Roblox 上の配置 |
| --- | --- |
| `src/server` | `ServerScriptService.Server` |
| `src/client` | `StarterPlayer.StarterPlayerScripts.Client` |
| `src/shared` | `ReplicatedStorage.Shared` |
| `Packages` | `ReplicatedStorage.Packages` |

`Packages` は `wally install` 後にだけ存在します。`$ignoreUnknownInstances` などの追加設定は入れません。

### 3.3 品質設定

- `stylua.toml`: `syntax = "Luau"`、列幅 120、タブ、`AutoPreferDouble`、`call_parentheses = "Always"`。
- `selene.toml`: `std = "roblox"`、`roblox-std-source = "pinned"`。Selene 0.30 以降は Roblox 上の文字列 require を受け付けます。
- `roblox.yml`（Selene の Roblox 定義）: 利用者が `selene generate-roblox-std` で一度だけ生成し、製品 Git で管理します。雛形には同梱しません。floating（既定）だと6時間ごとに自動ダウンロードされ、結果が再現できないためです（2026-10-11 改訂）。
- `.luaurc`: `languageMode = "strict"`。
- `wally.toml`: 依存は空、`realm = "shared"`、registry は公式の `UpliftGames/wally-index`。
- `.gitignore`: `Packages/`、`sourcemap.json`、`*.rbxl`、`*.rbxlx`、`.luau-lsp-cache/`。既存 leaf（Rust/Swift）に揃え `/.verification/` と `.DS_Store` も含めます（2026-10-11 改訂）。`wally.lock` と `roblox.yml` は Git 管理します。
- テスト実行器: 読込みエラー、テーブル以外、空テーブル、文字列以外のテスト名、関数以外の値を、ファイル名つきの失敗として数えます（2026-10-11 改訂）。

### 3.4 型定義

- 取得元: `https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/1.69.0/scripts/globalTypes.d.luau`
- SHA256: `7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2`（2026-10-11 取得時の実測値）
- 保存先: `.luau-lsp-cache/globalTypes-1.69.0.d.luau`（Git 管理外）
- SHA が一致しない場合は保存せず、非0で止めます。luau-lsp の版を上げるときは URL と SHA を同時に更新します。

## 4. チェックと Git フック

### 4.1 check.sh

`scripts/check.sh [all|format|lint|typecheck|test|build]`。省略時は `all` です。最初の失敗で止まり、非0を返します。

| 段階 | コマンド |
| --- | --- |
| 事前確認 | rokit.toml の各ツールが PATH にあり、`--version` が一致するか |
| format | `stylua --check src tests scripts` |
| lint | `selene src tests scripts` |
| typecheck | `rojo sourcemap default.project.json -o sourcemap.json` → 型定義の取得・照合 → `luau-lsp analyze --platform=roblox --sourcemap=sourcemap.json --definitions=<型定義> --ignore="Packages/**" src tests` |
| test | `lune run scripts/test.luau` |
| build | `rojo build default.project.json -o <一時ディレクトリ>/place.rbxl` → 出力確認後に削除 |

非0で止める条件:

- ツールが無い、または版が違う（「`rokit install` を実行してください」と案内）
- `src` 配下に `.luau` が1つもない
- `wally.toml` に依存があるのに `Packages/` が無い（「`wally install` を実行してください」と案内）
- テストが0件
- 型定義の SHA が一致しない（キャッシュ済みファイルも毎回照合）
- `roblox.yml` が無い（「`selene generate-roblox-std` を実行してください」と案内）

自動でツールや依存を導入しません。外部へ接続するのは、型定義の初回取得だけです。

### 4.2 scripts/test.luau

Lune 用の最小のテスト実行器です。`tests/` 配下の `*.spec.luau` を再帰的に探し、各ファイルを require します。各 spec は `{ [テスト名]: () -> () }` のテーブルを返します。1件でも error を投げたら非0、0件でも非0にします。外部のテストフレームワーク（TestEZ・Jest-Lua）は使いません。

### 4.3 Git フック

- `pre-commit`: `check.sh format` と `check.sh lint`
- `pre-push`: `check.sh all`
- コピーだけでは有効になりません。利用者が README の手順で `git config core.hooksPath .githooks` を実行します。既存フックがある場合は、先に内容を確認するよう README に書きます。

## 5. 合格基準・検証範囲

### 5.1 追加するテスト

- `tests/native/test_static_roblox.py`: 版の固定、`std = "roblox"`、strict、型定義の URL と SHA、Rojo の対応関係、`.gitignore`、製品 source の混入なしを確認します。
- `tests/native/test_roblox.py`＋`roblox_helpers.py`: leaf を `.verification/native/roblox/` へコピーした fixture で実行します。
- `tests/native/test_catalog.py`: `roblox/rojo` の配布ファイル一覧の完全一致、README リンク、独立コピーを追加します。
- `tests/native/test_hooks.py`: `RobloxHookTests` を追加します。synthetic HOME とローカル bare remote を使います。
- `package.json`: `test:native:roblox` を追加し、`test:native:static` に Roblox の静的テストを加えます。`pnpm test` は変更しません。

### 5.2 合格基準

| 種類 | 入力 | 期待 |
| --- | --- | --- |
| 正常系 | 純粋ロジック1つ＋spec 1つ | `all` が 0 |
| 異常系 | 整形崩れ | format で非0 |
| 異常系 | 未使用変数など Selene 警告 | lint で非0 |
| 異常系 | strict の型エラー | typecheck で非0 |
| 異常系 | 失敗する spec | test で非0 |
| 異常系 | spec 0件 | test で非0 |
| 異常系 | 存在しない `$path` | build で非0 |
| 異常系 | ツール不在・版違い | 事前確認で非0 |
| 異常系 | 型定義の SHA 不一致 | typecheck で非0 |
| 異常系 | 依存ありで `Packages/` 無し | 事前確認で非0 |
| 異常系 | `roblox.yml` 無し | 事前確認で非0 |
| フック | 整形崩れを commit | pre-commit で拒否 |
| フック | 型エラーを push | pre-push で拒否 |

### 5.3 検証しない範囲

Studio への実同期、Windows/Linux、Wally レジストリからの実取得、公開・配信は検証しません。README と progress.md に未検証と明記します。

## 6. 次のアクション

- [x] 本設計書のユーザーレビュー（2026-10-11 承認）
- [x] 実装計画の作成（2026-10-11）
- [x] Rokit 本体と6ツールの導入承認（2026-10-11。Wally 用に Rosetta 2 もユーザーが導入）
- [x] 実装・検証（TDD）（2026-10-11。native static 19件・roblox 16件成功）
- [x] progress.md 更新（2026-10-11）
- [ ] main への統合判断

## 7. リスク・残論点

| リスク | 影響 | 対策 |
| --- | --- | --- |
| 型定義の取得元が消える・変わる | typecheck が通らない | タグ固定と SHA 照合で検知します。 |
| Lune で Roblox 依存コードをテストできない | テスト範囲が狭い | README で対象を純粋ロジックに限定すると明記します。 |
| Wally 0.4 正式版で lock 形式が変わる | 将来の更新時に差分が出る | 0.3.2 固定。更新は別作業とします。 |
| Wally 0.3.2 は x86_64 のみ | Apple Silicon で Rosetta 2 が必要 | README に明記。check.sh は版確認で検知します。 |
| Rojo 7.7.1 は公開から9日 | 直後の patch が出る可能性 | リリースノートで次の patch が予告済みです。出たら版を更新します。 |

残る空白:

- Roblox 型付きの Wally パッケージ（wally-package-types）への対応は今回含めません。必要になったら別途検討します。

## 8. 参考元と決定ログ

- Rojo releases: https://github.com/rojo-rbx/rojo/releases
- Rokit releases: https://github.com/rojo-rbx/rokit/releases
- luau-lsp README（standalone analyze、sourcemap）: https://github.com/JohnnyMorganz/luau-lsp
- Selene releases: https://github.com/Kampfkarren/selene/releases
- StyLua releases: https://github.com/JohnnyMorganz/StyLua/releases
- Lune releases: https://github.com/lune-org/lune/releases
- Wally releases: https://github.com/UpliftGames/wally/releases
- 参考雛形: takoyakisoft/roblox-rojo-wally-template、Mark-Marks/roblox-project-template

| 日付 | 決定 |
| --- | --- |
| 2026-10-11 | Rojo でファイル管理、Rokit、6ツール全採用、空ディレクトリのみ、実ツール検証、check.sh 方式を決定 |
| 2026-10-11 | `.luau-lsp.json` を設計から削除し、analyze 引数を check.sh に集約 |
| 2026-10-11 | Selene の Roblox 定義を pinned（`roblox.yml` を利用者が生成・Git 管理）に変更。段階名 `fmt` を既存 leaf に合わせ `format` に変更 |
