# Godot と Blender Python 設定集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `godot/mobile` と `blender/assets` の自己完結 leaf を追加し、scaffold-profiles の言語対応表に登録する。

**Architecture:** 既存 Roblox leaf と同じ形（版固定・POSIX sh の `scripts/check.sh`・手動有効化の Git フック・Python の静的検査）。実ツール suite は作らず、asuka で leaf をコピーして正常系・異常系を手動確認1回。フックは leaf 相対。

**Tech Stack:** Godot 4.7.2 / GDScript、gdtoolkit 4.5.0、Blender 5.2.2 LTS（Python 3.13）、ruff 0.17.0、glTF-Transform CLI 4.5.1、Python unittest（静的検査）、POSIX sh。

**Spec:** `docs/superpowers/specs/2026-10-15-godot-blender-settings-design.md`

## Global Constraints

- 版: Godot `4.7.2`（`godot --version` が `4.7.2.stable` で始まる）、gdtoolkit `4.5.0`、Blender `5.2.2`（`blender --version` 1行目が `Blender 5.2.2` で始まる）、ruff `0.17.0`、glTF-Transform `4.5.1`。
- check.sh はツール・依存を導入しない。グローバル設定を変えない。版違い・不在は非0。
- leaf は親・兄弟に依存しない。製品 source・サンプル・生成物（`.godot/`、`.glb`）を配布しない。
- 配布する `.gd` は `scripts/test_runner.gd` と `scripts/test_context.gd` のみ。配布する `.py` は `scripts/build.py` と `scripts/test.py` のみ。
- Godot の `--check-only` は失敗でも exit 0。出力の `SCRIPT ERROR` / `Parse Error` / `Failed to load script` で判定する。
- Blender は `-b --factory-startup --python-exit-code 1 --python <script> -- <args>` で実行する。
- 面数上限の既定は `3000`（仮置き）。モデルごとに `MAX_TRIANGLES` で上書き。
- 文書は日本語、です・ます調。LICENSE は既存 leaf の MIT をそのまま複製。
- `pnpm test`（TypeScript suite）は変更しない。
- main 統合・push・scaffold-profiles の push・asuka の pull は、それぞれ実行前に AskUserQuestion で承認を得る。
- コミットに AI 帰属トレーラーを付けない。

## Review Focus

1. テスト中の実行時エラー（null 参照など）で Godot が関数を途中終了しても、test 段階は非0になるべき → Task 4 の手動確認ケース「実行時エラー」。
2. `.gd` ファイル名や leaf の置き場所に空白が含まれても check.sh が壊れないべき → check.sh は `find ... | while IFS= read -r` で処理し、Task 4 で空白入りパスにコピーして実行。
3. Blender のモデルが例外を投げても、他のモデルの結果を表示したうえで build 段階は非0になるべき → Task 4 ケース「例外モデル＋正常モデル」。
4. メッシュを作らない `build()`（空シーン）は合格にならないべき → build.py が三角形0を失敗にし、Task 4 で確認。
5. PATH 上に別版のツールがあると事前確認で止まるべき → Task 4 で偽の `godot` / `ruff` を PATH 先頭に置いて確認。

---

### Task 1: godot/mobile leaf

**Files:**
- Create: `godot/README.md`, `godot/mobile/README.md`, `godot/mobile/LICENSE`, `godot/mobile/.editorconfig`, `godot/mobile/.gitignore`, `godot/mobile/.gitattributes`, `godot/mobile/project.godot`, `godot/mobile/gdlintrc`, `godot/mobile/gdformatrc`, `godot/mobile/src/.gitkeep`, `godot/mobile/tests/.gitkeep`, `godot/mobile/scripts/check.sh`, `godot/mobile/scripts/test_runner.gd`, `godot/mobile/scripts/test_context.gd`, `godot/mobile/.githooks/pre-commit`, `godot/mobile/.githooks/pre-push`
- Create: `tests/native/test_static_godot.py`

**Interfaces:**
- Produces: `sh scripts/check.sh [format|lint|typecheck|test|all]`; テスト規約 `tests/**/test_*.gd` が `extends RefCounted` で `func test_*(t: TestContext) -> void`; `TestContext.expect(condition: bool, message: String)`、`TestContext.expect_eq(actual: Variant, expected: Variant, message: String = "")`、`TestContext.failures: Array[String]`。

- [ ] **Step 1: 失敗する静的検査を書く** — `tests/native/test_static_godot.py`

```python
"""Catch missing/non-self-contained Godot settings and weakened quality rules."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "godot/mobile"
INSTALLERS = ["brew install", "pip install", "uv tool install", "pipx install", "npm install"]


class StaticGodotTests(unittest.TestCase):
    def test_tool_versions_are_pinned_and_never_installed(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("GODOT_VERSION=4.7.2", text)
        self.assertIn("GDTOOLKIT_VERSION=4.5.0", text)
        for line in text.splitlines():
            for command in INSTALLERS:
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_project_settings(self):
        lines = (LEAF / "project.godot").read_text().splitlines()
        for expected in ["config_version=5",
                         'config/features=PackedStringArray("4.7", "Mobile")',
                         "gdscript/warnings/untyped_declaration=2",
                         'renderer/rendering_method="mobile"',
                         "textures/vram_compression/import_etc2_astc=true"]:
            self.assertIn(expected, lines)

    def test_check_judges_godot_output_not_only_exit_code(self):
        text = (LEAF / "scripts/check.sh").read_text()
        for marker in ["SCRIPT ERROR", "Parse Error", "Failed to load script", "--check-only",
                       "--import", "scripts/test_runner.gd"]:
            self.assertIn(marker, text)

    def test_gdtoolkit_configs_pin_full_defaults(self):
        lint = (LEAF / "gdlintrc").read_text()
        for entry in ["max-line-length: 100", "tab-characters: 1", "  .godot: null",
                      "  build: null", "function-arguments-number: 10"]:
            self.assertIn(entry, lint)
        fmt = (LEAF / "gdformatrc").read_text()
        for entry in ["line_length: 100", "use_spaces: null", "  .godot: null"]:
            self.assertIn(entry, fmt)

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/.godot/", "/build/", "/.verification/", ".DS_Store"]:
            self.assertIn(entry, ignored)
        self.assertNotIn("export_presets.cfg", ignored)
        scripts = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.gd"))
        self.assertEqual(scripts, ["scripts/test_context.gd", "scripts/test_runner.gd"])
        for empty in ["src", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])
        self.assertFalse((LEAF / ".godot").exists())

    def test_hooks_are_leaf_relative(self):
        for hook in ["pre-commit", "pre-push"]:
            text = (LEAF / ".githooks" / hook).read_text()
            self.assertIn('dirname -- "$0"', text)
            self.assertNotIn("--show-toplevel", text)
            self.assertIn("scripts/check.sh", text)

    def test_readme_links_resolve(self):
        text = (LEAF / "README.md").read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((LEAF / link).exists(), link)
        for phrase in ["gdlint", "untyped_declaration", "TestContext", "SCRIPT ERROR",
                       "blender/assets", "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 失敗を確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_godot`
Expected: FAIL（`FileNotFoundError: .../godot/mobile/scripts/check.sh` など）

- [ ] **Step 3: leaf の設定ファイルを作る**

`godot/mobile/LICENSE`: `cp roblox/rojo/LICENSE godot/mobile/LICENSE`

`godot/mobile/project.godot`:
```ini
; Godot 4.7 project settings for a mobile game. Rename config/name for the product.
config_version=5

[application]

config/name="Game"
config/features=PackedStringArray("4.7", "Mobile")

[debug]

gdscript/warnings/untyped_declaration=2

[rendering]

renderer/rendering_method="mobile"
textures/vram_compression/import_etc2_astc=true
```

`godot/mobile/.editorconfig`:
```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4
trim_trailing_whitespace = true

[*.gd]
indent_style = tab

[*.md]
trim_trailing_whitespace = false
```

`godot/mobile/.gitattributes`:
```
* text=auto eol=lf
```

`godot/mobile/.gitignore`:
```
/.godot/
/build/
*.tmp
/.verification/
.DS_Store
# export_presets.cfg belongs in the consuming project repository.
```

`godot/mobile/gdlintrc`（gdtoolkit 4.5.0 の `gdlint --dump-default-config` の全内容。`.godot` と `build` を除外に追加）:
```yaml
class-definitions-order:
- tools
- classnames
- extends
- docstrings
- signals
- enums
- consts
- staticvars
- exports
- pubvars
- prvvars
- onreadypubvars
- onreadyprvvars
- others
class-load-variable-name: (([A-Z][a-z0-9]*)+|_?[a-z][a-z0-9]*(_[a-z0-9]+)*)
class-name: ([A-Z][a-z0-9]*)+
class-variable-name: _?[a-z][a-z0-9]*(_[a-z0-9]+)*
comparison-with-itself: null
constant-name: _?[A-Z][A-Z0-9]*(_[A-Z0-9]+)*
disable: []
duplicated-load: null
enum-element-name: '[A-Z][A-Z0-9]*(_[A-Z0-9]+)*'
enum-name: ([A-Z][a-z0-9]*)+
excluded_directories: !!set
  .git: null
  .godot: null
  build: null
expression-not-assigned: null
function-argument-name: _?[a-z][a-z0-9]*(_[a-z0-9]+)*
function-arguments-number: 10
function-name: (_on_([A-Z][a-z0-9]*)+(_[a-z0-9]+)*|_?[a-z][a-z0-9]*(_[a-z0-9]+)*)
function-preload-variable-name: ([A-Z][a-z0-9]*)+
function-variable-name: '[a-z][a-z0-9]*(_[a-z0-9]+)*'
load-constant-name: (([A-Z][a-z0-9]*)+|_?[A-Z][A-Z0-9]*(_[A-Z0-9]+)*)
loop-variable-name: _?[a-z][a-z0-9]*(_[a-z0-9]+)*
max-file-lines: 1000
max-line-length: 100
max-public-methods: 20
max-returns: 6
mixed-tabs-and-spaces: null
no-elif-return: null
no-else-return: null
signal-name: '[a-z][a-z0-9]*(_[a-z0-9]+)*'
sub-class-name: _?([A-Z][a-z0-9]*)+
tab-characters: 1
trailing-whitespace: null
unnecessary-pass: null
unused-argument: null
```

`godot/mobile/gdformatrc`:
```yaml
excluded_directories: !!set
  .git: null
  .godot: null
  build: null
line_length: 100
safety_checks: null
use_spaces: null
```

`godot/mobile/src/.gitkeep`, `godot/mobile/tests/.gitkeep`: 空ファイル。

- [ ] **Step 4: TestContext と実行器を作る**

`godot/mobile/scripts/test_context.gd`:
```gdscript
class_name TestContext
extends RefCounted
## Collects failures for one test method. GDScript has no exceptions, so tests record them.

var failures: Array[String] = []


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func expect_eq(actual: Variant, expected: Variant, message: String = "") -> void:
	if typeof(actual) == typeof(expected) and actual == expected:
		return
	var prefix: String = message + ": " if message != "" else ""
	failures.append("%sexpected %s, got %s" % [prefix, var_to_str(expected), var_to_str(actual)])
```

`godot/mobile/scripts/test_runner.gd`:
```gdscript
extends SceneTree
## Minimal runner: tests/**/test_*.gd extend RefCounted and define
## func test_*(t: TestContext) -> void. Zero tests, load failures and recorded failures exit 1.

const TEST_DIR: String = "res://tests"


func _initialize() -> void:
	var files: Array[String] = []
	_collect(TEST_DIR, files)
	files.sort()
	var passed: int = 0
	var failed: int = 0
	for path: String in files:
		var script: Script = load(path) as Script
		if script == null or not script.can_instantiate():
			failed += 1
			print("FAIL %s: cannot load test script" % path)
			continue
		var names: Array[String] = []
		for method: Dictionary in script.get_script_method_list():
			var method_name: String = method["name"]
			if method_name.begins_with("test_"):
				names.append(method_name)
		if names.is_empty():
			failed += 1
			print("FAIL %s: no test_* methods" % path)
			continue
		names.sort()
		var suite: Object = script.new()
		for method_name: String in names:
			var t: TestContext = TestContext.new()
			suite.call(method_name, t)
			if t.failures.is_empty():
				passed += 1
				print("PASS %s :: %s" % [path, method_name])
			else:
				failed += 1
				for message: String in t.failures:
					print("FAIL %s :: %s: %s" % [path, method_name, message])
	print("%d passed, %d failed" % [passed, failed])
	if passed + failed == 0:
		print("FAIL no tests found under %s" % TEST_DIR)
		quit(1)
		return
	quit(1 if failed > 0 else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return
	for sub: String in dir.get_directories():
		_collect(dir_path.path_join(sub), out)
	for file: String in dir.get_files():
		if file.begins_with("test_") and file.ends_with(".gd"):
			out.append(dir_path.path_join(file))
```

- [ ] **Step 5: check.sh とフックを作る**

`godot/mobile/scripts/check.sh`:
```sh
#!/bin/sh
# Godot project checks. Never installs tools or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|typecheck|test|all]'
case "$stage" in format|lint|typecheck|test|all) ;; *) fail "unknown stage: $stage" ;; esac
GODOT_VERSION=4.7.2
GDTOOLKIT_VERSION=4.5.0

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is missing; install it (see README) and check PATH"; }
need godot
need gdlint
need gdformat
actual=$(godot --version </dev/null 2>&1) || fail "cannot read godot version: $actual"
printf '%s\n' "tool: $(command -v godot) $actual"
case "$actual" in "$GODOT_VERSION.stable"*) ;; *) fail "godot must be $GODOT_VERSION (found: $actual)" ;; esac
for tool in gdlint gdformat; do
    actual=$("$tool" --version </dev/null 2>&1) || fail "cannot read $tool version: $actual"
    printf '%s\n' "tool: $(command -v "$tool") $actual"
    [ "$actual" = "$tool $GDTOOLKIT_VERSION" ] || fail "$tool must be $GDTOOLKIT_VERSION (found: $actual)"
done
find src tests -type f -name '*.gd' | grep -q . || fail 'no GDScript under src/ or tests/'

# Godot exits 0 on parse/type errors and keeps running after runtime script errors,
# so the output is part of the verdict.
godot_run() {
    log=$(mktemp)
    status=0
    godot --headless --path . "$@" >"$log" 2>&1 || status=$?
    cat "$log"
    if [ "$status" -ne 0 ] || grep -E 'SCRIPT ERROR|Parse Error|Failed to load script' "$log" >/dev/null; then
        rm -f "$log"
        return 1
    fi
    rm -f "$log"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) gdformat --check src tests scripts ;;
        lint) gdlint src tests scripts ;;
        typecheck)
            godot_run --import || fail 'godot import failed'
            find src tests scripts -type f -name '*.gd' | sort | while IFS= read -r file; do
                godot_run --check-only --script "$file" || fail "typecheck failed: $file"
            done
            ;;
        test)
            godot_run --import || fail 'godot import failed'
            godot_run --script scripts/test_runner.gd || fail 'tests failed'
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint typecheck test; do run_stage "$step"; done
else
    run_stage "$stage"
fi
```

`godot/mobile/.githooks/pre-commit`:
```sh
#!/bin/sh
# Manual opt-in only. Runs this leaf's check from wherever the leaf is placed.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh scripts/check.sh format
exec sh scripts/check.sh lint
```

`godot/mobile/.githooks/pre-push`:
```sh
#!/bin/sh
# Manual opt-in only. Runs this leaf's check from wherever the leaf is placed.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
exec sh scripts/check.sh all
```

Run: `chmod +x godot/mobile/scripts/check.sh godot/mobile/.githooks/*`

- [ ] **Step 6: README を書く**

`godot/README.md`:
```markdown
# Godot（GDScript）設定

- [モバイルゲームの品質設定](mobile/README.md): Godot 4.7.2・gdtoolkit 4.5.0。型付き GDScript を
  強制し、ヘッドレスで検査とテストを行うモバイルゲーム用です。

3D モデルをコードで作る場合は [Blender Python の設定](../blender/README.md) と組で使います。
各 leaf は自己完結し、製品 source・生成物は配布しません。macOS（asuka）で手動確認済みで、
Android/iOS 書き出しと Windows/Linux は未検証です。
```

`godot/mobile/README.md`:
````markdown
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
````

- [ ] **Step 7: 静的検査が通ることを確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_godot`
Expected: `Ran 7 tests` … `OK`

- [ ] **Step 8: asuka で書式と構文を確認**（実ツール。結果に合わせて修正）

```sh
rsync -a --delete godot/mobile/ asuka@100.125.45.215:/tmp/lbp-godot-fmt/
ssh asuka@100.125.45.215 "zsh -lc 'cd /tmp/lbp-godot-fmt && gdformat --check scripts && gdlint scripts && godot --headless --path . --import 2>&1 | grep -E \"SCRIPT ERROR|Parse Error\"; for f in scripts/*.gd; do godot --headless --path . --check-only --script \$f 2>&1 | grep -E \"SCRIPT ERROR|Parse Error\"; done; echo done; cd /; rm -rf /tmp/lbp-godot-fmt'"
```
Expected: `gdformat` と `gdlint` が成功し、`SCRIPT ERROR`/`Parse Error` の行が出ずに `done`。
gdformat が書き換えを求めた場合は、asuka で `gdformat scripts` した結果を手元へ反映してから再実行する。

- [ ] **Step 9: Commit**

```bash
git add godot tests/native/test_static_godot.py
git commit -m "feat: add Godot mobile leaf settings"
```

---

### Task 2: blender/assets leaf

**Files:**
- Create: `blender/README.md`, `blender/assets/README.md`, `blender/assets/LICENSE`, `blender/assets/.editorconfig`, `blender/assets/.gitignore`, `blender/assets/pyproject.toml`, `blender/assets/models/.gitkeep`, `blender/assets/tests/.gitkeep`, `blender/assets/scripts/check.sh`, `blender/assets/scripts/build.py`, `blender/assets/scripts/test.py`, `blender/assets/.githooks/pre-commit`, `blender/assets/.githooks/pre-push`
- Create: `tests/native/test_static_blender.py`

**Interfaces:**
- Produces: `sh scripts/check.sh [format|lint|test|build|all]`; モデル規約 `models/<name>.py` が `build() -> None` と任意の `MAX_TRIANGLES: int`; `blender -b --factory-startup --python-exit-code 1 --python scripts/build.py -- --out DIR` が `DIR/<name>.glb` を出す。

- [ ] **Step 1: 失敗する静的検査を書く** — `tests/native/test_static_blender.py`

```python
"""Catch missing/non-self-contained Blender asset settings and weakened checks."""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "blender/assets"
INSTALLERS = ["brew install", "pip install", "uv tool install", "pipx install", "npm install"]


class StaticBlenderTests(unittest.TestCase):
    def test_tool_versions_are_pinned_and_never_installed(self):
        text = (LEAF / "scripts/check.sh").read_text()
        for pin in ["BLENDER_VERSION=5.2.2", "RUFF_VERSION=0.17.0", "GLTF_TRANSFORM_VERSION=4.5.1"]:
            self.assertIn(pin, text)
        for line in text.splitlines():
            for command in INSTALLERS:
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_blender_failures_reach_the_exit_code(self):
        check = (LEAF / "scripts/check.sh").read_text()
        for marker in ["--python-exit-code 1", "--factory-startup", "gltf-transform validate"]:
            self.assertIn(marker, check)
        for script in ["build.py", "test.py"]:
            self.assertIn("sys.exit(main())", (LEAF / "scripts" / script).read_text())

    def test_ruff_settings_match_blender_python(self):
        config = tomllib.loads((LEAF / "pyproject.toml").read_text())
        self.assertEqual(set(config), {"tool"})
        ruff = config["tool"]["ruff"]
        self.assertEqual(ruff["target-version"], "py313")
        self.assertEqual(ruff["line-length"], 100)
        self.assertEqual(ruff["lint"]["select"], ["E", "F", "W", "I", "B", "UP"])

    def test_triangle_budget_default(self):
        text = (LEAF / "scripts/build.py").read_text()
        self.assertIn("DEFAULT_MAX_TRIANGLES = 3000", text)
        self.assertIn("MAX_TRIANGLES", text)

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/build/", "__pycache__/", "/.verification/", ".DS_Store", "*.blend1"]:
            self.assertIn(entry, ignored)
        python = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.py"))
        self.assertEqual(python, ["scripts/build.py", "scripts/test.py"])
        for empty in ["models", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])
        self.assertEqual(list(LEAF.rglob("*.glb")), [])

    def test_hooks_are_leaf_relative(self):
        for hook in ["pre-commit", "pre-push"]:
            text = (LEAF / ".githooks" / hook).read_text()
            self.assertIn('dirname -- "$0"', text)
            self.assertNotIn("--show-toplevel", text)
            self.assertIn("scripts/check.sh", text)

    def test_readme_links_resolve(self):
        text = (LEAF / "README.md").read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((LEAF / link).exists(), link)
        for phrase in ["MAX_TRIANGLES", "build()", "--python-exit-code", "godot/mobile", "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 失敗を確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_blender`
Expected: FAIL（`FileNotFoundError: .../blender/assets/scripts/check.sh` など）

- [ ] **Step 3: 設定ファイルを作る**

`blender/assets/LICENSE`: `cp roblox/rojo/LICENSE blender/assets/LICENSE`

`blender/assets/pyproject.toml`:
```toml
# ruff settings for Blender 5.2.2 LTS scripts (bundled Python 3.13). No package metadata.
[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
```

`blender/assets/.editorconfig`:
```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false
```

`blender/assets/.gitignore`:
```
/build/
__pycache__/
*.blend1
/.verification/
.DS_Store
```

`blender/assets/models/.gitkeep`, `blender/assets/tests/.gitkeep`: 空ファイル。

- [ ] **Step 4: build.py と test.py を作る**

`blender/assets/scripts/build.py`:
```python
"""Build every models/<name>.py into <out>/<name>.glb inside headless Blender.

Usage: blender -b --factory-startup --python-exit-code 1 --python scripts/build.py -- --out DIR
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import bpy

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_TRIANGLES = 3000


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="build.py")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def load_model(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"models.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"{path.name}: cannot load module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build", None)):
        raise ValueError(f"{path.name}: define build() -> None")
    return module


def triangle_count() -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        total += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    return total


def build_one(path: Path, out: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    module = load_model(path)
    module.build()
    limit = getattr(module, "MAX_TRIANGLES", DEFAULT_MAX_TRIANGLES)
    count = triangle_count()
    if count == 0:
        raise ValueError(f"{path.name}: build() created no mesh triangles")
    if count > limit:
        raise ValueError(f"{path.name}: {count} triangles exceeds MAX_TRIANGLES={limit}")
    target = out / f"{path.stem}.glb"
    bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB")
    print(f"BUILT {target.name} ({count} triangles)")


def main() -> int:
    args = parse_args()
    models = sorted(p for p in (ROOT / "models").glob("*.py") if not p.name.startswith("_"))
    if not models:
        print("FAIL no models/*.py found")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for path in models:
        try:
            build_one(path, args.out)
        except Exception as error:  # report every model, then fail
            failed += 1
            print(f"FAIL {path.name}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

`blender/assets/scripts/test.py`:
```python
"""Run tests/test_*.py with unittest inside headless Blender. Zero tests fail.

Usage: blender -b --factory-startup --python-exit-code 1 --python scripts/test.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    if suite.countTestCases() == 0:
        print("FAIL no tests found under tests/")
        return 1
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: check.sh とフックを作る**

`blender/assets/scripts/check.sh`:
```sh
#!/bin/sh
# Blender asset checks. Never installs tools or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|test|build|all]'
case "$stage" in format|lint|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
BLENDER_VERSION=5.2.2
RUFF_VERSION=0.17.0
GLTF_TRANSFORM_VERSION=4.5.1

need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is missing; install it (see README) and check PATH"; }
need blender
need ruff
need gltf-transform
actual=$(blender --version </dev/null 2>&1 | head -n 1) || fail 'cannot read blender version'
printf '%s\n' "tool: $(command -v blender) $actual"
case "$actual" in "Blender $BLENDER_VERSION"|"Blender $BLENDER_VERSION "*) ;; *) fail "blender must be $BLENDER_VERSION (found: $actual)" ;; esac
actual=$(ruff --version </dev/null 2>&1) || fail "cannot read ruff version: $actual"
printf '%s\n' "tool: $(command -v ruff) $actual"
[ "$actual" = "ruff $RUFF_VERSION" ] || fail "ruff must be $RUFF_VERSION (found: $actual)"
actual=$(gltf-transform --version </dev/null 2>&1) || fail "cannot read gltf-transform version: $actual"
printf '%s\n' "tool: $(command -v gltf-transform) $actual"
[ "$actual" = "$GLTF_TRANSFORM_VERSION" ] || fail "gltf-transform must be $GLTF_TRANSFORM_VERSION (found: $actual)"

# Blender exits 0 when a --python script raises unless --python-exit-code is set.
run_blender() {
    script=$1
    shift
    blender -b --factory-startup --python-exit-code 1 --python "$script" -- "$@"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) ruff format --check models tests scripts ;;
        lint) ruff check models tests scripts ;;
        test) run_blender scripts/test.py || fail 'tests failed' ;;
        build)
            out=$(mktemp -d)
            if ! run_blender scripts/build.py --out "$out"; then rm -rf "$out"; fail 'build failed'; fi
            found=0
            for glb in "$out"/*.glb; do
                [ -f "$glb" ] || continue
                found=1
                if ! gltf-transform validate "$glb"; then rm -rf "$out"; fail "invalid glTF: $(basename "$glb")"; fi
            done
            rm -rf "$out"
            [ "$found" -eq 1 ] || fail 'build produced no .glb'
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint test build; do run_stage "$step"; done
else
    run_stage "$stage"
fi
```

`blender/assets/.githooks/pre-commit` と `pre-push`: Task 1 Step 5 の2ファイルと同一内容（leaf 相対で `sh scripts/check.sh format` + `exec sh scripts/check.sh lint`、`exec sh scripts/check.sh all`）。全文:

```sh
#!/bin/sh
# Manual opt-in only. Runs this leaf's check from wherever the leaf is placed.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
sh scripts/check.sh format
exec sh scripts/check.sh lint
```

```sh
#!/bin/sh
# Manual opt-in only. Runs this leaf's check from wherever the leaf is placed.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
exec sh scripts/check.sh all
```

Run: `chmod +x blender/assets/scripts/check.sh blender/assets/.githooks/*`

- [ ] **Step 6: README を書く**

`blender/README.md`:
```markdown
# Blender Python 設定

- [3D モデルをコードで作る設定](assets/README.md): Blender 5.2.2 LTS をヘッドレスで動かし、
  Python で作ったモデルを glTF（`.glb`）に書き出して検査します。

Godot のゲームでは [Godot の設定](../godot/README.md) と組で使います。各 leaf は自己完結し、
サンプルモデル・生成物は配布しません。macOS（asuka）で手動確認済みで、Windows/Linux は未検証です。
```

`blender/assets/README.md`:
````markdown
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
````

- [ ] **Step 7: 静的検査が通ることを確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_blender`
Expected: `Ran 7 tests` … `OK`

- [ ] **Step 8: asuka で ruff を確認**

```sh
rsync -a --delete blender/assets/ asuka@100.125.45.215:/tmp/lbp-blender-fmt/
ssh asuka@100.125.45.215 "zsh -lc 'cd /tmp/lbp-blender-fmt && ruff format --check scripts && ruff check scripts; echo exit:\$?; cd /; rm -rf /tmp/lbp-blender-fmt'"
```
Expected: `exit:0`。ruff が指摘したら修正して再実行。

- [ ] **Step 9: Commit**

```bash
git add blender tests/native/test_static_blender.py
git commit -m "feat: add Blender asset leaf settings"
```

---

### Task 3: カタログ・root README・package.json

**Files:**
- Modify: `tests/native/test_catalog.py`（ファイル一覧・言語案内・suite 名）
- Modify: `README.md`（言語表・範囲）
- Modify: `package.json`（`test:native:static`）

**Interfaces:**
- Consumes: Task 1・2 の leaf ファイル一覧。

- [ ] **Step 1: 失敗するカタログ検査を書く** — `tests/native/test_catalog.py` に追加・変更

`ROBLOX_FILES` の定義の直後に追加:
```python
GODOT_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', '.gitattributes',
               'project.godot', 'gdlintrc', 'gdformatrc', 'src/.gitkeep', 'tests/.gitkeep',
               'scripts/check.sh', 'scripts/test_runner.gd', 'scripts/test_context.gd',
               '.githooks/pre-commit', '.githooks/pre-push'}
BLENDER_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', 'pyproject.toml',
                 'models/.gitkeep', 'tests/.gitkeep', 'scripts/check.sh', 'scripts/build.py',
                 'scripts/test.py', '.githooks/pre-commit', '.githooks/pre-push'}
```

`test_root_language_leaf_navigation` のリストを置き換え:
```python
        for language, leaves in [('rust', ['tauri']), ('swift', ['macos', 'ios']),
                                 ('roblox', ['rojo']), ('godot', ['mobile']),
                                 ('blender', ['assets'])]:
```

`test_independent_copy_exact_inventory_and_local_references` のリストを置き換え:
```python
        for name, expected in [('rust/tauri', RUST_FILES), ('swift/macos', SWIFT_FILES),
                               ('swift/ios', SWIFT_FILES), ('roblox/rojo', ROBLOX_FILES),
                               ('godot/mobile', GODOT_FILES), ('blender/assets', BLENDER_FILES)]:
```

`test_explicit_nonempty_suites_preserve_typescript_entry` の最後の行の後に追加:
```python
        self.assertIn('test_static_godot', scripts['test:native:static'])
        self.assertIn('test_static_blender', scripts['test:native:static'])
```

- [ ] **Step 2: 失敗を確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_catalog`
Expected: FAIL（root README に `./godot/README.md` が無い、`test_static_godot` が package.json に無い）

- [ ] **Step 3: root README と package.json を更新**

`README.md` の言語表の Roblox 行の後に追加:
```markdown
| Godot（GDScript） | [godot/README.md](./godot/README.md) |
| Blender Python（3D モデル） | [blender/README.md](./blender/README.md) |
```

`README.md` の「## 範囲」の Roblox 行の後に追加:
```markdown
- Godot: モバイルゲーム用（Godot4.7.2/gdtoolkit4.5.0）。型付き GDScript を強制し、ヘッドレスで検査とテスト。asuka で手動確認、実ツール suite なし。
- Blender: 3D モデルをコードで作る用（Blender5.2.2 LTS/ruff0.17.0/glTF-Transform4.5.1）。glTF 書き出しと検査。asuka で手動確認、実ツール suite なし。
```

`package.json` の `test:native:static` を置き換え:
```json
    "test:native:static": "python3 -m tests.native.test_catalog tests.native.test_catalog tests.native.test_static_rust tests.native.test_static_swift tests.native.test_static_roblox tests.native.test_static_godot tests.native.test_static_blender tests.native.test_hooks.HookContractTests",
```

- [ ] **Step 4: 通ることを確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_catalog tests.native.test_static_rust tests.native.test_static_swift tests.native.test_static_roblox tests.native.test_static_godot tests.native.test_static_blender tests.native.test_hooks.HookContractTests`
Expected: `Ran 33 tests` … `OK`（既存19件＋Godot 7件＋Blender 7件）

- [ ] **Step 5: TypeScript の静的検査も壊れていないことを確認**

Run: `pnpm install --ignore-scripts --engine-strict --store-dir .verification/pnpm-store && pnpm test:static`
Expected: 全件 pass。依存導入が環境要因で失敗した場合は結果をそのまま記録し、変更が TypeScript 側に及ばないこと（`git diff --stat` に typescript/ と tests/*.mjs が無い）を示す。

- [ ] **Step 6: Commit**

```bash
git add tests/native/test_catalog.py README.md package.json
git commit -m "feat: register Godot and Blender leaves in catalog"
```

---

### Task 4: asuka での手動確認と記録

**Files:**
- Modify: `progress.md`（末尾に「Godot / Blender」節）
- 一時: `.verification/manual/run-godot-blender.sh`（Git 管理外。`.verification/` は ignore 済み）

**Interfaces:**
- Consumes: Task 1・2 の check.sh、TestContext API、モデル規約。

- [ ] **Step 1: 確認スクリプトを書く** — `.verification/manual/run-godot-blender.sh`

```sh
#!/bin/zsh -l
# Manual verification on asuka. Copies leaves into a path with a space and runs normal/abnormal cases.
set -u
base=$(mktemp -d)/"with space"
mkdir -p "$base"
cp -R /tmp/lbp-leaves/godot-mobile "$base/game"
cp -R /tmp/lbp-leaves/blender-assets "$base/art"
results=()
expect() { # name expected-code actual-code
    if [ "$2" = "$3" ]; then results+=("PASS $1 (exit $3)"); else results+=("FAIL $1 expected $2 got $3"); fi
}
G="$base/game"; A="$base/art"

# --- Godot normal
printf 'extends RefCounted\n\n\nstatic func add(a: int, b: int) -> int:\n\treturn a + b\n' > "$G/src/score.gd"
printf 'extends RefCounted\n\nconst Score = preload("res://src/score.gd")\n\n\nfunc test_add(t: TestContext) -> void:\n\tt.expect_eq(Score.add(1, 2), 3, "add")\n' > "$G/tests/test_score.gd"
sh "$G/scripts/check.sh" all; expect godot-normal 0 $?
# --- Godot abnormal (each restored after)
cp "$G/src/score.gd" /tmp/score.bak
printf 'extends RefCounted\n\n\nstatic func add(a: int, b: int) -> int:\n    return a + b\n' > "$G/src/score.gd"
sh "$G/scripts/check.sh" format; expect godot-format 1 $?
printf 'extends RefCounted\n\n\nstatic func Add(a: int, b: int) -> int:\n\treturn a + b\n' > "$G/src/score.gd"
sh "$G/scripts/check.sh" lint; expect godot-lint 1 $?
printf 'extends RefCounted\n\n\nstatic func add(a, b: int) -> int:\n\treturn a + b\n' > "$G/src/score.gd"
sh "$G/scripts/check.sh" typecheck; expect godot-untyped 1 $?
printf 'extends RefCounted\n\n\nstatic func add(a: int, b: int) -> int:\n\treturn "x"\n' > "$G/src/score.gd"
sh "$G/scripts/check.sh" typecheck; expect godot-type-error 1 $?
cp /tmp/score.bak "$G/src/score.gd"
printf 'extends RefCounted\n\nconst Score = preload("res://src/score.gd")\n\n\nfunc test_add(t: TestContext) -> void:\n\tt.expect_eq(Score.add(1, 2), 4, "add")\n' > "$G/tests/test_score.gd"
sh "$G/scripts/check.sh" test; expect godot-failing-test 1 $?
printf 'extends RefCounted\n\n\nfunc test_crash(t: TestContext) -> void:\n\tvar node: Node = null\n\tnode.queue_free()\n\tt.expect(true, "unreached")\n' > "$G/tests/test_score.gd"
sh "$G/scripts/check.sh" test; expect godot-runtime-error 1 $?
rm "$G/tests/test_score.gd"
sh "$G/scripts/check.sh" test; expect godot-zero-tests 1 $?

# --- Blender normal
printf 'import bpy\n\nMAX_TRIANGLES = 500\n\n\ndef build() -> None:\n    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.5))\n' > "$A/models/cube.py"
printf 'import unittest\n\nfrom models import cube\n\n\nclass CubeTests(unittest.TestCase):\n    def test_budget(self) -> None:\n        self.assertEqual(cube.MAX_TRIANGLES, 500)\n' > "$A/tests/test_cube.py"
sh "$A/scripts/check.sh" all; expect blender-normal 0 $?
# --- Blender abnormal
cp "$A/models/cube.py" /tmp/cube.bak
printf 'import bpy\n\nMAX_TRIANGLES = 500\n\ndef build() -> None:\n    bpy.ops.mesh.primitive_cube_add(size=1.0)\n' > "$A/models/cube.py"
sh "$A/scripts/check.sh" format; expect blender-format 1 $?
printf 'import bpy\nimport os\n\nMAX_TRIANGLES = 500\n\n\ndef build() -> None:\n    bpy.ops.mesh.primitive_cube_add(size=1.0)\n' > "$A/models/cube.py"
sh "$A/scripts/check.sh" lint; expect blender-lint 1 $?
printf 'import bpy\n\nMAX_TRIANGLES = 10\n\n\ndef build() -> None:\n    bpy.ops.mesh.primitive_uv_sphere_add()\n' > "$A/models/cube.py"
sh "$A/scripts/check.sh" build; expect blender-over-budget 1 $?
cp /tmp/cube.bak "$A/models/cube.py"
printf 'def build() -> None:\n    raise RuntimeError("boom")\n' > "$A/models/broken.py"
sh "$A/scripts/check.sh" build; expect blender-exception-plus-normal 1 $?
printf 'def build() -> None:\n    return None\n' > "$A/models/broken.py"
sh "$A/scripts/check.sh" build; expect blender-empty-scene 1 $?
rm "$A/models/broken.py"
mv "$A/tests/test_cube.py" /tmp/test_cube.bak
sh "$A/scripts/check.sh" test; expect blender-zero-tests 1 $?
mv /tmp/test_cube.bak "$A/tests/test_cube.py"

# --- wrong versions on PATH
fake=$(mktemp -d)
printf '#!/bin/sh\necho 4.6.0.stable.official\n' > "$fake/godot"
printf '#!/bin/sh\necho ruff 0.1.0\n' > "$fake/ruff"
chmod +x "$fake/godot" "$fake/ruff"
PATH="$fake:$PATH" sh "$G/scripts/check.sh" format; expect godot-wrong-version 1 $?
PATH="$fake:$PATH" sh "$A/scripts/check.sh" format; expect blender-wrong-ruff 1 $?

printf '%s\n' "${results[@]}"
rm -rf "$(dirname "$base")" "$fake" /tmp/score.bak /tmp/cube.bak
```

- [ ] **Step 2: asuka で実行**

```sh
ssh asuka@100.125.45.215 "rm -rf /tmp/lbp-leaves; mkdir -p /tmp/lbp-leaves"
rsync -a godot/mobile/ asuka@100.125.45.215:/tmp/lbp-leaves/godot-mobile/
rsync -a blender/assets/ asuka@100.125.45.215:/tmp/lbp-leaves/blender-assets/
scp .verification/manual/run-godot-blender.sh asuka@100.125.45.215:/tmp/lbp-leaves/run.sh
ssh asuka@100.125.45.215 "zsh -l /tmp/lbp-leaves/run.sh 2>&1 | tail -25; rm -rf /tmp/lbp-leaves" | tee .verification/manual/godot-blender-result.txt
```
Expected: 末尾の結果行がすべて `PASS`（19行）。

- [ ] **Step 3: FAIL があれば原因を調べて直す**

`superpowers:systematic-debugging` に従い、該当 leaf のファイルを修正→Task 1/2 の静的検査を再実行→Step 2 を再実行。修正は該当 leaf のコミットとして分ける（`fix: ...`）。

- [ ] **Step 4: progress.md に記録**

`progress.md` の末尾に追加（日付・確認環境・19ケースの結果を Step 2 の出力から転記）:
```markdown

## Godot / Blender — godot/mobile・blender/assets

- 2026-10-15、asuka（macOS 27.0.1、Apple Silicon）で手動確認。Godot 4.7.2、gdtoolkit 4.5.0、
  Blender 5.2.2 LTS、ruff 0.17.0、glTF-Transform 4.5.1。
- leaf を空白入りパスへコピーし、正常系2件・異常系17件を実行（結果は下の一覧）。
- 実ツール suite は設計どおり作っていない。静的検査は `test:native:static` に追加（Godot 7・Blender 7）。
- Android/iOS 書き出し・実機・Windows/Linux・Git フックの実 push は未実行。
- 結果:
  （Step 2 の PASS 行をそのまま列挙）
```

- [ ] **Step 5: Commit**

```bash
git add progress.md
git commit -m "docs: record Godot and Blender manual verification"
```

---

### Task 5: 統合と scaffold-profiles への登録（各段階で承認）

**Files:**
- scaffold-profiles: Modify `src/profile/skills/scaffold/references/basic-design.md`、再生成 `dist/**`

- [ ] **Step 1: ブランチ全体のレビュー**

`superpowers:requesting-code-review` で `main...feat/godot-blender-settings` をレビューし、指摘を反映。最後に `pnpm test:native:static` を再実行して結果を示す。

- [ ] **Step 2: main 統合と push の承認を取る**（AskUserQuestion: 対象ブランチ・コミット一覧・push 先 `origin/main`）

- [ ] **Step 3: 承認後に統合・push**（main worktree で実行）

```bash
cd /Users/papillon/Documents/Github/lang-boilerplates
git fetch origin main && git merge --ff-only origin/main
git merge --no-ff feat/godot-blender-settings -m "merge: add Godot and Blender settings"
git push origin main
```

- [ ] **Step 4: scaffold-profiles の worktree を作り、表と注意書きを追加**

`superpowers:using-git-worktrees` で `~/Code/scaffold-profiles` に `feat/godot-blender-languages` を作る。
`src/profile/skills/scaffold/references/basic-design.md` の言語表の Roblox 行の後に追加:
```markdown
| Godot（GDScript） | [godot/README.md](https://github.com/KendrickMalar/lang-boilerplates/blob/main/godot/README.md) |
| Blender Python（3D モデル） | [blender/README.md](https://github.com/KendrickMalar/lang-boilerplates/blob/main/blender/README.md) |
```
Roblox の注意書き（`- Roblox（Luau）は、Rojo で…` の行）の後に追加:
```markdown
- Godot（GDScript）のモバイルゲームは `godot/mobile` を使う。3D モデルをコードで作る場合は `blender/assets` を組で使い、製品リポジトリの別ディレクトリ（例: `game/` と `art/`）に置く。Godot・Blender・gdtoolkit・ruff・glTF-Transform の導入は global tool の変更を含む。対象と影響を示してこの工程で承認を得て、設計書と Epic（管理ブロックの外への追記）に記録する。実装工程では人に質問できない。
```

- [ ] **Step 5: 再生成と検査**

```bash
npm ci
node bin/generate.ts
node bin/generate.ts --check
npm run typecheck
npm test
```
Expected: `--check` が一致、typecheck と test が成功。test が言語表の行を固定している場合は、その期待値に2行を足す（`grep -rn "roblox/README.md" test/` で探す）。

- [ ] **Step 6: コミット、統合と push の承認を取り、実行**

```bash
git add src dist test
git commit -m "feat: register Godot and Blender language settings"
```
AskUserQuestion で承認後、scaffold-profiles の main worktree で `git merge --no-ff` → `git push origin main`。

- [ ] **Step 7: asuka の pull の承認を取り、実行**

```bash
ssh asuka@100.125.45.215 "zsh -lc 'cd ~/Documents/Github/lang-boilerplates && git pull --ff-only && git log --oneline -1; cd ~/Code/scaffold-profiles && git pull --ff-only && git log --oneline -1'"
```
Expected: 両方が push したコミットに進む。asuka の claude-scaffold が dist をどう読むか（`link-profiles` の再実行が要るか）を `~/Documents/Github/claude-scaffold` の README で確認し、要るなら同じ承認範囲で実行。
