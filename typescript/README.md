# TypeScript — Scaffold向け導入手順

このREADMEは、ScaffoldでTypeScriptを選んだ際の設定導入の入口です。以下のパスは**このREADMEのあるディレクトリからの相対パス**です。設定を読むことと、コピー・インストール・Git設定変更の許可は別です。

## 1. 用途を選ぶ

| 用途              | 選択するpreset                | 製品側で用意するもの                     |
| ----------------- | ----------------------------- | ---------------------------------------- |
| Nodeアプリ／CLI   | [node](./presets/node/)       | `src/index.ts`、`tests/**/*.test.ts`     |
| ブラウザの汎用Web | [web](./presets/web/)         | `src/`、`index.html`、テスト             |
| npmライブラリ     | [library](./presets/library/) | `src/index.ts`、テスト、公開用メタデータ |

pnpm 12.6.0、Node 24以上、ESMが前提です。Node 24系を標準とし、[.node-version](./.node-version)に記載します。React、Next.jsなどの固有設定、CLIのbin、DOMテスト環境、CJS二重配布は含めません。フレームワーク生成済みの場合は既存設定を優先し、必要な差分だけを検討してください。

製品コード・サンプルテスト・HTMLは配布しません。設定だけをコピーしても、型チェック・テスト・ビルドが成功するとは限りません。空のテストを合格扱いにしないでください。

## 2. 共通設定を読む・コピーする

同じディレクトリの共通設定と、**選択した1つのpreset**を対象プロジェクトのルートへコピーします。preset内の相対パスはコピー後の配置を前提にしています。presetディレクトリ内でそのまま実行しないでください。

| コピー元                                           | コピー先（対象プロジェクトのルート基準） | 役割                                            |
| -------------------------------------------------- | ---------------------------------------- | ----------------------------------------------- |
| [tsconfig.base.json](./tsconfig.base.json)         | `tsconfig.base.json`                     | 共通の厳密な型チェック                          |
| [eslint.base.mjs](./eslint.base.mjs)               | `eslint.base.mjs`                        | 型情報Lint、any禁止、Promise待ち忘れ検出        |
| [.prettierrc.json](./.prettierrc.json)             | `.prettierrc.json`                       | 2スペース、セミコロンあり、ダブルクォート、LF   |
| [.prettierignore](./.prettierignore)               | `.prettierignore`                        | 生成物などを整形から除外                        |
| [.editorconfig](./.editorconfig)                   | `.editorconfig`                          | エディタ間の編集設定                            |
| [.gitignore](./.gitignore)                         | `.gitignore`                             | 生成物・環境変数ファイルをGitから除外           |
| [.node-version](./.node-version)                   | `.node-version`                          | Nodeの標準major                                 |
| [lint-staged.config.mjs](./lint-staged.config.mjs) | `lint-staged.config.mjs`                 | 変更ファイルの整形・Lint                        |
| [pnpm-workspace.yaml](./pnpm-workspace.yaml)       | `pnpm-workspace.yaml`                    | 自動install禁止、依存の待機期間・script許可方針 |
| [pre-commit](./.husky/pre-commit)                  | `.husky/pre-commit`                      | commit前の変更ファイル検査                      |
| [pre-push](./.husky/pre-push)                      | `.husky/pre-push`                        | push前の全体検証                                |

対象の全ファイルをコピー前に調べてください。ドットファイルを省略しないでください。既存ファイル、symlink、既存.huskyがある場合は停止し、差分と影響を提示して許可を得ます。既存ファイルを無条件に上書きする一括コピーは行いません。既存pnpm-workspace.yamlのworkspace定義やscript許可を失わせないでください。

設定は[MITライセンス](../LICENSE)です。コピー時はライセンス文と著作権表示を、既存プロジェクトのライセンスを上書きしない形で保持してください（例: `LICENSE.lang-boilerplates`）。利用プロジェクト自身のライセンスをMITへ自動変更しません。

## 3. 選んだpresetの設定をコピーする

### Node／CLI

| コピー元                                                  | コピー先              |
| --------------------------------------------------------- | --------------------- |
| [package.json](./presets/node/package.json)               | `package.json`        |
| [tsconfig.json](./presets/node/tsconfig.json)             | `tsconfig.json`       |
| [tsconfig.build.json](./presets/node/tsconfig.build.json) | `tsconfig.build.json` |
| [eslint.config.mjs](./presets/node/eslint.config.mjs)     | `eslint.config.mjs`   |
| [vitest.config.ts](./presets/node/vitest.config.ts)       | `vitest.config.ts`    |

NodeNextで解決し、製品srcだけをdistへ出力します。DOM型は含めません。開発時は`pnpm dev`でtsxを使います。CLIのentryが決まった後にbinと実行権限を別途設定してください。

### Web

| コピー元                                                 | コピー先              |
| -------------------------------------------------------- | --------------------- |
| [package.json](./presets/web/package.json)               | `package.json`        |
| [tsconfig.json](./presets/web/tsconfig.json)             | `tsconfig.json`       |
| [tsconfig.app.json](./presets/web/tsconfig.app.json)     | `tsconfig.app.json`   |
| [tsconfig.tools.json](./presets/web/tsconfig.tools.json) | `tsconfig.tools.json` |
| [eslint.config.mjs](./presets/web/eslint.config.mjs)     | `eslint.config.mjs`   |
| [vite.config.ts](./presets/web/vite.config.ts)           | `vite.config.ts`      |
| [vitest.config.ts](./presets/web/vitest.config.ts)       | `vitest.config.ts`    |

Bundler解決とViteを使います。ブラウザsrcはDOM型とvite/client型で検査し、tests/configはNode型を含む別の型環境で検査します。`pnpm typecheck`は`tsc -b --noEmit`です。テストはNode環境のため、DOM操作の実行テストが必要なら別途環境を選びます。React等を選ぶ際は対応するJSX設定・依存・プラグインを追加してください。

### npmライブラリ

| コピー元                                                     | コピー先              |
| ------------------------------------------------------------ | --------------------- |
| [package.json](./presets/library/package.json)               | `package.json`        |
| [tsconfig.json](./presets/library/tsconfig.json)             | `tsconfig.json`       |
| [tsconfig.build.json](./presets/library/tsconfig.build.json) | `tsconfig.build.json` |
| [eslint.config.mjs](./presets/library/eslint.config.mjs)     | `eslint.config.mjs`   |
| [vitest.config.ts](./presets/library/vitest.config.ts)       | `vitest.config.ts`    |

ESMのJSと型定義をdistへ出力し、テスト・設定を配布物から除きます。初期設定は誤公開防止のため`private: true`です。公開前にname、version、license、repository、private、exports、配布内容を確認し、公開許可を別途得てください。自動publishは行いません。

## 4. package.jsonと依存を整える

- 新規プロジェクトではnameを製品名へ変更します。
- 既存package.jsonでは、scriptsとdevDependenciesの差分を確認して必要なものだけ統合します。
- `type: "module"`は既存CJSコードの意味を変えます。既存プロジェクトへ黙って適用しません。
- TypeScriptは6.0.3、typescript-eslintは8.71.1を固定しています。TypeScript 7はこのLint版の対応範囲外です。最新版へ一括更新せず、peer要件と検証結果を確認します。
- Node型定義は24系に合わせ、下限より新しいAPIを無条件に許容しません。

対象と依存の導入許可を確認してから、プロジェクトのルートで実行します。

```sh
pnpm install --ignore-scripts
```

pnpm-lock.yamlを生成しGitで管理します。prepare/postinstallによるHuskyの自動有効化は設定していません。

pnpmの設定は検査時の自動installを禁止します。公開24時間未満の依存は拒否し、未承認の依存ビルドscriptはエラーにします。現在のesbuild@0.28.2はinstall scriptを明示的に不許可とし、optional binaryを使います。依存更新で新しいscriptや待機期間エラーが出たら停止し、版・配布物・影響を確認してください。勝手な例外追加や全script許可で通しません。

## 5. 製品コードとテストを用意して検証する

| コマンド            | 内容                                   |
| ------------------- | -------------------------------------- |
| `pnpm typecheck`    | src・テスト・TS設定の型チェック        |
| `pnpm lint`         | 型情報Lint。warningも不合格            |
| `pnpm format`       | 整形を適用                             |
| `pnpm format:check` | 整形済みか検査                         |
| `pnpm test`         | Vitestを1回実行。テストなしは不合格    |
| `pnpm build`        | 製品ビルド                             |
| `pnpm check`        | 上記の検査を順に実行。最初の失敗で停止 |

`pnpm check`は型チェック → Lint → 整形検査 → テスト → ビルドの順です。変更ファイルだけの検査をプロジェクト全体の合格と扱いません。依存が不整合なら、検証中に自動導入せずinstall段階へ戻ります。

## 6. Gitフックを確認し、許可後に有効化する

**ここまでの設定コピー・依存導入では、Gitフックはまだ有効になっていません。**

1. Git rootと現在のプロジェクトルートが一致することを確認します。
2. 既存core.hooksPath、その指すフック、Git共通ディレクトリのhooks、既存.huskyを調べます。
3. 既存の有効なフックや別のhooksPathがある場合は停止します。既存.huskyのファイルが今回コピーしたもの以外なら、コピー段階へ戻って確認します。Git rootと異なるサブディレクトリ構成も、このテンプレートでは自動設定しません。
4. 既存フックを保持する統合方針を別途決めるか、既存フックがない新規Git rootで、プロジェクトローカルGit設定の変更許可を得ます。

読み取り確認の例です。

```sh
git rev-parse --show-toplevel
git rev-parse --git-common-dir
git config --show-origin --get core.hooksPath
```

core.hooksPath未設定時の最後のコマンドのexit 1は未設定を表します。Gitのhooksディレクトリにある.sampleは有効フックではありません。グローバルhooksPathやフックは変更しません。

条件と許可が揃った後だけ、プロジェクトのGit rootで実行します。

```sh
pnpm exec husky
```

この操作はプロジェクトローカルcore.hooksPathを変更し、.husky/_に内部ファイルを生成します。.husky/_をGitへ追加しません。`husky init`による既存pre-commitの上書きは行いません。

- commit前: lint-stagedで変更ファイルの整形・Lint。型チェックは全体検査へ任せます。
- push前: `pnpm check`を実行し、失敗ならpushを停止します。
- 有効化後は、許可されたローカルGit操作でフック動作を確認し、core.hooksPathと結果を読み戻します。テスト目的だけでGitHubへpushしません。

HuskyはCIと同じ強制力を持ちません。未設定端末、GitHub上の直接編集、Gitのhookスキップ操作では検証を保証できません。スキップで不合格を回避せず、検証出力と実際の有効化状態を記録してください。

## 保守と検証

設定リポジトリ自身のtestsとルートpackage.jsonは、利用プロジェクトへコピーしません。リポジトリの検証手順は[ルートREADME](../README.md)を参照してください。

## 公式資料

- https://www.typescriptlang.org/tsconfig/
- https://typescript-eslint.io/getting-started/typed-linting
- https://typicode.github.io/husky/how-to.html
- https://pnpm.io/settings/build
- https://pnpm.io/settings/dependency-resolution
