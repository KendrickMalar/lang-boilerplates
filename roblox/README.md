# Roblox（Luau）設定

- [Rojo プロジェクトの品質設定](rojo/README.md): Rokit で版固定した Rojo/StyLua/Selene/luau-lsp/
  Lune/Wally。Rojo でファイル管理する Roblox ゲーム用です。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。
コピー先と既存ファイル保護の手順は leaf README を参照してください。
macOS 実検証が対象で、Windows/Linux と Roblox Studio 実同期は未検証です。

保守 suite は repository root の `pnpm test:native:static` と `pnpm test:native:roblox` から
明示実行します。未実行 native suite は既存 TypeScript suite の成功と分けて記録します。
