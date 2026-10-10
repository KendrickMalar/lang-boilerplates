# TypeScript Boilerplates Implementation Plan

> 履歴資料: この文書は初期構成（共通設定＋presets）の記録です。自己完結型への移行後の現在の配置・導入手順は、[TypeScript README](../../../typescript/README.md)と用途別READMEを参照してください。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3用途のTypeScript設定とScaffold向けREADMEを作り、PublicリポジトリとDevelopmentの言語別表を接続します。

**Architecture:** 共通設定と1つのpresetを利用プロジェクトのルートへコピーします。製品srcは配布せず、Nodeのnode:testで一時fixtureを作り、実TypeScript・ESLint・Vitest・Vite・Gitで検証します。READMEを導入手順の正本にします。

**Tech Stack:** pnpm、ESM、TypeScript、ESLint/typescript-eslint、Prettier、Vitest、Husky、lint-staged、Vite、node:test。

**Spec:** `docs/superpowers/specs/2026-10-10-typescript-boilerplates-design.md`（ユーザーレビュー承認済み）

## Global Constraints

- GitHub先はKendrickMalar/lang-boilerplates、Public、MIT。作業はこのリポジトリの専用feature worktree、feat/typescript-configだけです。
- 配布物は設定とREADMEのみ。製品src、サンプルテスト、HTMLエントリはtypescript/へ置きません。
- pnpm 12.6.0、ESM、Node >=24。下限未検証ならその旨を報告します。OSのNode/pnpmは変更しません。
- 初期版: typescript 6.0.3、eslint 10.12.0、@eslint/js 10.0.1、typescript-eslint 8.71.1、globals 17.13.0、prettier 3.9.9、eslint-config-prettier 10.1.8、husky 9.1.7、lint-staged 17.6.0、vitest 5.0.3、vite 8.3.4、tsx 4.23.15、@types/node 24.19.1。
- strict、noUncheckedIndexedAccess、exactOptionalPropertyTypes、verbatimModuleSyntax、forceConsistentCasingInFileNamesを有効にします。targetはES2023です。
- pnpm checkはtypecheck → lint → format:check → test → buildの順で、失敗時に後続を実行しません。
- prepare/postinstallでHuskyを有効化しません。既存ファイル・Gitフックは許可なしに上書きしません。
- 2026-10-10改訂（ユーザー承認済み）: 共通pnpm-workspace.yamlにverifyDepsBeforeRun:error、minimumReleaseAge:1440＋strict、strictDepBuilds:true、esbuild@0.28.2 script不許可を追加します。fixtureは独立node_modulesへ専用storeから実installします。synthetic HOMEのmetadata bootstrapはnetwork取得し、誤ってoffline限定にしません。
- CI、自動コピーCLI、フレームワーク固有設定、CJS二重配布、npm公開は対象外です。
- 依存インストール、GitHub作成・push、main統合、Profile編集はそれぞれ実行直前に確認します。コミットにAI帰属行を付けません。
- synthetic HOME、作業専用pnpm store、Gitローカルbare remoteを使用します。テストfixtureとログは証拠として保持し、無許可で削除しません。

## Review Focus

1. 設定だけをコピーしたプロジェクト: src/テストなしを合格扱いしない（Task 1/2）。
2. コピー後のパス解決: extends/importがコピー元presetの位置に依存しない（Task 1/2）。
3. WebとNode環境の分離: browserコードでNode globalsを、NodeコードでDOM APIを無条件に許容しない（Task 2）。
4. Git hook競合: installによるhooksPath変更や既存グローバルフックの消失を起こさない（Task 3）。
5. library配布物: テストや設定がJS/.d.tsとして混入しない（Task 2）。

---

### Task 1: 共通設定とNode preset

**Files:**
- Create: `.gitignore`, `package.json`, `LICENSE`
- Create: `tests/helpers.mjs`, `tests/common.test.mjs`, `tests/node.test.mjs`
- Create: `typescript/tsconfig.base.json`, `typescript/eslint.base.mjs`, `typescript/.prettierrc.json`, `typescript/.prettierignore`, `typescript/.editorconfig`, `typescript/.gitignore`, `typescript/.node-version`, `typescript/lint-staged.config.mjs`
- Create: `typescript/presets/node/package.json`, `typescript/presets/node/tsconfig.json`, `typescript/presets/node/tsconfig.build.json`, `typescript/presets/node/eslint.config.mjs`, `typescript/presets/node/vitest.config.ts`

**Interfaces:**
- Consumes: Specのファイル配置、依存版、A1〜A4。
- Produces: `copyPreset(name: 'node' | 'web' | 'library') -> Promise<string>`（fixture root）、`runAt(root: string, command: string, args: string[]) -> {status: number, output: string}` をtests/helpers.mjsから提供します。共通ESLintは `createConfig({environment: 'node' | 'browser'})` をexportし、コピー後のeslint.config.mjsから呼びます。
- 共通ファイルはhelpers内で明示列挙し、presetの全ファイルと合わせてfixture rootにコピーします。依存インストールはユーザー承認後だけ実行し、fixtureは承認した検証用領域へ作ります。

- [ ] Step 1: common.testでstrict各フラグ・固定依存版・check順序・prepare/postinstall不在をassertします。node.testでNode fixtureのpnpm check exit 0、実dist/index.js起動成功、型不一致・undefined未考慮・optional誤代入・any・floating Promise・整形違反・失敗テスト・テスト欠落のexit非0をassertします。fixtureはsrc/index.tsとtests/index.test.ts、設定のみを生成します。
- [ ] Step 2: `node --test tests/common.test.mjs` を実行し、配布設定不在のassert失敗を記録します。構文エラーでなく設定欠落が理由であることを確認します。
- [ ] Step 3: 設定とpackage.jsonを実装します。NodeのlibはES2023、module/moduleResolutionはNodeNext、typesはnode。tsconfig.jsonはnoEmitでsrc/tests/vitest.config.tsをinclude、buildはsrcだけをincludeしてrootDir src/outDir dist/noEmit falseとします。ESLintの.mjs設定はNode globals＋型情報なし、TSはprojectService＋recommendedTypeChecked、no-explicit-any/no-floating-promises errorとします。
- [ ] Step 4: ルート維持用package.jsonに検証依存と `test:static`、`test:integration`、`test` を配置します。fixture生成はここからコピーする設定を使い、テストに期待設定そのものを埋め込んで代用しません。インストール前に対象依存・store・native optional依存の影響を示して承認を得ます。
- [ ] Step 5: `pnpm test:static` とNode integrationを実行し、正常系・異常系の実出力とexitを記録します。Node24が既存環境にない場合、隔離領域へのランタイム導入を別途確認し、Node24/26の両方で検証します。インストールのpeer/native依存問題は隠さず解決・記録します。
- [ ] Step 6: 差分と結果を確認し、`feat: add common TypeScript and Node configuration` でコミットします。

### Task 2: Web・library preset

**Files:**
- Create: `tests/web.test.mjs`, `tests/library.test.mjs`
- Create: 各 `typescript/presets/{web,library}/{package.json,tsconfig.json,eslint.config.mjs,vitest.config.ts}`
- Create: `typescript/presets/web/vite.config.ts`, `typescript/presets/library/tsconfig.build.json`

**Interfaces:**
- Consumes: Task 1のhelpers、createConfig、共通設定・scripts。
- Produces: 3presetで同一のコピー契約。各presetのpackage.jsonはprivate:true、libraryにはmain/types/exports/filesを追加します。

- [ ] Step 1: web.testでHTMLエントリ付きfixtureのcheck exit 0、dist/index.html存在、browser globals許可とprocessの拒否をassertします。library.testでcheck exit 0、dist/index.js/.d.ts存在、dist内testsと設定ファイル不在、package main/types/exports先の実在をassertします。Node fixtureではdocumentの型検査拒否もassertします。
- [ ] Step 2: 新テストを実行し、preset欠落のassert失敗を記録します。
- [ ] Step 3: Webはmodule ESNext/moduleResolution Bundler/lib ES2023+DOM+DOM.Iterable/types vite/clientを使用し、Viteビルドを設定します。testsとVite/Vitest設定にはNode型を使えるようtsconfig/ESLintの対象を明示し、製品srcにNode globalsを付与しません。TSの型境界に追加tsconfigが必要ならpreset内へ追加し、READMEコピー表とfixture helperも整合します。
- [ ] Step 4: libraryはNode設定からdev用途を除き、declarationを有効にしたsrc-onlyビルドとdist配布メタデータを実装します。テストをdistへ出力しません。packageのpublishを自動実行するscriptを追加しません。
- [ ] Step 5: 3presetのintegrationとstatic suiteを実行します。設定ファイルの型チェック・Lintにエラーがないことも実出力で確認します。
- [ ] Step 6: `feat: add web and library TypeScript presets` でコミットします。

### Task 3: GitフックとREADME入口

**Files:**
- Create: `typescript/.husky/pre-commit`, `typescript/.husky/pre-push`
- Create: `README.md`, `typescript/README.md`, `tests/hooks.test.mjs`, `tests/readme.test.mjs`

**Interfaces:**
- Consumes: Task 1/2の共通コピー一覧・3preset・scripts、Spec A6〜A8。
- Produces: READMEに用途選択、全相対パスとコピー先、利用側が用意するsrc/テスト/HTML、既存設定とhooksの停止条件、有効化・検証手順、Huskyの限界を明記します。フックはPOSIX shellです。

- [ ] Step 1: readme.testはREADMEの参照先の実在と、配布ファイル集合に製品src/サンプルテスト/HTML/.husky/_がないことをassertします。hooks.testはsynthetic HOMEでcommit成功、lint違反commit非0、push成功、型エラーpush非0かつbare remote ref不変をassertします。
- [ ] Step 2: README/フック欠落のREDを記録します。実ユーザーHOME・グローバルhooksPath・.git-hooksファイルハッシュのbaselineを読み取り専用で取得します。
- [ ] Step 3: READMEとhooksを実装します。Husky手動有効化前に既存core.hooksPath/フック/.husky/Git rootを確認する手順を先に置きます。利用者の既存ファイルに対する無条件cp、husky initによる上書き、フック回避を推奨しません。
- [ ] Step 4: fixtureで `pnpm install --ignore-scripts` を実行しhooksPath不変をassertします。Husky有効化はfixtureだけで行い、実Git commitとローカルbare remoteへのpushでフックを検証します。外部pushや実ユーザーGit設定の変更をしません。
- [ ] Step 5: `pnpm test` を実行し、全合格とglobal hook baseline不変を確認します。最終差分は独立reviewerが読み取り専用で確認し、重要な指摘には回帰検証を追加します。
- [ ] Step 6: `docs: document Scaffold entry and local verification hooks` でコミットします。

### Task 4: 公開とDevelopmentのREADMEリンク

**Files:**
- Modify: `~/.pi/agent/profiles/development/skills/scaffold/references/basic-design.md` のTypeScriptテーブル行のみ。
- Create: 必要な検証・公開記録（機密情報を含めない）。

**Interfaces:**
- Consumes: Task 3で合格した不変commit、独立レビュー結果。
- Produces: Public main上のREADMEとDevelopmentの1行リンク。URLは `https://github.com/KendrickMalar/lang-boilerplates/blob/main/typescript/README.md`。

- [ ] Step 1: 同名GitHub repoが依然存在しないか読み直し、公開対象ファイルを秘密情報・fixture/ログ混入について検査します。最終test出力・差分を提示します。
- [ ] Step 2: root初期mainがunbornなので、承認したfeature commitからmainを初期化する方針を明示します。既存mainの上書きやforceは行いません。GitHub Public作成・このcommitのmain pushについて対象と影響を示し承認を得ます。
- [ ] Step 3: 承認された操作だけでmainとGitHub repositoryを作成し、通常pushします。失敗・成否不明は確認前に再送しません。main上READMEとvisibility/licenseを読み戻します。
- [ ] Step 4: Profile表の1行更新について確認し、バックアップ後に〇〇をMarkdownリンクへ置換します。変更行以外のbytes不変とURL到達を検証します。
- [ ] Step 5: 必須未完了があれば、既存Issueを検索したうえでIssue案を準備し、投稿許可前には作成しません。worktree・fixture・証拠は無許可で削除しません。

## 実行ハンドオフ

設計文書・本計画をユーザーがレビューし、Native（親が直接実装し最後に独立レビュー）かSubagent-drivenを選んでから設定実装を開始します。依存導入・公開・Profile編集の確認は、この計画の承認で省略しません。
