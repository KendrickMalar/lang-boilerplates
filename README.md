# lang-boilerplates

Scaffoldでプロジェクトを作る際に参照する、言語別の設定と導入手順です。製品コードではなく、コピーして使う設定を管理します。MITライセンスです。

## 言語別の入口

| 言語       | 導入手順                                       |
| ---------- | ---------------------------------------------- |
| TypeScript | [typescript/README.md](./typescript/README.md) |

Scaffoldは言語を選んだ後、当該言語のREADMEを読み、参照された設定ファイルと導入条件を確認します。他言語は必要になった時点で追加します。

## このリポジトリの検証

Node 24以上、pnpm 12.6.0を使います。依存導入前に環境・権限を確認してください。

```sh
pnpm install --ignore-scripts --store-dir .verification/pnpm-store
pnpm test
```

共通設定の構造、3presetのコピー後の型チェック・Lint・整形・テスト・ビルド、正常系と異常系、実Gitフックを検証します。fixtureとログは `.verification/` に生成し、Gitへ追加しません。テストはsynthetic HOMEとローカルbare remoteを使い、ユーザーのグローバルGitフックを変更せず、GitHubへ試験pushしません。

推移依存はルートpnpm-lock.yamlで固定します。型定義とLintの対応範囲やpnpmの依存安全設定を変更したら、3presetを再検証してください。

## 範囲

- TypeScript: Node/CLI、汎用Web、npmライブラリ。
- CI、フレームワーク固有設定、自動コピーCLI、npm公開は含みません。
- コピー対象・既存ファイル保護・Huskyの手動有効化は言語別READMEを正本とします。

## ライセンス

[MIT](./LICENSE)。利用プロジェクトへコピーする際は著作権表示とライセンス文を保持してください。
