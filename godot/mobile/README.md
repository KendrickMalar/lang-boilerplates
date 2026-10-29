# Godot モバイルゲーム — GDScript 品質設定

Godot **4.7.2**（標準版、.NET なし）と gdtoolkit **4.5.0**（gdlint / gdformat）を使う、
モバイルゲーム用の自己完結した設定です。製品 source、`.godot/`、書き出し設定は配布しません。

## 導入（既存ファイルを保護）

製品リポジトリのゲーム用ディレクトリ（root でも `game/` などでもよい）へ同じ相対位置で導入します。

| コピー元 | コピー先 |
| --- | --- |
| [project.godot](project.godot) | `project.godot`（`config/name` を製品に合わせる） |
| [gdlintrc](gdlintrc) | `gdlintrc` |
| [gdformatrc](gdformatrc) | `gdformatrc` |
| [.editorconfig](.editorconfig) | `.editorconfig` |
| [.gitignore](.gitignore) | `.gitignore` |
| [.gitattributes](.gitattributes) | `.gitattributes` |
| [src/.gitkeep](src/.gitkeep) | `src/.gitkeep` |
| [tests/.gitkeep](tests/.gitkeep) | `tests/.gitkeep` |
| [scripts/check.sh](scripts/check.sh) | `scripts/check.sh` |
| [scripts/test_runner.gd](scripts/test_runner.gd) | `scripts/test_runner.gd` |
| [scripts/test_context.gd](scripts/test_context.gd) | `scripts/test_context.gd` |
| [.husky/pre-commit](.husky/pre-commit) | `.husky/pre-commit` |
| [.husky/pre-push](.husky/pre-push) | `.husky/pre-push` |
| [LICENSE](LICENSE) | `LICENSE.lang-boilerplates` |
| この README | 参照用。製品 README を上書きしない |

コピー前に既存ファイル・symlink・Git hooksPath/フックを読み取り、差分を提示して承認を得てください。
無条件の一括コピーは行いません。

`project.godot` の設定:

- 描画方式 Mobile（Metal / Vulkan）。古い端末を優先する製品は Compatibility へ変えてください。
- ETC2/ASTC の VRAM 圧縮を有効化（Android 書き出しに必要）。
- `debug/gdscript/warnings/untyped_declaration=2`: 型のない変数・引数・戻り値をエラーにします。

## ツール

チェックはツールを導入しません。範囲を確認し、別途承認して利用者が導入してください（macOS の例）。

```sh
brew install --cask godot        # godot コマンドも入る
brew install uv
uv tool install gdtoolkit==4.5.0 # gdlint / gdformat（~/.local/bin）
```

## チェック

```sh
sh scripts/check.sh all
sh scripts/check.sh format # format|lint|typecheck|test|all
```

| 段階 | コマンド |
| --- | --- |
| 事前確認 | godot・gdlint・gdformat の版が一致するか、`src/` か `tests/` に `.gd` があるか |
| format | `gdformat --check src tests scripts`（書換えなし） |
| lint | `gdlint src tests scripts` |
| typecheck | `godot --headless --import` の後、各 `.gd` を `--check-only` で解析 |
| test | `--import` の後 `godot --headless --path . --script scripts/test_runner.gd` |

Godot 4.7.2 は構文エラー・型エラーでも終了コード0を返し、テスト中の実行時エラーの後も処理を続けます。
そのため check.sh は、出力に `SCRIPT ERROR`・`Parse Error`・`Failed to load script` があれば不合格にします。
実行時エラーで途中終了したテストは、実行器の集計では PASS と表示され、実行器単体の終了コードも0です。
合否は必ず check.sh 経由で判定してください（実行器を直接呼んだ結果を合格とみなさない）。
最初の失敗で停止します（成功0、不合格非0）。

## テスト

`tests/**/test_*.gd` は `extends RefCounted` とし、`test_` で始まるメソッドが `TestContext` を受け取ります。
GDScript には例外がないため、`assert` ではなく `TestContext` に失敗を記録します。

```gdscript
extends RefCounted

const Score = preload("res://src/score.gd")


func test_adds_points(t: TestContext) -> void:
	t.expect_eq(Score.add(1, 2), 3, "add")
	t.expect(Score.add(0, 0) == 0, "zero stays zero")
```

テスト0件、読み込めないテスト、`test_` メソッドの無いファイルは失敗です。
テストの中で `await` は使えません（最初の `await` で呼び出しが戻り、その後の記録を拾えないため、
`await` したテストは失敗にします）。フレームやシグナルを待つ処理は、待たずに確かめられる純粋なロジックに
分けてテストしてください。

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
例えば godot/mobile と blender/assets の root package.json の `scripts.check` は次の値にします。

```json
"check": "sh game/scripts/check.sh all && sh art/scripts/check.sh all"
```

各 check.sh は自身の leaf に移動します。どちらかが失敗すれば両フックとも非0になります。
Tauri + TypeScript では root の `check` に backend と frontend の全体検査を漏れなく登録します。
frontend側 package.json の check 名と root の集約 check 名を分け、相互呼び出しの再帰を避けます。
Roblox の Git root / project root の不一致は既存 guard の対象外なので、guard を外して混在対応しません。


## 検証範囲

macOS（asuka、Apple Silicon）で leaf をコピーし、正常系と異常系を手動で1回確認しました（結果は
リポジトリの progress.md）。Android/iOS への書き出しと実機、Windows/Linux、Godot エディタでの操作、
Git フックの実 push は**未検証**です。ツールの版を上げるときは同じ確認をやり直してください。

- [Godot コマンドライン](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
- [Godot 描画方式](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html)
- [gdtoolkit](https://github.com/Scony/godot-gdscript-toolkit)

本設定はこのリポジトリの MIT ライセンスです。
