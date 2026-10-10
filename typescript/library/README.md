# TypeScript npmライブラリ Boilerplate

npmライブラリ向けの設定一式です。ESMのJSと型定義をdistへ出力します。ルートtestsとsrc内の`*.test.ts`・`*.spec.ts`・`__tests__/`をテスト対象とし、ビルドから除外します。初期設定は誤公開防止のため`private: true`です。公開前にname、version、license、repository、private、exports、配布内容を確認し、公開許可を別途得てください。自動publishは行いません。

このディレクトリだけで設定が完結します。以下のパスは**このREADMEからの相対パス**です。親・兄弟の設定ファイルには依存しません。pnpm 12.6.0、Node 24以上、ESMが前提です。

## 1. 設定を確認・コピーする

表のファイルを対象プロジェクトのルートへ導入します。ドットファイルと.husky内のフックも含みます。READMEは導入手順として読み、コピーは任意です。既存ファイル・symlink・既存.huskyがある場合は停止し、差分と影響を提示して許可を得てください。既存package.jsonやpnpm-workspace.yamlを丸ごと上書きせず、必要な差分を統合します。

| 同じディレクトリのコピー元                         | コピー先（対象プロジェクトのルート基準） |
| -------------------------------------------------- | ---------------------------------------- |
| [package.json](./package.json)                     | `package.json`                           |
| [tsconfig.base.json](./tsconfig.base.json)         | `tsconfig.base.json`                     |
| [tsconfig.json](./tsconfig.json)                   | `tsconfig.json`                          |
| [eslint.base.mjs](./eslint.base.mjs)               | `eslint.base.mjs`                        |
| [eslint.config.mjs](./eslint.config.mjs)           | `eslint.config.mjs`                      |
| [.prettierrc.json](./.prettierrc.json)             | `.prettierrc.json`                       |
| [.prettierignore](./.prettierignore)               | `.prettierignore`                        |
| [.editorconfig](./.editorconfig)                   | `.editorconfig`                          |
| [.gitignore](./.gitignore)                         | `.gitignore`                             |
| [.node-version](./.node-version)                   | `.node-version`                          |
| [lint-staged.config.mjs](./lint-staged.config.mjs) | `lint-staged.config.mjs`                 |
| [pnpm-workspace.yaml](./pnpm-workspace.yaml)       | `pnpm-workspace.yaml`                    |
| [vitest.config.ts](./vitest.config.ts)             | `vitest.config.ts`                       |
| [tsconfig.build.json](./tsconfig.build.json)       | `tsconfig.build.json`                    |
| [clean-dist.mjs](./clean-dist.mjs)                 | `clean-dist.mjs`                         |
| [.husky/pre-commit](./.husky/pre-commit)           | `.husky/pre-commit`                      |
| [.husky/pre-push](./.husky/pre-push)               | `.husky/pre-push`                        |
| [LICENSE](./LICENSE)                               | `LICENSE.lang-boilerplates`              |

設定はMITです。ライセンス文・著作権表示を保持してください。LICENSEは既存ライセンスを上書きしないよう、例えばLICENSE.lang-boilerplatesとして保存します。利用プロジェクト自身のライセンスを自動変更しません。

製品コード・サンプルテスト・HTMLは配布しません。利用側でsrcとtests/**/*.test.tsを用意してください。設定だけをコピーした状態やテストなしを検証合格にしません。フレームワーク生成済みなら既存設定を優先し、差分を確認します。

**libraryのbuildは生成物専用distを削除してから再生成します。** 初回build前に既存distの由来と内容を確認し、生成物専用と確認できない場合は停止して相談してください。distに手書きファイルを置かないでください。clean-dist.mjsと実行rootが一致しない場合、distがsymlinkまたは通常ディレクトリ以外の場合は、削除せず停止します。src・テスト・ログは削除対象ではありません。

## 2. package.jsonと依存を整える

- nameを製品名に変更します。既存package.jsonではscripts/devDependenciesの差分を確認します。
- type:moduleは既存CJSコードの意味を変えます。黙って適用しません。
- TypeScript 6.0.3、typescript-eslint 8.71.1を固定しています。TypeScript 7はこのLint版の対応範囲外です。一括更新せずpeer要件と検証を確認します。
- Node型定義は24系です。下限より新しいAPIを無条件に許容しません。

対象と導入許可を確認してから、対象プロジェクトのrootで実行します。

```sh
pnpm install --ignore-scripts
```

生成したpnpm-lock.yamlをGitで管理します。prepare/postinstallによるHuskyの自動有効化はありません。pnpmの検証時自動installは禁止、公開24時間未満の依存は拒否、未承認の依存build scriptはエラーにします。現在のesbuild@0.28.2はinstall scriptを不許可とし、optional binaryを使います。エラーを勝手な例外追加や全script許可で回避しません。

## 3. 製品コードとテストを用意して検証する

| コマンド            | 内容                                                     |
| ------------------- | -------------------------------------------------------- |
| `pnpm typecheck`    | src・テスト・TS設定の型チェック                          |
| `pnpm lint`         | 型情報Lint。warningも不合格                              |
| `pnpm format`       | 整形適用                                                 |
| `pnpm format:check` | 整形検査                                                 |
| `pnpm test`         | Vitestを1回実行。テストなしは不合格                      |
| `pnpm build`        | 製品ビルド                                               |
| `pnpm check`        | 型チェック→Lint→整形検査→テスト→ビルド。最初の失敗で停止 |

変更ファイルだけの検査を全体の合格にしません。依存不整合なら検証中に自動導入せず、install段階へ戻ります。

## Lintの方針

- TypeScriptは`strictTypeChecked`＋`stylisticTypeChecked`で検査します。非null断定（`value!`）・不要な条件・危険な型操作などを検出し、`import type`の書き方を揃えます。any・Promiseの待ち忘れ検出は維持します。
- 不要になったeslint-disableコメントはerrorです。スタイルの細部はPrettierへ任せ、整形とLintの競合ルールを無効化します。
- Vitestの推奨検査を実行対象のテストに適用し、focused test（.only）・disabled test（.skip等）をerrorにします。.onlyをLintの--fixで勝手に除去する設定にはしません。テストのunsafe検査を一括offにはしません。
- 正規表現は推奨ルールで、重複した選択肢・誤用・不必要な記述等を検査します。
- Nodeで実行するコードは、対象プロジェクトのpackage.jsonのengines.nodeに基づく静的Node API検査を行います。実験的APIは明示的な採用判断なしに許可しません。この検査はpluginの対応表で分かる静的APIに限られ、instance method・追加引数・全optionsの互換性を保証するものではありません。
- libraryの製品srcにはexplicit-module-boundary-typesを適用し、公開関数・メソッドの引数/戻り値の型を明示します。実行対象の併置テストはこの公開APIルールから除外します。

固定plugin版は`@vitest/eslint-plugin 1.6.27`、`eslint-plugin-n 18.4.1`、`eslint-plugin-regexp 3.3.1`です。ルール強化により、以前通っていたコードが不合格になる場合があります。エラーの理由を確認して修正し、検査を一括offにして回避しません。

参考にした実設定:

- [Josh Goldberg / create-typescript-app](https://github.com/JoshuaKGoldberg/create-typescript-app/blob/9bbf2385f495b912b306d66c8d2118ab340e4c4c/eslint.config.ts)
- [typescript-eslint自身の設定](https://github.com/typescript-eslint/typescript-eslint/blob/76786e8adbfe937fb49130d7930d21d5479389d6/eslint.config.mjs)

作者の設定を丸ごと複製したものではなく、公式プリセット/APIと必要なルールを組み合わせ、既存の用途・安全境界へ適合させています。

## 4. 既存Gitフックを確認し、許可後に有効化する

設定コピー・依存導入だけではフックは有効になりません。Git root、既存core.hooksPath、その指すフック、Git共通ディレクトリのhooks、既存.huskyを確認します。

```sh
git rev-parse --show-toplevel
git rev-parse --git-common-dir
git config --show-origin --get core.hooksPath
```

未設定時の最後のexit 1は未設定を表します。.sampleは有効フックではありません。既存フックや別hooksPathがある場合、今回コピーしたもの以外の.huskyがある場合、プロジェクトがGit rootと異なる場合は停止し、統合方針を別途確認します。グローバルフックを変更しません。

条件とプロジェクトローカルGit設定変更の許可が揃った場合だけ、Git rootで実行します。

```sh
pnpm exec husky
```

これはローカルcore.hooksPathを変更し、.husky/_に内部ファイルを生成します。**.husky/_はGitへ追加せず、設定として配布する.husky/pre-commitと.husky/pre-pushはGitで管理します。** husky initによる既存フックの上書きは行いません。

commit前は変更ファイルの整形・Lint、push前はpnpm checkを実行し、不合格なら停止します。有効化後は許可されたローカルGit操作で検証し、設定と結果を読み戻します。テスト目的だけでGitHubへpushしません。

HuskyにはCIと同じ強制力はありません。未設定端末・GitHub上の直接編集・hookスキップでは保証できません。不合格をスキップで回避せず、実行結果と有効化状態を記録します。

## 公式資料

- https://www.typescriptlang.org/tsconfig/
- https://typescript-eslint.io/getting-started/typed-linting
- https://typicode.github.io/husky/how-to.html
- https://pnpm.io/settings/build
- https://pnpm.io/settings/dependency-resolution
