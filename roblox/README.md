# Roblox（Luau）設定

- [Rojo プロジェクトの品質設定](rojo/README.md): Rokit で版固定した Rojo/StyLua/Selene/luau-lsp/
  Lune/Wally。Rojo でファイル管理する Roblox ゲーム用です。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。
コピー先と既存ファイル保護の手順は leaf README を参照してください。
macOS 実検証が対象で、Windows/Linux と Roblox Studio 実同期は未検証です。

保守 suite は repository root の `pnpm test:native:static` と `pnpm test:native:roblox` から
明示実行します。未実行 native suite は既存 TypeScript suite の成功と分けて記録します。

### 保守 suite の前提（Git 管理外 seed）

`test:native:roblox` は実 tool と次の seed を必要とし、自動では用意しません。不在なら非0で止まります。
導入・取得は対象と保存先を確認し、別途承認してから行ってください。

1. Rokit で `roblox/rojo/rokit.toml` の6ツールを導入する（Apple Silicon は Wally 用に Rosetta 2）。
2. `.verification/native/roblox/seed/` に `selene.toml`（`std = "roblox"`、`roblox-std-source = "pinned"`）を置き、
   そこで `selene generate-roblox-std` を実行して `roblox.yml` を作る。
3. 同じ場所に luau-lsp 1.69.0 の `globalTypes.d.luau` を `globalTypes-1.69.0.d.luau` として保存し、
   SHA256 が `roblox/rojo/scripts/check.sh` の値と一致することを確認する。
