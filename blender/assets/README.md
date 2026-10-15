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
| [.githooks/pre-commit](.githooks/pre-commit) | `.githooks/pre-commit` |
| [.githooks/pre-push](.githooks/pre-push) | `.githooks/pre-push` |
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

`build/<name>.glb` ができます。[Godot の設定](https://github.com/KendrickMalar/lang-boilerplates/blob/main/godot/mobile/README.md)
（godot/mobile）と組で使う場合は、ゲーム側の `assets/` などへコピーしてください（Godot は `.glb` を
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

## 手動 Git フック（別承認で有効化）

godot/mobile の README と同じ手順です。フックは自身の位置から leaf の root を求めます。

```sh
git config --show-origin --get-all core.hooksPath
git rev-parse --git-path hooks
chmod +x art/.githooks/pre-commit art/.githooks/pre-push art/scripts/check.sh
git config --local core.hooksPath art/.githooks
```

既存フック、global hooksPath、symlink があれば停止して相談してください。

## 検証範囲

macOS（asuka、Apple Silicon）で leaf をコピーし、正常系と異常系を手動で1回確認しました（結果は
リポジトリの progress.md）。Windows/Linux、Blender の GUI 操作、Git フックの実 push は**未検証**です。
ツールの版を上げるときは同じ確認をやり直してください。

- [Blender コマンドライン引数](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
- [ruff](https://docs.astral.sh/ruff/)
- [glTF-Transform CLI](https://gltf-transform.dev/cli)

本設定はこのリポジトリの MIT ライセンスです。
