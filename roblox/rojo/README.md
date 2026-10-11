# Rojo プロジェクト — Roblox（Luau）品質設定

Rojo でファイル管理する Roblox ゲーム用の自己完結した設定です。Rokit で次の版を固定します:
Rojo **7.7.1**、StyLua **2.5.2**、Selene **0.32.0**、luau-lsp **1.69.0**、Lune **0.10.5**、
Wally **0.3.2**。製品 source、`roblox.yml`、`wally.lock`、fixture/cache は配布しません。

## 導入（既存ファイルを保護）

プロジェクト root へ次を同じ相対位置で導入します（親/兄弟設定は不要）。

| コピー元 | コピー先 |
| --- | --- |
| [rokit.toml](rokit.toml) | `rokit.toml` |
| [default.project.json](default.project.json) | `default.project.json`（`name` を製品に合わせる） |
| [wally.toml](wally.toml) | `wally.toml`（`name` を製品に合わせる） |
| [stylua.toml](stylua.toml) | `stylua.toml` |
| [selene.toml](selene.toml) | `selene.toml` |
| [.luaurc](.luaurc) | `.luaurc` |
| [.editorconfig](.editorconfig) | `.editorconfig` |
| [.gitignore](.gitignore) | `.gitignore` |
| [src/server/.gitkeep](src/server/.gitkeep) | `src/server/.gitkeep` |
| [src/client/.gitkeep](src/client/.gitkeep) | `src/client/.gitkeep` |
| [src/shared/.gitkeep](src/shared/.gitkeep) | `src/shared/.gitkeep` |
| [tests/.gitkeep](tests/.gitkeep) | `tests/.gitkeep` |
| [scripts/check.sh](scripts/check.sh) | `scripts/check.sh` |
| [scripts/test.luau](scripts/test.luau) | `scripts/test.luau` |
| [.githooks/pre-commit](.githooks/pre-commit) | `.githooks/pre-commit` |
| [.githooks/pre-push](.githooks/pre-push) | `.githooks/pre-push` |
| [LICENSE](LICENSE) | `LICENSE.lang-boilerplates` |
| この README | 参照用。製品 README を上書きしない |

コピー前に既存ファイル・symlink・Git hooksPath/フックを読み取り、差分を提示して承認を得てください。
無条件の一括コピーは行いません。製品のライセンスは変更しません。

Rojo の配置は次の通りです。`Packages` は optional なので、`wally install` 前でも build できます。

| ファイル | Roblox 上の配置 |
| --- | --- |
| `src/server` | `ServerScriptService.Server` |
| `src/client` | `StarterPlayer.StarterPlayerScripts.Client` |
| `src/shared` | `ReplicatedStorage.Shared` |
| `Packages` | `ReplicatedStorage.Packages` |

## tool と定義ファイル

チェックは tool・依存・定義ファイルを自動導入しません。範囲を確認し、別途承認して実行してください。

1. Rokit を利用側で導入し、プロジェクト root で `rokit install` を実行します。
   `~/.rokit/bin` を PATH の先頭に置いてください。Homebrew 等の別版が先にあると版不一致で止まります。
2. Wally 0.3.2 は Intel 版のみです。Apple Silicon の Mac では Rosetta 2 が必要です
   （`softwareupdate --install-rosetta`）。OS 全体の変更なので、導入は利用者が判断してください。
3. `selene generate-roblox-std` で `roblox.yml` を生成し、製品 Git に保存します。
   `selene.toml` は `roblox-std-source = "pinned"` のため、Selene は自動更新しません。
4. 依存を追加したら `wally install` を実行し、`wally.lock` を製品 Git に保存します。
   Wally パッケージの型（wally-package-types）は対象外で、`Packages/**` の型エラーは無視します。
   対応するのは `[dependencies]`（`Packages/`）だけです。`[server-dependencies]` や
   `[dev-dependencies]` を使う場合は、`default.project.json`・`.gitignore`・check.sh を製品側で
   拡張してください。未拡張のまま書くと check.sh は止まります。
5. Roblox の型定義は、初回の typecheck で luau-lsp 1.69.0 タグの `globalTypes.d.luau` を取得し、
   SHA256 を照合して `.luau-lsp-cache/` に保存します。これがチェック唯一のネットワーク接続です。

## チェック

```sh
sh scripts/check.sh all
sh scripts/check.sh format # format|lint|typecheck|test|build|all
```

| 段階 | コマンド |
| --- | --- |
| 事前確認 | `rokit.toml` の各 tool が PATH にあり `--version` が一致するか |
| format | `stylua --check src tests scripts`（書換えなし） |
| lint | `selene src tests scripts`（警告も不合格） |
| typecheck | `rojo sourcemap` → 型定義の取得・SHA256 照合 → `luau-lsp analyze --platform=roblox`（strict） |
| test | `lune run scripts/test.luau` |
| build | `rojo build` で一時ディレクトリに place を出力し、確認後に削除 |

最初の失敗で停止します（成功0、不合格非0）。次の場合も非0です: tool 不在・版違い、`src` に
`.luau` が無い、`roblox.yml` が無い、`wally.toml` に依存があるのに `Packages/` が無い、
型定義の SHA256 不一致（キャッシュ済みも毎回照合。壊れたら削除して再取得）、テスト0件、
`rokit.toml` の `[tools]` に読めない行がある（行末コメント等）、server/dev 依存がある。

## テスト

`tests/**/*.spec.luau` は `{ [テスト名]: () -> () }` のテーブルを返します。
error を投げたテストは失敗です。テーブル以外を返す spec や読込みエラーも失敗に数えます。

```lua
local Greeting = require("../src/shared/Greeting")

return {
	["formats a name"] = function()
		assert(Greeting.format("Roblox") == "Hello, Roblox!")
	end,
}
```

Lune で実行するため、対象は `require("./x")` や `require("../x")` 形式で書いた純粋ロジックに
限ります。`script.Parent` 形式の require や Roblox API に依存するコードは Lune では動きません。
Roblox 上の動作は Studio で確認してください。

## 手動 Git フック（別承認で有効化）

コピー/check は hooksPath を変更しません。Node/Husky は不要です。
プロジェクト root で、まず有効な設定の全 origin と既存フックを読み取り確認します。

```sh
git config --show-origin --get-all core.hooksPath
git rev-parse --git-path hooks
```

設定が未定義の場合の最初のコマンドは exit 1 です。既存フック、global hooksPath、
symlink があれば**有効化を停止して相談**し、既存内容・差分を提示してください。
local hooksPath は global の既存フックも隠すため、無断で置き換え/連結しません。
既存フックなし、又は承認済みの統合方針がある場合に限り、変更の別承認後に実行します。

```sh
chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks
```

pre-commit は `sh scripts/check.sh format` と `lint`、pre-push は `sh scripts/check.sh all` を
実行し、不合格は非0で commit/push を止めます。IDE の Git にも同じ PATH が必要です。
GitHub への試験 push、global Git 設定変更、`--no-verify` による回避は行いません。

## 検証範囲

macOS（Apple Silicon、Rosetta 2 導入済み）で、実 tool を使った正常/異常系とローカル bare remote
への commit/push を検証しています。Roblox Studio への実同期、Windows/Linux、Wally レジストリからの
実取得は**未検証**です。macOS の成功を他 OS の成功に一般化しません。

- [Rojo](https://rojo.space/docs/v7/)
- [Rokit](https://github.com/rojo-rbx/rokit)
- [Selene Roblox Guide](https://kampfkarren.github.io/selene/roblox.html)
- [StyLua](https://github.com/JohnnyMorganz/StyLua)
- [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp)
- [Lune](https://lune-org.github.io/docs)
- [Wally](https://github.com/UpliftGames/wally)

本設定はこのリポジトリの MIT ライセンスです。第三者製品の source/config を移植していません。
