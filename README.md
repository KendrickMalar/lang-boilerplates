# lang-boilerplates

Scaffoldでプロジェクトを作る際に参照する、言語別の設定と導入手順です。製品コードではなく、コピーして使う設定を管理します。MITライセンスです。

## 言語別の入口

| 言語                        | 導入手順                                       |
| --------------------------- | ---------------------------------------------- |
| TypeScript                  | [typescript/README.md](./typescript/README.md) |
| Rust                        | [rust/README.md](./rust/README.md)             |
| Swift                       | [swift/README.md](./swift/README.md)           |
| Roblox (Luau)               | [roblox/README.md](./roblox/README.md)         |
| Godot（GDScript）           | [godot/README.md](./godot/README.md)           |
| Blender Python（3D モデル） | [blender/README.md](./blender/README.md)       |

Scaffoldは言語を選んだ後、当該言語のREADMEを読み、参照された設定ファイルと導入条件を確認します。各用途は親/兄弟設定に依存せず自己完結します。

## 用途ごとのアーキテクチャ

用途 README の「アーキテクチャ」節に、依存の向きの選択肢と、それを Lint で強制する設定（各用途の `architecture/`）を置きます。scaffold は仕様策定で選択肢を提示し、基本設計で選ばれたものを導入します。

| 用途                                                       | 選択肢                                                        | 既定              |
| ---------------------------------------------------------- | ------------------------------------------------------------- | ----------------- |
| [TypeScript cli](./typescript/cli/README.md)               | オニオン／機能コア＋命令的シェル／機能別の縦割り              | オニオン          |
| [TypeScript web](./typescript/web/README.md)               | オニオン（選択肢なし）                                        | オニオン          |
| [TypeScript web-game](./typescript/web-game/README.md)     | ルールの純粋コア／ECS／コア＋エンジンの殻                     | ルールの純粋コア  |
| [TypeScript ts-library](./typescript/ts-library/README.md) | 入口1つ＋internal／コア＋実行環境アダプター／機能別の複数入口 | 入口1つ＋internal |

## 全言語共通の Git フック

全言語・全用途で Husky **9.1.7** を必須にし、commit / push 前にテストを含む全体検査を実行します。
Node は24.15以上の24系または26以上（25は対象外）、pnpm **12.6.0** を使います。
Husky は Git root に1つだけ置き、複数言語の検査を root の check に集約します。
依存 install とフック有効化は別手順です。既存フック・global hooksPath を無断で置き換えません。
製品へのコピー・統合・明示有効化の詳細は各 leaf README に従います。既存プロジェクトへ自動適用しません。

## このリポジトリの検証

Node 24.15以上の24系またはNode26以上（Node25は対象外）、pnpm 12.6.0を使います。依存導入前に環境・権限を確認してください。
保守試験でも、用途別READMEのsimilarity-ts導入手順に従い、固定版0.5.0とLICENSEをこのリポジトリの`.tools/similarity/`へ明示配置します。テストはこの検証済みバイナリを各fixtureへコピーします。未導入をskipや自動ダウンロードで回避しません。

依存は worktree ごとに導入します。ルートの導入では `--store-dir` を付けず、pnpm の共通ストア（`pnpm store path`）を使います。2つ目以降の worktree はストアから複製またはハードリンクで取り込むため、再ダウンロードしません。テストが fixture へ依存を入れるときは、引き続き `.verification/pnpm-store` を使って隔離します。

```sh
pnpm install --frozen-lockfile --ignore-scripts --engine-strict
PLAYWRIGHT_BROWSERS_PATH="$PWD/.verification/playwright" pnpm exec playwright install chromium --only-shell
pnpm test
```

TypeScript の自己完結した4用途ディレクトリの構造、選択ディレクトリだけをコピーした後の型チェック・Lint・整形・テスト・ビルド、正常系と異常系、実Gitフックを検証します。fixtureとログは `.verification/` に生成し、Gitへ追加しません。テストはsynthetic HOMEとローカルbare remoteを使い、ユーザーのグローバルGitフックを変更せず、GitHubへ試験pushしません。

推移依存はルートpnpm-lock.yamlで固定します。型定義とLintの対応範囲やpnpmの依存安全設定を変更したら、4用途を再検証してください。

## Husky 移行の検証

`pnpm test:husky` は実 Git・Husky・ローカル bare remote で各 native leaf の拒否動作を検証します。
遅い native compiler/test command だけを代替しており、Swift/Rust/Godot/Blender の実 build/test 成功とは別です。
`LUNE_BIN=/approved/path/to/lune pnpm test:husky:luau` は既存 Lune 0.10.5 で、
Husky・Node関連入力が Git に追跡されていないと Roblox の実 snapshot が拒否することを検証します。
Luneや各言語toolのインストールは行いません。compiler/Studio/Xcode/実機を使う確認は従来のnative suiteで別途行います。

## Native の保守検証（明示実行）

Python 3.11+ が必要です。既存 `pnpm test` は TypeScript suite のままで、native
suite を自動導入/自動実行しません。tool や依存は対象・保存先・副作用の別承認後に
用意し、不足/空 source/空 test/lock 欠落は非0です。各 leaf README が導入の正本です。

```sh
pnpm test:native:static
pnpm test:native:quality # 設定の実効検証。既存Clippy/SwiftLint/swift-format/luau-lspのみ使用
pnpm test:native:rust-game # rust/game・rust/web-game・rust/web。隔離した Rust 1.99.1 と各 tool を使用
pnpm test:native:blender # Blender のアーキテクチャ強制設定。既存 ruff 0.17.0・Blender 5.2.2 のみ使用
pnpm test:native:macos
pnpm test:native:roblox
NATIVE_IOS_TEST_DESTINATION='platform=iOS Simulator,id=APPROVED-UUID' pnpm test:native:ios
```

明示した Python test modules を実行し、test 0件の discovery を使いません。
Rust は Git 管理外の隔離 toolchain（`.verification/native/rust-game/`）と固定版の cargo subcommand が必要で、自動導入しません。
hook は通常 working-tree check script を検査します。未所有変更を除外する検証に限り、
承認済み full SHA を `NATIVE_HOOK_CHECK_REF` に明示指定できます。選択ref/script hashを
記録し、不正/欠落refは非0。この固定refの成功は working-tree版の承認を意味しません。
Swift は選択 Xcode と SwiftLint が必要で、iOS は許可済み具体的 Simulator UUID を指定。
ローカル bare remote だけへ hook 試験 push し、global hooksPath/フックを変更しません。
Native suite 未実行は TypeScript 成功と区別します。

実検証範囲は macOS の Rust サーバー leaf の check（fixture crate）、macOS app test/build、
iOS27.0 iPhone17/iPad(A16) Simulator app test/build です。Package-only/mock 成功を
製品アプリ合格としません。Windows/Linux native/PowerShell は未実行、iOS17 runtime/
実機/UI flows/製品署名・release/archive/公開は未検証です。全 OS 合格とは宣言しません。

## 範囲

- TypeScript: CLI／Nodeアプリ（cli）、汎用Web（web）、ブラウザゲーム（web-game。2D・3D。3D は Three.js＋Rapier）、npmライブラリ（ts-library）。
- Rust: サーバー用の品質設定（Rust1.99.1/edition2024、依存・source なし）。game（リアルタイム対戦・ルーム制（WebSocket）のゲームサーバー）/ web-game（ソシャゲ型の Web ゲーム API）/ web（一般の HTTP API）。
- Swift: 標準 Xcode app 用、Swift6 mode/macOS15/iOS17/SwiftLint0.65.1。xcconfig の実効接続を確認。
- Roblox: Rojo でファイル管理するゲーム用（roblox-game）（Rojo7.7.1/StyLua2.5.2/Selene0.32.0/luau-lsp1.69.0/Lune0.10.5/Wally0.3.2 を Rokit で固定）。macOS 実検証、Studio 実同期は未検証。
- Godot: モバイルゲーム用（mobile-game、Godot4.7.2/gdtoolkit4.5.0）。型付き GDScript を強制し、ヘッドレスで検査とテスト。asuka で手動確認、実ツール suite なし。
- Blender: 3D モデルをコードで作る用（Blender5.2.2 LTS/ruff0.17.0/glTF-Transform4.5.1）。glTF 書き出しと検査。asuka で手動確認、実ツール suite なし。
- 製品 source/frontend/fixture/cache/秘密情報/署名 asset は配布しません。
- CI、フレームワーク固有設定、自動コピーCLI、npm公開は含みません。
- コピー対象・既存ファイル保護・Huskyの手動有効化は言語別READMEを正本とします。

## ライセンス

[MIT](./LICENSE)。利用プロジェクトへコピーする際は著作権表示とライセンス文を保持してください。
