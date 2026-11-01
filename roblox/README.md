# Roblox（Luau）設定

- [Roblox ゲーム（Rojo）の品質設定](roblox-game/README.md): Rokit で版固定した Rojo/StyLua/Selene/luau-lsp/
  Lune/Wally。Rojo でファイル管理する Roblox ゲーム用です。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。
コピー先と既存ファイル保護の手順は leaf README を参照してください。
macOS 実検証が対象で、Windows/Linux と Roblox Studio 実同期は未検証です。

保守 suite は repository root の `pnpm test:native:static` と `pnpm test:native:roblox` から
明示実行します。未実行 native suite は既存 TypeScript suite の成功と分けて記録します。

### 保守 suite の前提（Git 管理外 seed）

`test:native:roblox` は実 tool と次の seed を必要とし、自動では用意しません。不在なら非0で止まります。
導入・取得は対象と保存先を確認し、別途承認してから行ってください。

1. Rokit で `roblox/roblox-game/rokit.toml` の6ツールを導入する（Apple Silicon は Wally 用に Rosetta 2）。
2. `.verification/native/roblox/seed/` に `selene.toml`（`std = "roblox"`、`roblox-std-source = "pinned"`）を置き、
   そこで `selene generate-roblox-std` を実行して `roblox.yml` を作る。
3. 同じ場所に luau-lsp 1.69.0 の `globalTypes.d.luau` を `globalTypes-1.69.0.d.luau` として保存し、
   SHA256 が `roblox/roblox-game/scripts/check.sh` の値と一致することを確認する。

4. 承認済みprivate ReleaseからCLI archiveを取得し、SHA256を照合してbinaryを別の検証領域へ展開します。
   元asset名のままのarchiveと、regular fileのbinaryを明示します。suiteは自動取得しません。

```sh
LUAU_SIMILARITY_BINARY=/absolute/verified/luau-similarity \
LUAU_SIMILARITY_ARCHIVE=/absolute/luau-similarity-v0.1.0-aarch64-apple-darwin.tar.gz \
pnpm test:native:roblox
```

suiteは固定binaryを所有fixtureへコピーし、Lune内蔵型宣言をfixtureのHOMEで生成します。
private setupのunit試験はgh process stubを使い、通常の検査からnetworkや認証を呼びません。
既存の型定義取得試験だけは上記の固定公開URLへ明示接続します。
global dispatcherとlinked worktreeの試験は現在設定されたglobal hookのbytesを試験用HOMEへ
コピーして実行し、元のglobal設定／hook／core.bare不変を照合します。実物がなければ前提不足として失敗します。
Git fixtureへ渡す前にGIT_*を除去し、本物のrepo/index/configを操作しないようにします。

実private setupは別の明示試験で検証します。既存のgh認証を利用し、Lune型生成は所有領域の
専用HOME/cwdへ限定します。単なる隔離HOMEでは既存認証が解決せず、正しく停止する場合があります。
認証・権限不足を見つけたら迂回せず、本人に確認してください。
