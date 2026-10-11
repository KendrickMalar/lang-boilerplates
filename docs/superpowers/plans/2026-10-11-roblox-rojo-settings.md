# Roblox Rojo 設定集 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `roblox/rojo/` に、Rojo でファイル管理する Roblox ゲーム用の自己完結した設定 leaf を追加し、macOS で実ツール検証する。

**Architecture:** 設定ファイル＋空ディレクトリ＋`scripts/check.sh`（format→lint→typecheck→test→build）＋Lune 用最小テスト実行器＋任意 Git フック。保守検証は既存 Python native suite に `test_static_roblox` / `test_roblox` / `RobloxHookTests` を追加。

**Tech Stack:** Rokit 1.2.0、Rojo 7.7.1、Wally 0.3.2、Selene 0.32.0、StyLua 2.5.2、luau-lsp 1.69.0、Lune 0.10.5、POSIX sh、Python 3.11 unittest。

**Spec:** `docs/superpowers/specs/2026-10-11-roblox-rojo-settings-design.md`

## Global Constraints

- leaf は `roblox/rojo/`。親・兄弟設定に依存しない。製品 source・fixture・cache・`roblox.yml`・`wally.lock` は配布しない。
- 版: rojo 7.7.1 / wally 0.3.2 / selene 0.32.0 / stylua 2.5.2 / luau-lsp 1.69.0 / lune 0.10.5（rokit.toml の key は実行ファイル名）。
- 型定義 URL `https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/1.69.0/scripts/globalTypes.d.luau`、SHA256 `7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2`、保存先 `.luau-lsp-cache/globalTypes-1.69.0.d.luau`。
- check.sh は自動導入・global 設定変更をしない。段階名は `format|lint|typecheck|test|build|all`。出力に `stage: <名前>` を出す。
- Selene は `roblox-std-source = "pinned"`。`roblox.yml` は利用者が生成・製品 Git 管理。
- `pnpm test` の定義は変更しない。native suite は明示実行のみ。
- 検証キャッシュ・ログは `.verification/native/roblox/`（Git 管理外）。
- コミットに AI 帰属トレーラーを付けない。

## Review Focus

1. 利用者の PATH に rokit 以外（Homebrew の古い stylua 等）が先にある → 版不一致として非0で止まり、`rokit install` と PATH を案内する。Task 2 の版違いテストで固定。
2. 型定義キャッシュが途中まで書かれて壊れた → SHA 照合で非0、削除して再取得を案内。一時ファイル経由で書き込み、Task 2 の SHA 不一致テストで固定。
3. `wally install` 前（依存なし）で `rojo build` → `Packages` は optional path なので成功する。Task 2 正常系（Packages 無し）で固定。
4. spec が table 以外を返す・require に失敗 → 失敗として数え非0。Task 2 で「table を返さない spec」テストを追加。
5. check.sh をリポジトリ外の cwd から実行 → スクリプト位置から root に移動して動く。Task 2 の全実行を fixture 外 cwd から呼んで固定。

---

### Task 0: ツール導入（承認ゲート）と CLI 事実の確認

**承認が必要。** 実行前にユーザーへ次を提示し、明示の承認を得る: Rokit 1.2.0 を公式 install.sh で `~/.rokit` へ導入（シェル設定に PATH 追記の可能性）、`rokit install` で6ツールを `~/.rokit/tool-storage` へ取得、型定義と Selene Roblox 定義のネットワーク取得。

**Files:**
- Create（Git 管理外）: `.verification/native/roblox/seed/rokit.toml`、`seed/roblox.yml`、`seed/globalTypes-1.69.0.d.luau`、`seed/facts.md`

- [ ] **Step 1: 承認取得後、Rokit 導入**

```sh
curl -sSf https://raw.githubusercontent.com/rojo-rbx/rokit/main/scripts/install.sh | bash
~/.rokit/bin/rokit --version   # 期待: rokit 1.2.0
```

- [ ] **Step 2: seed に rokit.toml を書き、ツール導入**

```toml
[tools]
rojo = "rojo-rbx/rojo@7.7.1"
wally = "UpliftGames/wally@0.3.2"
selene = "Kampfkarren/selene@0.32.0"
stylua = "JohnnyMorganz/StyLua@2.5.2"
luau-lsp = "JohnnyMorganz/luau-lsp@1.69.0"
lune = "lune-org/lune@0.10.5"
```

Run: `cd .verification/native/roblox/seed && ~/.rokit/bin/rokit install`
（初回は tool の trust 確認が対話で出る。`--no-trust-check` は使わない。`!` 経由は stdin が使えないため、ユーザー自身の端末での実行を依頼する）

- [ ] **Step 3: 事実確認を facts.md に記録**

以下の各コマンド出力を `seed/facts.md` に貼る。計画の前提と違えば、該当 Task のコードを直してから進める。

```sh
ls -R ~/.rokit/tool-storage | head -40          # 前提: <owner>/<repo>/<version>/<binary>
for t in rojo wally selene stylua luau-lsp lune; do ~/.rokit/bin/$t --version; done
~/.rokit/bin/luau-lsp analyze --help | grep -E 'definitions|sourcemap|platform|ignore'
                                                # 前提: --definitions=@roblox=<path> を受け付ける
printf 'local x=1\n' > /tmp/x.luau && ~/.rokit/bin/stylua --check /tmp/x.luau; echo $?
                                                # 前提: "Diff in" を含み非0
printf 'local unused = 1\n' > /tmp/y.luau && ~/.rokit/bin/selene /tmp/y.luau; echo $?
                                                # 前提: 警告のみでも非0
```

- [ ] **Step 4: seed の定義ファイルを用意**

```sh
cd .verification/native/roblox/seed
printf 'std = "roblox"\nroblox-std-source = "pinned"\n' > selene.toml
~/.rokit/bin/selene generate-roblox-std        # roblox.yml を生成
curl -fsSL -o globalTypes-1.69.0.d.luau https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/1.69.0/scripts/globalTypes.d.luau
shasum -a 256 globalTypes-1.69.0.d.luau        # 期待: 7db9cd4f…aaf2
```

コミットなし（Git 管理外のみ）。

---

### Task 1: leaf の設定ファイルと静的検査

**Files:**
- Create: `roblox/README.md`、`roblox/rojo/{README.md,LICENSE,.editorconfig,.gitignore,rokit.toml,default.project.json,wally.toml,stylua.toml,selene.toml,.luaurc}`、`roblox/rojo/src/{server,client,shared}/.gitkeep`、`roblox/rojo/tests/.gitkeep`
- Create: `tests/native/test_static_roblox.py`
- Modify: `tests/native/test_catalog.py`（ROBLOX_FILES、ナビゲーション、inventory、package.json 検査）、`package.json`（`test:native:static` に `tests.native.test_static_roblox`）、`README.md`（言語表と範囲）
- Note: `scripts/check.sh`、`scripts/test.luau`、`.githooks/*` は Task 2・3 で作るが、ROBLOX_FILES にはこの Task で含める（catalog テストは Task 3 完了まで RED のまま。Task 1 の GREEN 判定は `test_static_roblox` のみ）。

**Interfaces:**
- Produces: `ROBLOX_FILES`（test_catalog.py）、leaf 設定一式、`tests.native.test_static_roblox.StaticRobloxTests`

- [ ] **Step 1: 失敗する静的テストを書く**

`tests/native/test_static_roblox.py`:

```python
"""Catch missing/non-self-contained Rojo settings and weakened quality rules."""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "roblox/rojo"
PINS = {"rojo": "rojo-rbx/rojo@7.7.1", "wally": "UpliftGames/wally@0.3.2",
        "selene": "Kampfkarren/selene@0.32.0", "stylua": "JohnnyMorganz/StyLua@2.5.2",
        "luau-lsp": "JohnnyMorganz/luau-lsp@1.69.0", "lune": "lune-org/lune@0.10.5"}
DEFS_SHA = "7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2"


class StaticRobloxTests(unittest.TestCase):
    def test_tool_pins_are_exact(self):
        tools = tomllib.loads((LEAF / "rokit.toml").read_text())["tools"]
        self.assertEqual(tools, PINS)

    def test_quality_settings(self):
        selene = tomllib.loads((LEAF / "selene.toml").read_text())
        self.assertEqual(selene, {"std": "roblox", "roblox-std-source": "pinned"})
        stylua = tomllib.loads((LEAF / "stylua.toml").read_text())
        self.assertEqual(stylua["syntax"], "Luau")
        self.assertEqual(stylua["column_width"], 120)
        self.assertEqual(stylua["indent_type"], "Tabs")
        self.assertEqual(stylua["quote_style"], "AutoPreferDouble")
        self.assertEqual(stylua["call_parentheses"], "Always")
        self.assertEqual(json.loads((LEAF / ".luaurc").read_text()), {"languageMode": "strict"})

    def test_rojo_tree_mapping(self):
        tree = json.loads((LEAF / "default.project.json").read_text())["tree"]
        self.assertEqual(tree["$className"], "DataModel")
        self.assertEqual(tree["ServerScriptService"]["Server"]["$path"], "src/server")
        self.assertEqual(tree["StarterPlayer"]["StarterPlayerScripts"]["Client"]["$path"], "src/client")
        shared = tree["ReplicatedStorage"]
        self.assertEqual(shared["Shared"]["$path"], "src/shared")
        self.assertEqual(shared["Packages"]["$path"], {"optional": "Packages"})

    def test_wally_manifest_has_no_dependencies(self):
        wally = tomllib.loads((LEAF / "wally.toml").read_text())
        self.assertEqual(wally["package"]["realm"], "shared")
        self.assertEqual(wally["package"]["registry"], "https://github.com/UpliftGames/wally-index")
        self.assertEqual(wally.get("dependencies", {}), {})

    def test_gitignore_and_no_product_source(self):
        ignored = (LEAF / ".gitignore").read_text().splitlines()
        for entry in ["/Packages/", "/sourcemap.json", "*.rbxl", "*.rbxlx", "/.luau-lsp-cache/"]:
            self.assertIn(entry, ignored)
        self.assertNotIn("wally.lock", ignored)
        self.assertNotIn("roblox.yml", ignored)
        luau = sorted(p.relative_to(LEAF).as_posix() for p in LEAF.rglob("*.luau"))
        self.assertEqual(luau, ["scripts/test.luau"], "only the test runner is distributed")
        for name in ["roblox.yml", "wally.lock", "sourcemap.json"]:
            self.assertFalse((LEAF / name).exists(), name)
        for empty in ["src/server", "src/client", "src/shared", "tests"]:
            self.assertEqual([p.name for p in (LEAF / empty).iterdir()], [".gitkeep"])

    def test_check_script_pins_type_definitions(self):
        text = (LEAF / "scripts/check.sh").read_text()
        self.assertIn("luau-lsp/1.69.0/scripts/globalTypes.d.luau", text)
        self.assertIn(DEFS_SHA, text)
        self.assertIn(".luau-lsp-cache/globalTypes-1.69.0.d.luau", text)
        for command in ["rokit install", "wally install", "selene generate-roblox-std"]:
            for line in text.splitlines():
                if command in line:
                    self.assertIn("fail ", line, f"{command} may only appear in guidance: {line}")

    def test_readme_links_resolve(self):
        text = (LEAF / "README.md").read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in link and not link.startswith("#"):
                self.assertTrue((LEAF / link).exists(), link)
        for phrase in ["selene generate-roblox-std", "wally install", "rokit install",
                       'require("./', "未検証"]:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
```

（`test_check_script_pins_type_definitions` は Task 2 まで RED で可。）

- [ ] **Step 2: RED 確認**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_roblox`
Expected: FAIL（`FileNotFoundError: .../roblox/rojo/rokit.toml` など）

- [ ] **Step 3: 設定ファイルを書く**

`roblox/rojo/rokit.toml`:
```toml
# Tool versions for this project. Install with `rokit install`.
[tools]
rojo = "rojo-rbx/rojo@7.7.1"
wally = "UpliftGames/wally@0.3.2"
selene = "Kampfkarren/selene@0.32.0"
stylua = "JohnnyMorganz/StyLua@2.5.2"
luau-lsp = "JohnnyMorganz/luau-lsp@1.69.0"
lune = "lune-org/lune@0.10.5"
```

`roblox/rojo/default.project.json`:
```json
{
	"name": "project",
	"tree": {
		"$className": "DataModel",
		"ReplicatedStorage": {
			"Shared": { "$path": "src/shared" },
			"Packages": { "$path": { "optional": "Packages" } }
		},
		"ServerScriptService": {
			"Server": { "$path": "src/server" }
		},
		"StarterPlayer": {
			"StarterPlayerScripts": {
				"Client": { "$path": "src/client" }
			}
		}
	}
}
```

`roblox/rojo/wally.toml`:
```toml
[package]
name = "your-name/project"
version = "0.1.0"
registry = "https://github.com/UpliftGames/wally-index"
realm = "shared"

[dependencies]
```

`roblox/rojo/stylua.toml`:
```toml
syntax = "Luau"
column_width = 120
line_endings = "Unix"
indent_type = "Tabs"
indent_width = 4
quote_style = "AutoPreferDouble"
call_parentheses = "Always"
```

`roblox/rojo/selene.toml`:
```toml
std = "roblox"
roblox-std-source = "pinned"
```

`roblox/rojo/.luaurc`:
```json
{ "languageMode": "strict" }
```

`roblox/rojo/.gitignore`:
```
/Packages/
/sourcemap.json
*.rbxl
*.rbxlx
/.luau-lsp-cache/
/.verification/
.DS_Store
# wally.lock and roblox.yml belong in the consuming project repository.
```

`roblox/rojo/.editorconfig`:
```
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4
trim_trailing_whitespace = true

[*.{luau,lua,json}]
indent_style = tab

[*.md]
trim_trailing_whitespace = false
```

`roblox/rojo/LICENSE`: `rust/tauri/LICENSE` と同一内容をコピー。
`src/server/.gitkeep`、`src/client/.gitkeep`、`src/shared/.gitkeep`、`tests/.gitkeep`: 空ファイル。

- [ ] **Step 4: README を書く**

`roblox/rojo/README.md`（構成。文体は既存 leaf に合わせ、です・ます調）:

```markdown
# Rojo プロジェクト — Roblox（Luau）品質設定

Rojo でファイル管理する Roblox ゲーム用の自己完結した設定です。Rojo **7.7.1**、
StyLua **2.5.2**、Selene **0.32.0**、luau-lsp **1.69.0**、Lune **0.10.5**、Wally **0.3.2** を
Rokit で固定します。製品 source、`roblox.yml`、`wally.lock`、fixture/cache は配布しません。

## 導入（既存ファイルを保護）

| コピー元 | コピー先 |
| --- | --- |
| [rokit.toml](rokit.toml) | `rokit.toml` |
| [default.project.json](default.project.json) | `default.project.json` |
| [wally.toml](wally.toml) | `wally.toml`（name を製品に合わせる） |
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

コピー前に既存ファイル・Git hooksPath/フックを読み取り、差分を提示して承認を得てください。

## tool と定義ファイル

1. Rokit を利用側で導入し、プロジェクト root で `rokit install` を実行します（このチェックは自動導入しません）。
2. `selene generate-roblox-std` で `roblox.yml` を生成し、製品 Git に保存します。
3. 依存を追加したら `wally install` を実行し、`wally.lock` を製品 Git に保存します。
4. 型定義は初回の typecheck で luau-lsp 1.69.0 タグから取得し、SHA256 を照合します。

## チェック

    sh scripts/check.sh all
    sh scripts/check.sh format # format|lint|typecheck|test|build|all

順序と失敗条件（spec §4.1 の表をそのまま記載）。

## テスト

`tests/**/*.spec.luau` は `{ [テスト名]: () -> () }` を返します。Lune で実行するため、
対象は `require("./x")` 形式の純粋ロジックに限ります。`script.Parent` や Roblox API に依存する
コードは Lune では動きません。

## Git フック（任意）

（rust/tauri/README.md の該当節と同じ手順・文言。次の3コマンドと「既存フック」「別承認」を必ず含める）
    git config --show-origin --get-all core.hooksPath
    git rev-parse --git-path hooks
    git config --local core.hooksPath .githooks

## 検証範囲

macOS で実ツールを使って検証済み。Studio への実同期、Windows/Linux、Wally レジストリからの
実取得は未検証です。
```

`roblox/README.md`:
```markdown
# Roblox（Luau）設定

- [Rojo プロジェクトの品質設定](rojo/README.md): Rokit で版固定した Rojo/StyLua/Selene/luau-lsp/Lune/Wally。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。macOS 実検証のみです。
保守 suite は repository root の `pnpm test:native:static` と `pnpm test:native:roblox` から明示実行します。
```

ルート `README.md`: 言語表に `| Roblox (Luau) | [roblox/README.md](./roblox/README.md) |`、Native 保守検証の例に `pnpm test:native:roblox`、「範囲」に `- Roblox: Rojo プロジェクト用（Rojo7.7.1/Rokit 固定、macOS 実検証）。` を追加。

- [ ] **Step 5: catalog と package.json を更新**

`tests/native/test_catalog.py`:
```python
ROBLOX_FILES = {'README.md', 'LICENSE', '.editorconfig', '.gitignore', 'rokit.toml',
                'default.project.json', 'wally.toml', 'stylua.toml', 'selene.toml', '.luaurc',
                'src/server/.gitkeep', 'src/client/.gitkeep', 'src/shared/.gitkeep',
                'tests/.gitkeep', 'scripts/check.sh', 'scripts/test.luau',
                '.githooks/pre-commit', '.githooks/pre-push'}
```
- `test_root_language_leaf_navigation` のリストに `('roblox', ['rojo'])`
- `test_independent_copy_exact_inventory_and_local_references` のリストに `('roblox/rojo', ROBLOX_FILES)`
- `test_explicit_nonempty_suites_preserve_typescript_entry` のリストに `('roblox', 'test_roblox')`、さらに `self.assertIn('test_static_roblox', scripts['test:native:static'])`

`package.json` scripts:
```json
"test:native:static": "python3 -m tests.native.test_catalog tests.native.test_catalog tests.native.test_static_rust tests.native.test_static_swift tests.native.test_static_roblox tests.native.test_hooks.HookContractTests",
"test:native:roblox": "python3 -m tests.native.test_catalog tests.native.test_roblox tests.native.test_hooks.RobloxHookTests"
```

- [ ] **Step 6: GREEN 確認（check.sh 依存テスト以外）**

Run: `python3 -m tests.native.test_catalog tests.native.test_static_roblox`
Expected: `test_check_script_pins_type_definitions` と `test_gitignore_and_no_product_source`（test.luau 未作成）のみ FAIL、他 PASS。

- [ ] **Step 7: Commit**

```sh
git add roblox README.md package.json tests/native/test_static_roblox.py tests/native/test_catalog.py
git commit -m "feat: add Roblox Rojo leaf settings"
```

---

### Task 2: check.sh・テスト実行器・実ツール検証

**Files:**
- Create: `roblox/rojo/scripts/check.sh`、`roblox/rojo/scripts/test.luau`
- Create: `tests/native/roblox_helpers.py`、`tests/native/test_roblox.py`

**Interfaces:**
- Consumes: Task 0 の seed（`.verification/native/roblox/seed/`）、Task 1 の leaf
- Produces: `roblox_helpers.copy_fixture(name: str) -> Path`、`roblox_helpers.roblox_env(root: Path) -> dict[str, str]`、`roblox_helpers.run_check(root: Path, stage: str, env: dict | None = None) -> subprocess.CompletedProcess[str]`、定数 `GREETING_SOURCE: str`、`GREETING_SPEC: str`

- [ ] **Step 1: helper を書く**

`tests/native/roblox_helpers.py`:
```python
"""Git-ignored Rojo fixtures using already-installed Rokit tools; never installs anything."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEAF = ROOT / "roblox/rojo"
CACHE = ROOT / ".verification/native/roblox"
SEED = CACHE / "seed"
GREETING_SOURCE = """--!strict
local Greeting = {}

function Greeting.format(name: string): string
\treturn `Hello, {name}!`
end

return Greeting
"""
GREETING_SPEC = """--!strict
local Greeting = require("../src/shared/Greeting")

return {
\t["formats a name"] = function()
\t\tassert(Greeting.format("Roblox") == "Hello, Roblox!", "unexpected greeting")
\tend,
}
"""


def tool_bin_dir() -> Path:
    """Link pinned binaries from Rokit storage so a synthetic HOME cannot break shims."""
    pins = tomllib.loads((LEAF / "rokit.toml").read_text())["tools"]
    storage = Path.home() / ".rokit/tool-storage"
    bin_dir = CACHE / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, spec in pins.items():
        repo, version = spec.split("@")
        owner, project = repo.split("/")
        real = storage / owner / project / version / name
        if not real.is_file():
            raise RuntimeError(f"{real} missing; run approved `rokit install` first (Task 0)")
        link = bin_dir / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(real)
    return bin_dir


def roblox_env(root: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ROKIT")}
    home = root / "home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), PATH=os.pathsep.join([str(tool_bin_dir()), "/usr/bin", "/bin"]))
    return env


def copy_fixture(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=CACHE)) / "project"
    shutil.copytree(LEAF, root)
    (root / "src/shared/Greeting.luau").write_text(GREETING_SOURCE)
    (root / "tests/Greeting.spec.luau").write_text(GREETING_SPEC)
    shutil.copy2(SEED / "roblox.yml", root / "roblox.yml")
    (root / ".luau-lsp-cache").mkdir()
    shutil.copy2(SEED / "globalTypes-1.69.0.d.luau", root / ".luau-lsp-cache/globalTypes-1.69.0.d.luau")
    return root


def run_check(root: Path, stage: str, env: dict[str, str] | None = None):
    env = env if env is not None else roblox_env(root)
    # Run from outside the fixture: check.sh must locate its own root.
    result = subprocess.run(["sh", str(root / "scripts/check.sh"), stage], cwd=CACHE, env=env,
                            text=True, capture_output=True, check=False)
    logs = CACHE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stem = f"{root.parent.name}-{stage}-{time.time_ns()}"
    (logs / f"{stem}.log").write_text(f"exit={result.returncode}\n{result.stdout}\n{result.stderr}")
    (logs / f"{stem}.json").write_text(json.dumps({"fixture": str(root), "stage": stage,
                                                   "exit": result.returncode}, indent=2))
    return result
```

- [ ] **Step 2: 失敗する実行テストを書く**

`tests/native/test_roblox.py`:
```python
"""Real Rokit-pinned tools against isolated fixtures: normal passes, each defect fails."""
import re
import shutil
import unittest

from tests.native.roblox_helpers import copy_fixture, roblox_env, run_check


class RobloxCheckTests(unittest.TestCase):
    def assert_fails(self, result, *needles):
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        for needle in needles:
            self.assertIn(needle, output)

    def test_normal_all_passes_without_packages(self):
        root = copy_fixture("normal")
        result = run_check(root, "all")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        for stage in ["format", "lint", "typecheck", "test", "build"]:
            self.assertIn(f"stage: {stage}", output)
        self.assertIn("1 passed, 0 failed", output)
        self.assertFalse((root / "Packages").exists())
        self.assertEqual(list(root.rglob("*.rbxl")), [], "build output must be temporary")

    def test_bad_format(self):
        root = copy_fixture("format")
        (root / "src/shared/Greeting.luau").write_text("local Greeting={}\nreturn Greeting\n")
        self.assert_fails(run_check(root, "format"), "Diff in")

    def test_lint_warning(self):
        root = copy_fixture("lint")
        (root / "src/shared/Unused.luau").write_text("local unused = 1\n\nreturn {}\n")
        self.assert_fails(run_check(root, "lint"), "unused_variable")

    def test_strict_type_error(self):
        root = copy_fixture("types")
        (root / "src/shared/Bad.luau").write_text('--!strict\nlocal n: number = "x"\n\nreturn n\n')
        self.assert_fails(run_check(root, "typecheck"), "Bad.luau")

    def test_failing_spec(self):
        root = copy_fixture("failing")
        spec = root / "tests/Greeting.spec.luau"
        spec.write_text(spec.read_text().replace('"Hello, Roblox!"', '"Bye"'))
        self.assert_fails(run_check(root, "test"), "FAIL", "0 passed, 1 failed")

    def test_spec_not_returning_table(self):
        root = copy_fixture("notable")
        (root / "tests/Broken.spec.luau").write_text("return 1\n")
        self.assert_fails(run_check(root, "test"), "Broken.spec.luau")

    def test_zero_specs(self):
        root = copy_fixture("zero")
        (root / "tests/Greeting.spec.luau").unlink()
        self.assert_fails(run_check(root, "test"), "no tests discovered")

    def test_missing_rojo_path(self):
        root = copy_fixture("path")
        project = root / "default.project.json"
        project.write_text(project.read_text().replace('"src/server"', '"src/missing"'))
        self.assert_fails(run_check(root, "build"))

    def test_missing_tool(self):
        root = copy_fixture("notool")
        env = roblox_env(root)
        env["PATH"] = "/usr/bin:/bin"
        self.assert_fails(run_check(root, "format", env), "rokit install")

    def test_wrong_tool_version(self):
        root = copy_fixture("version")
        pins = root / "rokit.toml"
        pins.write_text(pins.read_text().replace("StyLua@2.5.2", "StyLua@2.5.1"))
        self.assert_fails(run_check(root, "format"), "stylua must be 2.5.1")

    def test_definition_sha_mismatch(self):
        root = copy_fixture("sha")
        (root / ".luau-lsp-cache/globalTypes-1.69.0.d.luau").write_text("-- tampered\n")
        self.assert_fails(run_check(root, "typecheck"), "SHA256 mismatch")

    def test_dependencies_without_packages(self):
        root = copy_fixture("packages")
        wally = root / "wally.toml"
        wally.write_text(wally.read_text() + 'Promise = "evaera/promise@4.0.0"\n')
        self.assert_fails(run_check(root, "format"), "wally install")

    def test_missing_roblox_std(self):
        root = copy_fixture("std")
        (root / "roblox.yml").unlink()
        self.assert_fails(run_check(root, "lint"), "selene generate-roblox-std")

    def test_empty_source(self):
        root = copy_fixture("empty")
        (root / "src/shared/Greeting.luau").unlink()
        self.assert_fails(run_check(root, "format"), "no Luau source")

    def test_unknown_stage(self):
        root = copy_fixture("stage")
        self.assert_fails(run_check(root, "fmt"), "unknown stage")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: RED 確認**

Run: `PYTHONPATH=. python3 -m tests.native.test_catalog tests.native.test_roblox`
Expected: 全件 FAIL（`scripts/check.sh: No such file`）。

- [ ] **Step 4: check.sh を書く**

`roblox/rojo/scripts/check.sh`（実行権限 755）:
```sh
#!/bin/sh
# Rojo project checks. Never installs tools/packages or mutates global configuration.
set -eu
fail() { printf '%s\n' "error: $*" >&2; exit 1; }
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
stage=${1:-all}
[ "$#" -le 1 ] || fail 'usage: check.sh [format|lint|typecheck|test|build|all]'
case "$stage" in format|lint|typecheck|test|build|all) ;; *) fail "unknown stage: $stage" ;; esac
DEFS_URL='https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/1.69.0/scripts/globalTypes.d.luau'
DEFS_SHA256='7db9cd4fe55a4d26f3f7d5a39b6279a376f95a6c055c71d5591c26a1d525aaf2'
DEFS=.luau-lsp-cache/globalTypes-1.69.0.d.luau

[ -s rokit.toml ] || fail 'missing rokit.toml'
pins=$(awk -F'"' '/^[a-z-]+ = "[^"]+@[^"]+"$/ { split($1, k, " "); n = split($2, v, "@"); print k[1], v[n] }' rokit.toml)
[ -n "$pins" ] || fail 'rokit.toml pins no tools'
while read -r tool version; do
    command -v "$tool" >/dev/null 2>&1 || fail "$tool is missing; run rokit install and put ~/.rokit/bin first on PATH"
    actual=$("$tool" --version 2>&1) || fail "cannot read $tool version"
    printf '%s\n' "tool: $(command -v "$tool") $actual"
    case " $actual " in
        *[!0-9.]"$version"[!0-9.]*) ;;
        *) fail "$tool must be $version (found: $actual); run rokit install and check PATH order" ;;
    esac
done <<EOF
$pins
EOF

find src -type f -name '*.luau' | grep -q . || fail 'no Luau source under src/'
[ -s roblox.yml ] || fail 'missing roblox.yml; run selene generate-roblox-std and commit it'
if awk '/^\[/ { s = ($0 ~ /^\[(server-|dev-)?dependencies\]$/) } s && /^[A-Za-z0-9_-]+ *=/ { f = 1 } END { exit !f }' wally.toml \
    && [ ! -d Packages ]; then
    fail 'wally.toml declares dependencies but Packages/ is missing; run wally install'
fi

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{ print $1 }'
}
ensure_defs() {
    if [ ! -f "$DEFS" ]; then
        command -v curl >/dev/null 2>&1 || fail 'curl is required to fetch Roblox type definitions'
        mkdir -p .luau-lsp-cache
        tmp="$DEFS.tmp.$$"
        curl -fsSL -o "$tmp" "$DEFS_URL" || { rm -f "$tmp"; fail "cannot download $DEFS_URL"; }
        [ "$(sha256 "$tmp")" = "$DEFS_SHA256" ] || { rm -f "$tmp"; fail 'downloaded type definitions SHA256 mismatch'; }
        mv "$tmp" "$DEFS"
    fi
    [ "$(sha256 "$DEFS")" = "$DEFS_SHA256" ] || fail "type definitions SHA256 mismatch: $DEFS (delete it to refetch)"
}

run_stage() {
    printf '%s\n' "stage: $1"
    case "$1" in
        format) stylua --check src tests scripts ;;
        lint) selene src tests scripts ;;
        typecheck)
            ensure_defs
            rojo sourcemap default.project.json --output sourcemap.json
            luau-lsp analyze --platform=roblox --sourcemap=sourcemap.json \
                --definitions=@roblox="$DEFS" --ignore='Packages/**' src tests
            ;;
        test) lune run scripts/test.luau ;;
        build)
            out=$(mktemp -d)
            if ! rojo build default.project.json --output "$out/place.rbxl"; then rm -rf "$out"; exit 1; fi
            [ -s "$out/place.rbxl" ] || { rm -rf "$out"; fail 'rojo build produced no place file'; }
            rm -rf "$out"
            ;;
    esac
}
if [ "$stage" = all ]; then
    for step in format lint typecheck test build; do run_stage "$step"; done
else
    run_stage "$stage"
fi
```

（Task 0 facts.md で `--definitions` の書式が違えばここを合わせる。）

- [ ] **Step 5: test.luau を書く**

`roblox/rojo/scripts/test.luau`:
```lua
-- Minimal Lune runner: every tests/**/*.spec.luau returns { [name]: () -> () }.
local fs = require("@lune/fs")
local process = require("@lune/process")

local SUFFIX = ".spec.luau"

local function collect(dir: string, out: { string })
	if not fs.isDir(dir) then
		return
	end
	local names = fs.readDir(dir)
	table.sort(names)
	for _, name in names do
		local path = dir .. "/" .. name
		if fs.isDir(path) then
			collect(path, out)
		elseif string.sub(name, -#SUFFIX) == SUFFIX then
			table.insert(out, path)
		end
	end
end

local files = {}
collect("tests", files)
local passed, failed = 0, 0
for _, file in files do
	-- Paths resolve relative to this script; the extension is omitted.
	local modulePath = "../" .. string.sub(file, 1, -#".luau" - 1)
	local loaded, suite = pcall(function()
		return require(modulePath)
	end)
	if not loaded or type(suite) ~= "table" then
		failed += 1
		print(`FAIL {file}: spec must return a table of test functions ({suite})`)
		continue
	end
	local names = {}
	for name in suite do
		table.insert(names, name)
	end
	table.sort(names)
	for _, name in names do
		local ok, err = pcall(suite[name])
		if ok then
			passed += 1
			print(`PASS {file} :: {name}`)
		else
			failed += 1
			print(`FAIL {file} :: {name}: {err}`)
		end
	end
end
print(`{passed} passed, {failed} failed`)
if passed + failed == 0 then
	print("error: no tests discovered")
	process.exit(1)
end
if failed > 0 then
	process.exit(1)
end
```

（Lune が動的パスの require を拒否する場合は facts.md に記録し、`@lune/luau` の `load` + `fs.readFile` 方式へ切り替えて相対 require の解決をテストで確認する。）

- [ ] **Step 6: 整形と GREEN 確認**

```sh
.verification/native/roblox/bin/stylua roblox/rojo/scripts/test.luau
PYTHONPATH=. python3 -m tests.native.test_catalog tests.native.test_roblox tests.native.test_static_roblox
```
Expected: test_roblox 全 PASS（15 tests）、test_static_roblox 全 PASS。

- [ ] **Step 7: Commit**

```sh
git add roblox/rojo/scripts tests/native/roblox_helpers.py tests/native/test_roblox.py
git commit -m "feat: add Roblox check script and Lune test runner"
```

---

### Task 3: Git フックと実 commit/push 検証

**Files:**
- Create: `roblox/rojo/.githooks/pre-commit`、`roblox/rojo/.githooks/pre-push`（755）
- Modify: `tests/native/test_hooks.py`

**Interfaces:**
- Consumes: `roblox_helpers.copy_fixture`、`roblox_env`、`GREETING_SPEC`

- [ ] **Step 1: 失敗するフックテストを書く**

`tests/native/test_hooks.py`:
- `HookContractTests` の2つのループ対象に `'roblox/rojo'` を追加。
- `exercise_git_gates` の platform 分岐を3分岐へ:
```python
        if platform == 'rust':
            test.assertIn('1 passed', output)
        elif platform == 'roblox':
            test.assertIn('1 passed, 0 failed', output)
        else:
            test.assertRegex(output, r'"passedTests"\s*:\s*1')
```
```python
        test.assertIn({'rust': 'Diff in', 'roblox': 'Diff in'}.get(platform, '[Spacing]'), output)
```
```python
        test.assertIn({'rust': 'test result: FAILED', 'roblox': 'FAIL tests/Greeting.spec.luau'}
                      .get(platform, 'FixtureTests.testAddition()'), output)
```
- 追加クラス:
```python
class RobloxHookTests(unittest.TestCase):
    platform = 'roblox'

    def test_real_commit_push_gates_and_global_preservation(self):
        self.assertTrue((ROOT / 'roblox/rojo/.githooks/pre-commit').is_file(), 'manual hook missing')
        exercise_git_gates(self, self.platform, self.fixture_inputs())

    def fixture_inputs(self):
        from tests.native.roblox_helpers import GREETING_SPEC, copy_fixture, roblox_env
        root = copy_fixture('hooks')
        copy_check_script('roblox/rojo', root)
        source = root / 'src/shared/Greeting.luau'
        tests = root / 'tests/Greeting.spec.luau'
        return (root, roblox_env(root), source, tests, 'local Greeting={}\nreturn Greeting\n',
                GREETING_SPEC.replace('"Hello, Roblox!"', '"Bye"'))
```

- [ ] **Step 2: RED 確認**

Run: `PYTHONPATH=. python3 -m tests.native.test_catalog tests.native.test_hooks.HookContractTests tests.native.test_hooks.RobloxHookTests`
Expected: FAIL（`manual hook missing`）

- [ ] **Step 3: フックを書く**

`roblox/rojo/.githooks/pre-commit`:
```sh
#!/bin/sh
# Manual opt-in only. Run the same gate as the project-local check.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"
sh scripts/check.sh format
exec sh scripts/check.sh lint
```

`roblox/rojo/.githooks/pre-push`:
```sh
#!/bin/sh
# Manual opt-in only. Run the same gate as the project-local check.
set -eu
root=$(git rev-parse --show-toplevel)
cd "$root"
exec sh scripts/check.sh all
```

`chmod 755 roblox/rojo/.githooks/*`

- [ ] **Step 4: GREEN 確認（静的・Roblox 全体）**

```sh
PYTHONPATH=. python3 -m tests.native.test_catalog tests.native.test_hooks.HookContractTests tests.native.test_hooks.RobloxHookTests
pnpm test:native:static
pnpm test:native:roblox
```
Expected: 全 PASS。`test:native:static` は Rust/Swift の静的テストも含め PASS（回帰なし）。

- [ ] **Step 5: Commit**

```sh
git add roblox/rojo/.githooks tests/native/test_hooks.py
git commit -m "feat: add Roblox Git hooks with real gate tests"
```

---

### Task 4: 記録と最終確認

**Files:**
- Modify: `progress.md`、`docs/superpowers/specs/2026-10-11-roblox-rojo-settings-design.md`（§6 次のアクションのチェック更新）

- [ ] **Step 1: progress.md に「Roblox Task — roblox-rojo」節を追加**

内容: BASE commit、実装 head、TDD の RED→GREEN 要約、実行した suite と件数、ツール版と `seed/facts.md` の要点、未検証範囲（Studio 実同期・Windows/Linux・Wally 実取得）、`pnpm test`（TypeScript）を実行したかどうか。

- [ ] **Step 2: 回帰確認**

```sh
pnpm test:native:static
pnpm test:native:roblox
```
（`pnpm test` は依存導入が必要。未導入なら実行せず、未実行と progress.md に書く。）

- [ ] **Step 3: Commit**

```sh
git add progress.md docs/superpowers/specs/2026-10-11-roblox-rojo-settings-design.md
git commit -m "docs: record Roblox Rojo settings verification"
```

main への統合・push はユーザー判断（superpowers:finishing-a-development-branch）。
