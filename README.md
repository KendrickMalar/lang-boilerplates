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

## このリポジトリの検証

Node 24.15以上の24系またはNode26以上（Node25は対象外）、pnpm 12.6.0を使います。依存導入前に環境・権限を確認してください。

```sh
pnpm install --ignore-scripts --engine-strict --store-dir .verification/pnpm-store
PLAYWRIGHT_BROWSERS_PATH="$PWD/.verification/playwright" pnpm exec playwright install chromium --only-shell
pnpm test
```

TypeScript の自己完結した4用途ディレクトリの構造、選択ディレクトリだけをコピーした後の型チェック・Lint・整形・テスト・ビルド、正常系と異常系、実Gitフックを検証します。fixtureとログは `.verification/` に生成し、Gitへ追加しません。テストはsynthetic HOMEとローカルbare remoteを使い、ユーザーのグローバルGitフックを変更せず、GitHubへ試験pushしません。

推移依存はルートpnpm-lock.yamlで固定します。型定義とLintの対応範囲やpnpmの依存安全設定を変更したら、4用途を再検証してください。

## Native の保守検証（明示実行）

Python 3.11+ が必要です。既存 `pnpm test` は TypeScript suite のままで、native
suite を自動導入/自動実行しません。tool や依存は対象・保存先・副作用の別承認後に
用意し、不足/空 source/空 test/lock 欠落は非0です。各 leaf README が導入の正本です。

```sh
pnpm test:native:static
pnpm test:native:quality # 設定の実効検証。既存Clippy/SwiftLint/swift-format/luau-lspのみ使用
pnpm test:native:rust
pnpm test:native:macos
pnpm test:native:roblox
NATIVE_IOS_TEST_DESTINATION='platform=iOS Simulator,id=APPROVED-UUID' pnpm test:native:ios
```

明示した Python test modules を実行し、test 0件の discovery を使いません。
Rust は Git 管理外の承認済み lock/依存審査・実 build/test record が必要です。
Rust hook fixture は capacity 制約のため `NATIVE_HOOK_RUST_FIXTURE=fixture-50ncrnnd`
という既存所有 fixture の再利用を明示承認した環境だけで実行します。不在/未承認は非0。
新規検証環境の取得/fixture 方針は別途相談し、既存 fixture を勝手に上書きしません。
この capacity 制約下では新 Rust target を作る通常 runtime suite をそのまま起動せず、
承認済み所有 fixture を再利用する統合 runner を使います。
hook は通常 working-tree check script を検査します。未所有変更を除外する検証に限り、
承認済み full SHA を `NATIVE_HOOK_CHECK_REF` に明示指定できます。選択ref/script hashを
記録し、不正/欠落refは非0。この固定refの成功は working-tree版の承認を意味しません。
Swift は選択 Xcode と SwiftLint が必要で、iOS は許可済み具体的 Simulator UUID を指定。
ローカル bare remote だけへ hook 試験 push し、global hooksPath/フックを変更しません。
Native suite 未実行は TypeScript 成功と区別します。

実検証範囲は macOS Cargo/backend ACL mock/native build、macOS app test/build、
iOS27.0 iPhone17/iPad(A16) Simulator app test/build です。Package-only/mock 成功を
製品アプリ合格としません。Windows/Linux native/PowerShell は未実行、iOS17 runtime/
実機/UI flows/製品署名・release/archive/公開は未検証です。全 OS 合格とは宣言しません。

## 範囲

- TypeScript: Node/CLI、汎用Web、ブラウザ3Dゲーム（Three.js＋Rapier）、npmライブラリ。
- Rust: Tauri desktop の backend のみ（Rust1.92.0/edition2024/Tauri2.12.2/tauri-build2.7.1）。frontend は利用側で接続。
- Swift: 標準 Xcode app 用、Swift6 mode/macOS15/iOS17/SwiftLint0.65.1。xcconfig の実効接続を確認。
- Roblox: Rojo でファイル管理するゲーム用（Rojo7.7.1/StyLua2.5.2/Selene0.32.0/luau-lsp1.69.0/Lune0.10.5/Wally0.3.2 を Rokit で固定）。macOS 実検証、Studio 実同期は未検証。
- Godot: モバイルゲーム用（Godot4.7.2/gdtoolkit4.5.0）。型付き GDScript を強制し、ヘッドレスで検査とテスト。asuka で手動確認、実ツール suite なし。
- Blender: 3D モデルをコードで作る用（Blender5.2.2 LTS/ruff0.17.0/glTF-Transform4.5.1）。glTF 書き出しと検査。asuka で手動確認、実ツール suite なし。
- 製品 source/frontend/fixture/cache/秘密情報/署名 asset は配布しません。
- CI、フレームワーク固有設定、自動コピーCLI、npm公開は含みません。
- コピー対象・既存ファイル保護・Huskyの手動有効化は言語別READMEを正本とします。

## ライセンス

[MIT](./LICENSE)。利用プロジェクトへコピーする際は著作権表示とライセンス文を保持してください。
