# Godot（GDScript）と Blender Python の設定集 — 設計

> 作成日・最終更新: 2026-10-15
> 出所: ユーザーとの質疑（2026-10-15）、調査レポート「アプリゲームの言語セット選定」（https://claude.ai/artifact/VqJcnXQKhrWhRUscBzS445）、asuka（MacBook Air）での導入と動作確認（2026-10-15）。
> 目的: Scaffold（Development プロファイル）が言語別 README から、Godot のモバイルゲームと、コードで 3D モデルを作る Blender Python の設定を選び、導入できるようにします。

## 目次

1. 要約と決定事項
2. 配置・コピー契約
3. ツールと設定
4. チェックと Git フック
5. 合格基準・検証範囲
6. Scaffold への登録
7. 次のアクション
8. リスク・残論点
9. 参考元と決定ログ

## 1. 要約と決定事項

`godot/mobile/` と `blender/assets/` の2つの leaf を追加します。どちらも `scripts/check.sh` で整形・Lint・検査・テストを直列に実行します。実ツールでの検証 suite は作らず、静的検査と、実ツールでの手動確認1回にとどめます。scaffold-profiles の言語対応表に2行を追加します。

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| エンジン | **Godot 4.7.2 + 型付き GDScript** | エディタなしで一周でき、テキスト中心でエージェント向き（レポート参照）。 |
| 3D モデル | **Blender 5.2.2 LTS の Python をヘッドレス実行** | モデルをコードで作り glTF に書き出す。 |
| 構成 | **2つの leaf に分ける** | 既存の「1 leaf＝1用途で自己完結」に合わせる。Blender 側は他エンジンでも使える。 |
| 深さ | **設定・check.sh・Git フック・静的検査まで** | ユーザー選択。実ツール suite は作らない。実ツールでは手動で1回確認する。 |
| Godot のテスト | **自作の最小実行器（GUT 等は使わない）** | 第三者コードを配布しない。Roblox の Lune 実行器と同じ考え方。 |
| 型の強制 | **`untyped_declaration` 警告をエラーに** | 型なし宣言を検査で落とす。 |
| ツール導入 | **check.sh は導入しない。版が違えば止まる** | 既存 leaf と同じ。 |

## 2. 配置・コピー契約

```text
godot/
  README.md                入口
  mobile/
    README.md              配布ファイル、コピー先、導入、チェック、フック、検証範囲
    LICENSE / .editorconfig / .gitignore / .gitattributes
    project.godot
    gdlintrc
    gdformatrc
    src/.gitkeep
    tests/.gitkeep
    scripts/check.sh
    scripts/test_runner.gd
    scripts/test_context.gd
    .githooks/pre-commit
    .githooks/pre-push
blender/
  README.md                入口
  assets/
    README.md
    LICENSE / .editorconfig / .gitignore
    pyproject.toml
    models/.gitkeep
    tests/.gitkeep
    scripts/check.sh
    scripts/build.py
    scripts/test.py
    .githooks/pre-commit
    .githooks/pre-push
```

- leaf は親や兄弟に依存しません。そのフォルダだけをコピーすれば動きます。
- 製品 source・サンプルモデル・生成物（`.godot/`、`.glb`）は配布しません。
- 2つを組で使う場合は、製品リポジトリの別ディレクトリに置きます（例: `game/` に godot/mobile、`art/` に blender/assets）。書き出した `.glb` を `game/` 側へ置く手順は blender README に書きます。
- Git フックは leaf 相対（フックの置き場所から leaf の root を求める）にします。1リポジトリで両方を使う場合のフック例（両方の check.sh を呼ぶ）を godot README に書きます。
- リポジトリ直下 README の言語表と「範囲」に2行を追加します。

## 3. ツールと設定

### 3.1 版の固定

| ツール | 版 | 確認方法（check.sh の事前確認） |
| --- | --- | --- |
| Godot | 4.7.2（標準版、.NET なし） | `godot --version` が `4.7.2.stable` で始まる |
| gdtoolkit（gdlint / gdformat） | 4.5.0 | `gdlint --version` / `gdformat --version` |
| Blender | 5.2.2 LTS | `blender --version` の1行目が `Blender 5.2.2` |
| ruff | 0.17.0 | `ruff --version` |
| glTF-Transform CLI | 4.5.1 | `gltf-transform --version` |

【確度：高】asuka で導入し、版と headless 実行を確認しました（2026-10-15）。

### 3.2 godot/mobile

- `project.godot`: `config_version=5`、`config/features` に `4.7` と `Mobile`、描画方式 Mobile、ETC2/ASTC の VRAM 圧縮を有効（Android 書き出しに必要）、`debug/gdscript/warnings/untyped_declaration=2`（エラー）。キー名は実装時に Godot 4.7.2 で生成・確認します。
- `gdlintrc` / `gdformatrc`: gdtoolkit 4.5.0 の `--dump-default-config` の全内容を置き、除外ディレクトリに `.godot` と `build` を足します。行長 100、タブ。将来の版で既定が変わっても挙動を固定するため、差分だけでなく全項目を置きます（2026-10-15 改訂）。
- `.gitignore`: `/.godot/`、`/build/`、`*.tmp`、`/.verification/`、`.DS_Store`。`export_presets.cfg` は製品で管理するため除外しません。
- `.gitattributes`: 改行を LF に固定（Godot 公式の推奨に合わせる）。
- テスト規約: `tests/**/test_*.gd` は `extends RefCounted`。`func test_*(t: TestContext) -> void` を実行器が呼び、`t.expect(cond, msg)` / `t.expect_eq(a, b)` で失敗を記録します。GDScript には例外がないため、assert ではなく記録方式にします。読込み失敗、`test_*` が0件のファイル、全体で0件は失敗です。
- `TestContext` は `scripts/test_context.gd`（`class_name TestContext`）として配布します。内部クラスではテスト側から型名で参照できないためです（2026-10-15 改訂、asuka で確認）。
- テスト中の実行時エラー（null 参照など）で関数が途中終了しても、Godot は実行を続けます。check.sh が出力の `SCRIPT ERROR` を失敗として扱います。

### 3.3 blender/assets

- `pyproject.toml`: ruff の設定のみ（`target-version = "py313"`＝Blender 5.2.2 同梱の Python 3.13、`line-length = 100`、`select = ["E", "F", "W", "I", "B", "UP"]`）。パッケージ定義や依存は書きません。
- モデル規約: `models/<name>.py` が `build() -> None` を定義し、空のシーンにオブジェクトを作ります。任意で `MAX_TRIANGLES: int` を定義すると上限を上書きできます（既定 3,000。仮置きの値で、README に明記）。
- `scripts/build.py`: Blender 内で実行。`models/*.py` ごとに工場出荷状態の空シーンへ戻し、`build()` を呼び、評価後メッシュの三角形数を数え、上限超過なら失敗します。合格したら `--out` のディレクトリへ `<name>.glb` を書き出します。モデル0件は失敗です。
- `scripts/test.py`: Blender 内で `tests/test_*.py` を unittest で実行します。0件は失敗です。
- `.gitignore`: `/build/`、`__pycache__/`、`/.verification/`、`.DS_Store`、`*.blend1`。

## 4. チェックと Git フック

### 4.1 godot/mobile の check.sh

`scripts/check.sh [all|format|lint|typecheck|test]`。省略時は `all`。最初の失敗で止まり非0。

| 段階 | コマンド |
| --- | --- |
| 事前確認 | godot・gdlint・gdformat が PATH にあり版が一致。`src/` か `tests/` に `.gd` が1つ以上 |
| format | `gdformat --check src tests scripts` |
| lint | `gdlint src tests scripts` |
| typecheck | `godot --headless --path . --import` の後、各 `.gd` を `godot --headless --path . --check-only --script <file>` |
| test | `--import` の後 `godot --headless --path . --script scripts/test_runner.gd` |

Godot 4.7.2 の `--check-only` は、構文エラー・型エラー・型なし宣言でも終了コード0を返します（2026-10-15 asuka で確認）。そのため check.sh は、終了コードに加えて出力に `SCRIPT ERROR`・`Parse Error`・`Failed to load script` があれば失敗にします。test 段階も同じ判定を使います（2026-10-15 改訂）。

### 4.2 blender/assets の check.sh

`scripts/check.sh [all|format|lint|test|build]`。

| 段階 | コマンド |
| --- | --- |
| 事前確認 | blender・ruff・gltf-transform の版が一致 |
| format | `ruff format --check models tests scripts` |
| lint | `ruff check models tests scripts` |
| test | `blender -b --factory-startup --python scripts/test.py` |
| build | 一時ディレクトリへ `blender -b --factory-startup --python scripts/build.py -- --out <tmp>` → 各 `.glb` を `gltf-transform validate` → 一時ディレクトリを削除 |

Blender 5.2.2 は `--python` のスクリプトが例外で止まっても終了コード0を返します（2026-10-15 asuka で確認）。check.sh は `--python-exit-code 1` を付け、`build.py` と `test.py` は失敗時に `sys.exit(1)` を明示します。`gltf-transform validate` は不正な glTF で終了コード1を返すことを確認済みです。

### 4.3 Git フック

- `pre-commit`: `check.sh format` と `lint`。`pre-push`: `check.sh all`。
- フックはフック自身の位置から leaf root へ移動して実行します（サブディレクトリ配置に対応）。
- コピーだけでは有効になりません。既存 leaf と同じく、hooksPath と既存フックを確認し、承認後に `git config --local core.hooksPath <leaf>/.githooks` を実行します。

## 5. 合格基準・検証範囲

### 5.1 追加する静的検査

- `tests/native/test_static_godot.py`: 版の文字列、`project.godot` の必須キー、`.gitignore`、製品 source の混入なし（配布する `.gd` は `scripts/test_runner.gd` だけ）、README のリンクと必須語。
- `tests/native/test_static_blender.py`: 版の文字列、ruff 設定、`.gitignore`、配布する `.py` は `scripts/` の2つだけ、`sys.exit` と `--python-exit-code` の存在、README。
- `tests/native/test_catalog.py`: 2 leaf の配布ファイル一覧の完全一致、独立コピー、フックが `scripts/check.sh` を呼ぶこと、言語→leaf の案内。
- `package.json` の `test:native:static` に2つを追加。`pnpm test` は変更しません。

### 5.2 手動確認（asuka、1回）

leaf を一時ディレクトリへコピーし、次を確認して結果を README の「検証範囲」と progress.md に記録します。

| 種類 | 入力 | 期待 |
| --- | --- | --- |
| Godot 正常系 | 型付きの関数1つ＋テスト1つ | `all` が 0 |
| Godot 異常系 | 整形崩れ／lint 違反／型なし宣言／失敗テスト／テスト0件 | 該当段階で非0 |
| Blender 正常系 | 立方体モデル1つ＋テスト1つ | `all` が 0、`.glb` が validate を通る |
| Blender 異常系 | 整形崩れ／lint 違反／上限超過モデル／例外を投げるモデル／テスト0件 | 該当段階で非0 |
| 共通 | ツールの版違い（PATH に別版） | 事前確認で非0 |

### 5.3 検証しない範囲

Android/iOS への書き出しと実機、Windows/Linux、Godot エディタでの操作、Git フックの実 push（手順のみ記載）。README に未検証と明記します。

## 6. Scaffold への登録

- 対象: `scaffold-profiles/src/profile/skills/scaffold/references/basic-design.md` の「言語の選定」表。
- 追加行: `Godot（GDScript）` → `godot/README.md`、`Blender Python（3D モデル）` → `blender/README.md`（GitHub の main を指す既存形式）。
- 注意書きを1つ追加: Godot ゲームは `godot/mobile` を使い、3D モデルをコードで作る場合は `blender/assets` を組で使う。Godot・Blender・gdtoolkit・ruff・glTF-Transform の導入は global tool の変更を含むため、この工程で承認を得て記録する。
- `dist/` は scaffold-profiles の手順で再生成し、同リポジトリのテストを通します。作業は同リポジトリの worktree で行います。
- lang-boilerplates の main へ統合して push した後に登録します（リンク先が存在してから）。

## 7. 次のアクション

- [ ] 本設計書のユーザーレビュー
- [ ] 実装計画の作成
- [ ] 実装（静的検査は TDD）
- [ ] asuka での手動確認と記録
- [ ] main への統合・push（別承認）
- [ ] scaffold-profiles への登録・push（別承認）
- [ ] asuka の2リポジトリを pull

## 8. リスク・残論点

| リスク | 影響 | 対策 |
| --- | --- | --- |
| `--check-only` が型エラーでも0を返す（確認済み） | 終了コードだけでは素通り | 出力の `SCRIPT ERROR` 等で判定する。Godot 更新時に出力形式が変わらないか手動確認で見る。 |
| Blender の例外で終了コード0（確認済み） | 失敗を見逃す | `sys.exit(1)` の明示と `--python-exit-code 1`。手動確認で異常系を試す。 |
| gdtoolkit が Godot 4.7 の新構文に未対応 | 正しいコードが lint/format で落ちる | 手動確認で検知。発生時は README に回避策を記載。 |
| 実ツール suite がない | 版更新時の退行を自動で検知できない | 版更新のたびに 5.2 の手動確認をやり直すと README に書く。 |
| 面数上限 3,000 は仮置き | ゲームによって過大・過小 | モデルごとに `MAX_TRIANGLES` で上書き可能にする。 |

残る空白:

- Android/iOS 書き出し設定（`export_presets.cfg`、署名）は扱いません。
- 1リポジトリで2 leaf を使うときのフック統合は README の例止まりです。

## 9. 参考元と決定ログ

- Godot 4.7 リリースノート: https://godotengine.org/releases/4.7/
- Godot コマンドライン: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- Godot 描画方式: https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html
- gdtoolkit: https://github.com/Scony/godot-gdscript-toolkit
- Blender コマンドライン引数: https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
- ruff: https://docs.astral.sh/ruff/
- glTF-Transform CLI: https://gltf-transform.dev/cli

| 日付 | 決定 |
| --- | --- |
| 2026-10-15 | Godot 4.7 + GDScript と Blender Python を採用（調査レポート） |
| 2026-10-15 | ひな形はいったん見送り → scaffold が対応表外の言語で止まるため、設定と check.sh までの leaf を作り対応表に登録すると決定 |
| 2026-10-15 | 2 leaf に分割、自作テスト実行器、手動確認1回、静的検査のみの方針を承認 |
| 2026-10-15 | asuka の事前確認で改訂: `--check-only` の終了コードが当てにならないため出力判定、`TestContext` を別ファイル化、gdtoolkit 設定は全項目を置く |
