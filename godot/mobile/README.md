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
| [.githooks/pre-commit](.githooks/pre-commit) | `.githooks/pre-commit` |
| [.githooks/pre-push](.githooks/pre-push) | `.githooks/pre-push` |
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
| test | `godot --headless --script scripts/test_runner.gd` |

Godot 4.7.2 は構文エラー・型エラーでも終了コード0を返し、テスト中の実行時エラーの後も処理を続けます。
そのため check.sh は、出力に `SCRIPT ERROR`・`Parse Error`・`Failed to load script` があれば不合格にします。
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

## 手動 Git フック（別承認で有効化）

コピー/check は hooksPath を変更しません。まず有効な設定と既存フックを確認します。

```sh
git config --show-origin --get-all core.hooksPath
git rev-parse --git-path hooks
```

既存フック、global hooksPath、symlink があれば有効化を停止して相談してください。
問題がなく、変更の別承認を得た場合に限り実行します（leaf を `game/` に置いた例）。

```sh
chmod +x game/.githooks/pre-commit game/.githooks/pre-push game/scripts/check.sh
git config --local core.hooksPath game/.githooks
```

フックは自身の位置から leaf の root を求めるので、root でもサブディレクトリでも動きます。

### blender/assets と組で使う場合

1つのリポジトリで両方を使うとき、hooksPath は1つしか設定できません。製品 root に次のような
フックを置き、両方の check.sh を呼びます（例: `game/` と `art/`）。

```sh
#!/bin/sh
# .githooks/pre-push at the product root
set -eu
cd "$(git rev-parse --show-toplevel)"
sh game/scripts/check.sh all
exec sh art/scripts/check.sh all
```

## 検証範囲

macOS（asuka、Apple Silicon）で leaf をコピーし、正常系と異常系を手動で1回確認しました（結果は
リポジトリの progress.md）。Android/iOS への書き出しと実機、Windows/Linux、Godot エディタでの操作、
Git フックの実 push は**未検証**です。ツールの版を上げるときは同じ確認をやり直してください。

- [Godot コマンドライン](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
- [Godot 描画方式](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html)
- [gdtoolkit](https://github.com/Scony/godot-gdscript-toolkit)

本設定はこのリポジトリの MIT ライセンスです。
