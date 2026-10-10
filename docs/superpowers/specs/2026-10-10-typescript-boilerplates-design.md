# lang-boilerplates TypeScript設定 — 設計

> 作成日・最終更新: 2026-10-10
> 出所: ユーザーとの要件整理、TypeScript・typescript-eslint・Huskyの公式文書、npm registryのパッケージmetadata。
> 目的: Scaffoldが言語別READMEを入口に、用途に合う設定を新規プロジェクトへ安全に導入できるようにします。

## 目次

1. 要約と決定事項
2. 配置とコピー契約
3. 設定・検証コマンド
4. READMEの手順と安全境界
5. 合格基準
6. 次のアクションと残論点
7. 出典

## 1. 要約と決定事項

Developmentの言語別テーブルから `typescript/README.md` へ案内し、READMEに設定ファイルの相対パス・コピー先・導入条件・検証方法を記載します。各プロジェクトは必要な設定をコピーして使い、共有npm設定には依存しません。

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| リポジトリ | **KendrickMalar/lang-boilerplates、Public、MIT** | 今後、複数言語を収容します。最初はTypeScriptだけです。 |
| 配布物 | **設定とREADMEのみ** | 製品のsrc、サンプルテスト、HTMLエントリは配布しません。 |
| 用途 | **Node/CLI、汎用Web、npmライブラリ** | React等のフレームワーク固有設定は対象外です。 |
| 利用方法 | **コピー式** | 共通ファイルと1つのpresetを対象プロジェクトのルートへコピーします。 |
| 標準 | **pnpm 12.6.0、ESM、Node >=24** | packageManagerでpnpmを固定します。Node >=24は下限で、.node-versionは24を指定します。 |
| 品質検査 | **ESLint＋typescript-eslint、Prettier、Vitest** | 型情報Lintと整形を分離します。 |
| 自動検証 | **Huskyによるローカル検証、CIなし** | 強制力の限界と手動有効化の必要性をREADMEに記載します。 |
| Node型定義 | **@types/node 24系** | 最小サポート対象より新しいNode APIを型定義で許容しません。 |
| TypeScript | **6.0.3** | npm latestの7.0.2はtypescript-eslint 8.71.1のpeer要件 >=4.8.4 <6.1.0 を満たさないため採用しません。 |

初期依存は正確な版をpackage.jsonへ記載します。typescript 6.0.3、eslint 10.12.0、@eslint/js 10.0.1、typescript-eslint 8.71.1、globals 17.13.0、prettier 3.9.9、eslint-config-prettier 10.1.8、husky 9.1.7、lint-staged 17.6.0、vitest 5.0.3、vite 8.3.4、tsx 4.23.15、@types/node 24.19.2。用途に不要な直接依存は追加しません。推移依存は利用プロジェクトで生成するpnpm-lock.yamlに固定します。

## 2. 配置とコピー契約

```text
README.md
LICENSE
typescript/
  README.md
  tsconfig.base.json
  eslint.base.mjs
  .prettierrc.json
  .prettierignore
  .editorconfig
  .gitignore
  .node-version
  lint-staged.config.mjs
  .husky/pre-commit
  .husky/pre-push
  presets/
    node/
    web/
    library/
```

各presetは `package.json`、`tsconfig.json`、`eslint.config.mjs`、`vitest.config.ts` を持ちます。Nodeとlibraryには `tsconfig.build.json` を追加します。Webには必要な `vite.config.ts` を追加します。

共通ファイルはtypescript直下から、presetファイルは選択したpresetから、それぞれ対象プロジェクトのルートへコピーします。preset内のtsconfig extendsとESLint importは、コピー後の共通ファイルを参照します。preset単体では実行しません。READMEはコピー対象を省略せず表で列挙し、ドットファイルも含めます。

設定リポジトリの維持用検証は `tests/` とルート `package.json` に置きます。これらは利用プロジェクトへコピーしません。製品コードの代わりとなるfixtureは検証時だけ一時ディレクトリに生成します。

## 3. 設定・検証コマンド

### 共通ルール

- strict、noUncheckedIndexedAccess、exactOptionalPropertyTypes、verbatimModuleSyntax、forceConsistentCasingInFileNamesを有効にします。
- 共通の出力・include・module・libは固定せず、各presetが決めます。共通targetはES2023です。
- ESLintはflat config、typed lintはprojectServiceを使います。TypeScriptソース・テストを対象にrecommendedTypeCheckedとno-explicit-any、no-floating-promisesをerrorで適用します。
- .mjs設定ファイルには型情報Lintを要求せず、Nodeのglobalsを適用します。Webの製品コードはbrowser globals、Node/libraryはnode globalsを適用します。
- テスト・設定ファイルも型チェックします。ビルド出力には製品srcだけを含めます。
- Prettierは2スペース、セミコロンあり、ダブルクォート、trailingComma all、LFを指定します。生成物・lockfile・Husky内部生成物は整形対象外にします。
- lint-stagedでは変更ファイルのPrettier writeとESLintを実行します。tscへ変更ファイル一覧を渡しません。

### 用途別

- Node/CLI: NodeNext、NodeNext解決、Node型定義。型検査はnoEmit、ビルドはtsconfig.build.jsonからsrcをdistへ出力します。開発実行はtsxです。CLIのbinは製品のentry確定後に設定するためテンプレートでは設定しません。
- Web: ESNext、Bundler解決、DOM/DOM.Iterable、Vite client型。型検査はnoEmit、ビルドはViteです。テスト環境はNodeを標準にし、DOM実行テストは利用側の要件で別途追加します。
- Library: NodeNext、NodeNext解決。srcからESM JSと.d.tsをdistへ出力し、main/types/exports/filesはdist/indexに対応させます。初期package.jsonはprivate:trueで誤公開を防ぎます。公開前に製品名、private、license、repository等を利用者が確認します。CJSとの二重配布は対象外です。

### scriptsとhooks

- typecheck: `tsc --noEmit`
- lint: `eslint . --max-warnings 0`
- format: `prettier . --write`
- format:check: `prettier . --check`
- test: `vitest run`（テストなしを成功にしません）
- build: Node/libraryは `tsc -p tsconfig.build.json`、Webは `vite build`
- check: `pnpm typecheck && pnpm lint && pnpm format:check && pnpm test && pnpm build`
- pre-commit: `pnpm exec lint-staged`
- pre-push: `pnpm check`

prepare/postinstallによるHuskyの自動有効化は設定しません。利用プロジェクトのGit設定を確認し、許可後に `pnpm exec husky` を手動で実行します。Huskyの内部生成物 .husky/_ は配布・コミットしません。

## 4. READMEの手順と安全境界

言語別READMEはScaffold担当者向けの実行手順書を兼ねます。以下の順番を明記します。

1. 言語・実行環境・フレームワーク・用途を確認し、1つのpresetを選びます。既存フレームワーク生成物の設定は上書きせず照合します。
2. READMEから列挙した相対パスを読み、コピー先と既存ファイルの有無を確認します。既存ファイルがあれば変更案を提示し、承認まで上書きしません。
3. package.jsonのname等を製品に合わせます。既存package.jsonがある場合は丸ごと交換せず、必要なscriptsとdevDependenciesの差分を確認します。
4. Node・pnpmの対応版を確認し、依存インストールをユーザーの許可範囲で行います。lockfileを生成・保存します。インストールだけでフックを変更しません。
5. 利用側がsrc、テスト、WebならHTMLエントリを用意し、pnpm checkを実行します。設定のみをコピーした直後は製品の検証合格とは扱いません。
6. `git config --show-origin --get core.hooksPath`、既存フック、既存.husky、Git rootを確認します。既存フックがある場合やプロジェクトがGit rootと異なる場合は停止し、統合方針と承認を別途得ます。グローバルフックは変更しません。
7. 新規のGit root・既存フックなし・明示許可ありの条件が揃えばHuskyを有効化し、実Git操作で検証します。

Huskyは未設定端末、--no-verify、HUSKY=0、GitHub上の編集を強制できません。READMEの限界説明は回避操作の推奨ではありません。既存.huskyやcore.hooksPathの統合、自動コピーCLI、CI、他言語、npm公開、OSや認証設定の変更は今回の範囲外です。

Developmentの `skills/scaffold/references/basic-design.md` のTypeScript行だけを、公開後に次のリンクへ変更します。他の工程文書・共通ルールは変更しません。

`https://github.com/KendrickMalar/lang-boilerplates/blob/main/typescript/README.md`

## 5. 合格基準

- A1: 3presetのコピー先で設定の相対参照がすべて解決し、fixtureのpnpm checkが終了コード0になる。
- A2: 型不一致、配列アクセスのundefined無視、省略可能プロパティへの不適切なundefined代入はtypecheckが非0で拒否する。
- A3: explicit anyと待ち忘れPromiseはlintが非0で拒否する。
- A4: 整形違反、テスト失敗、テスト欠落はそれぞれ対応検査が非0で拒否する。checkは先行検査の失敗で停止する。
- A5: libraryのdistに製品JSと.d.tsが存在し、テスト・設定ファイルは存在しない。Node出力は実Nodeから起動でき、WebはHTMLエントリ付きfixtureをビルドできる。
- A6: synthetic HOMEのローカルGitとbare remoteでpre-commit/pre-pushを検証し、不合格pushはremote refを更新しない。外部GitHubへ試験pushしない。
- A7: pnpm installだけではcore.hooksPathが変化しない。利用者のHOME、グローバルhooksPathとフックbytesは検証前後で不変。
- A8: READMEの参照ファイルはすべて存在する。配布対象に製品src、サンプルテスト、node_modules、.husky/_、秘密情報が含まれない。
- A9: Public GitHubのmain上のREADMEを読み戻してからDevelopment表を1行更新し、他行不変を検証する。

## 6. 次のアクションと残論点

| 項目 | 状態 |
| --- | --- |
| 会話での要件・構成・MITの確認 | 確認済み |
| 保存済み設計文書のレビュー | これからユーザーが確認します |
| 詳細実装計画、実装、独立レビュー | 未実施 |
| インストール、GitHub作成・push、main統合、Profile表更新 | 実行直前の対象別承認が必要です |

- [ ] 設計文書をレビューし、実装計画を作ります。
- [ ] feature worktreeで検証を先に作り、設定を実装します。
- [ ] 実出力と差分で受け入れを確認します。
- [ ] 対象別承認後に公開・Profileリンク更新を行います。

リスク: ツールの最新版同士が互換とは限りません。固定した版とpeer要件を照合し、更新時はfixtureを再検証します。Node24下限の検証環境がない場合はNode26検証だけでNode24合格を宣言せず、不足を報告します。利用プロジェクトのフレームワーク固有設定と既存Gitフックの統合は、その場の別判断として残します。

## 7. 出典

- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/tsconfig/extends.html
- https://typescript-eslint.io/getting-started/typed-linting
- https://typicode.github.io/husky/get-started.html
- https://typicode.github.io/husky/how-to.html
- https://pnpm.io/package_json
- https://registry.npmjs.org/ （2026-10-10にversion、engines、peerDependenciesを照合）
