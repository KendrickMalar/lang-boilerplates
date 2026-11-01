# Blender アセット — 3D モデルをコードで作る設定

Blender **5.2.2 LTS**（同梱 Python 3.13）、ruff **0.17.0**、glTF-Transform CLI **4.5.1** を使う
自己完結した設定です。モデルを Python で組み立て、`.glb` に書き出して検査します。
サンプルモデル・生成物は配布しません。

## 導入（既存ファイルを保護）

製品リポジトリのアセット用ディレクトリ（例: `art/`）へ同じ相対位置で導入します。

| コピー元 | コピー先 |
| --- | --- |
| [pyproject.toml](pyproject.toml) | `pyproject.toml` |
| [.editorconfig](.editorconfig) | `.editorconfig` |
| [.gitignore](.gitignore) | `.gitignore` |
| [models/.gitkeep](models/.gitkeep) | `models/.gitkeep` |
| [tests/.gitkeep](tests/.gitkeep) | `tests/.gitkeep` |
| [scripts/check.sh](scripts/check.sh) | `scripts/check.sh` |
| [scripts/build.py](scripts/build.py) | `scripts/build.py` |
| [scripts/test.py](scripts/test.py) | `scripts/test.py` |
| [.husky/pre-commit](.husky/pre-commit) | `.husky/pre-commit` |
| [.husky/pre-push](.husky/pre-push) | `.husky/pre-push` |
| [LICENSE](LICENSE) | `LICENSE.lang-boilerplates` |
| この README | 参照用。製品 README を上書きしない |

コピー前に既存ファイル・symlink・Git hooksPath/フックを読み取り、差分を提示して承認を得てください。

## ツール

チェックはツールを導入しません。範囲を確認し、別途承認して利用者が導入してください（macOS の例）。

```sh
brew install --cask blender      # blender コマンドも入る
brew install uv
uv tool install ruff==0.17.0
npm install -g @gltf-transform/cli@4.5.1
```

## モデルの書き方

`models/<name>.py` が `build() -> None` を定義し、空のシーンにオブジェクトを作ります。
任意で `MAX_TRIANGLES` を定義すると面数の上限を上書きできます（既定 3,000。仮置きの値です）。

```python
import bpy

MAX_TRIANGLES = 500


def build() -> None:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.5))
```

約束事: 1単位 = 1m、原点は足元、色は頂点カラーか小さな色見本テクスチャ1枚。

書き出し:

```sh
blender -b --factory-startup --python-exit-code 1 --python scripts/build.py -- --out build
```

`build/<name>.glb` ができます。[Godot の設定](https://github.com/KendrickMalar/lang-boilerplates/blob/main/godot/mobile-game/README.md)
（godot/mobile-game）と組で使う場合は、ゲーム側の `assets/` などへコピーしてください（Godot は `.glb` を
そのまま取り込みます）。

## チェック

```sh
sh scripts/check.sh all
sh scripts/check.sh build # format|lint|test|build|all
```

| 段階 | コマンド |
| --- | --- |
| 事前確認 | blender・ruff・gltf-transform の版が一致するか |
| format | `ruff format --check models tests scripts` |
| lint | `ruff check models tests scripts` |
| test | Blender 内で `tests/test_*.py` を unittest 実行（0件は失敗） |
| build | 一時ディレクトリへ全モデルを書き出し、`gltf-transform validate` で検査して削除 |

Blender 5.2.2 は `--python` のスクリプトが例外で止まっても終了コード0を返すため、常に
`--python-exit-code 1` を付けます。モデル0件、三角形0、上限超過、例外は build の失敗です。
失敗したモデルがあっても全モデルの結果を表示してから止まります。

## テスト

`tests/test_*.py` は unittest で書きます。Blender 内で動くので `bpy` を使えます。
`models/` は `from models import cube` のように import できます。

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
Rust サーバー + TypeScript frontend では root の `check` にサーバーと frontend の全体検査を漏れなく登録します。
frontend側 package.json の check 名と root の集約 check 名を分け、相互呼び出しの再帰を避けます。
Roblox の Git root / project root の不一致は既存 guard の対象外なので、guard を外して混在対応しません。


## 検証範囲

macOS（asuka、Apple Silicon）で leaf をコピーし、正常系と異常系を手動で1回確認しました（結果は
リポジトリの progress.md）。Windows/Linux、Blender の GUI 操作、Git フックの実 push は**未検証**です。
ツールの版を上げるときは同じ確認をやり直してください。

- [Blender コマンドライン引数](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
- [ruff](https://docs.astral.sh/ruff/)
- [glTF-Transform CLI](https://gltf-transform.dev/cli)

本設定はこのリポジトリの MIT ライセンスです。
