# TypeScript Boilerplate

このREADMEは、TypeScriptプロジェクトを作成する際の推奨configの入口です。
以下のパスは**このREADMEからの相対パス**です。

## 用途を選ぶ

| 用途              | 設定・導入手順                           |
| ----------------- | ---------------------------------------- |
| Nodeアプリ／CLI   | [node/README.md](./node/README.md)       |
| ブラウザの汎用Web | [web/README.md](./web/README.md)         |
| npmライブラリ     | [library/README.md](./library/README.md) |

各ディレクトリは自己完結しています。選んだ1つのディレクトリに必要な設定・Gitフック・README・MITライセンスが揃っており、親や兄弟ディレクトリの設定ファイルをコピーする必要はありません。

選択したREADMEを読み、そこで列挙された同じディレクトリ内のファイルを対象プロジェクトへ導入してください。既存設定・Gitフックの確認、依存インストール、有効化の条件も、各READMEに記載しています。

pnpm 12.6.0、Node 24.15以上の24系またはNode26以上（Node25は対象外）、ESMを標準とします。製品コード・サンプルテスト・HTMLは含みません。React等のフレームワーク固有設定やCJS二重配布は対象外です。
