# TypeScript quality gates implementation plan

**Goal:** 新規TypeScriptプロジェクトで保守性の上限とcommit前の全体検査を適用する。
**Spec:** この会話で承認された設計。全4用途、Scaffold手順。既存repoへの有効化・GitHub CIは対象外。
**Architecture:** ESLintの3ルールとjscpdを既存checkへ追加。commitゲートはindexと作業内容の不一致を拒否し、全体checkを実行。既存global dispatcherは保持する。
**Tech Stack:** ESLint 10.12.0、typescript-eslint 8.71.1、jscpd 5.4.1、Husky 9.1.7、pnpm 12.6.0。

## Constraints

- src/testsの循環複雑度10、関数50行（空行・コメント除外、IIFE含む）、ネスト3。
- src製品コードの5行以上かつ50トークン以上の重複率0%。test/spec/__tests__は除外。
- commit前は型・Lint・重複・書式・単体・build。3Dはbuild＋preview E2Eも実行。
- 未stage変更・ignoreされていない未追跡ファイル・check中のindex変更を拒否。自動stash/format/stageなし。
- 既存global/local hooksを上書きしない。global dispatcher経路はlocal hooksPathを追加しない。
- 各leafは単独コピーで完結。依存安全設定は維持。

## Tasks

1. 保守性: 各leafのeslint.base.mjs/package.json/.jscpd.json/README、root manifest/lock、tests/quality-metrics.test.mjs。
   RED→GREEN: 複雑度10/11、長さ50/51、深度3/4、重複なし/あり、併置テスト除外。設定・生成物はスキャン外。
2. Commit gate: 各leafの.husky/pre-commit/check-commit.mjs/README、tests/commit-gate.test.mjs、既存hook tests。
   RED→GREEN: 正常commit、型/テスト失敗、未stage/未追跡、check中変更で拒否してHEAD/index/作業内容を保持。global連携・worktree・push拒否を実Gitで確認。
3. Scaffold: 別worktreeのsrc/profile/skills/scaffold/references/basic-design.md・implementation.md、generateでdistを更新。
   .husky/.githooks選択、既存global保持、commit全体検査の導入と不正commit拒否をsetup完了条件へ追加。

## Verification

- lang-boilerplates: pnpm test（静的＋統合、3Dの実WebGL/WASM/E2E含む）、変更ファイルのPrettier、git diff --check。
- scaffold-profiles: npm run generate、npm run check、npm run typecheck、npm test。
- 独立review後に必要な修正と再検証。mainへのmerge/push・Profile導入は未承認のため行わない。

## Review focus

- 部分stageで未検査内容がcommitされないこと。
- checkがindexまたは追跡ファイルを書き換えた場合の拒否。
- global hooks不変と、別worktreeがそのworktree自身の.huskyを使うこと。
- テスト・generated outputの重複除外、製品コード重複の拒否。
- ブラウザ未導入・テスト0件・失敗したbuild/E2Eを合格にしないこと。

## 追加承認: similarity-ts併用

- similarity-ts 0.5.0、関数類似度90%以上／ASTノード50以上。型の比較とfast prefilterはoff。jscpdの重複率0%は維持。
- oxc-parser 0.73.2を固定し、CLIの黙示的な解析失敗skipを事前構文検査で防ぐ。
- check-similarity.mjsで実行root、版、対象列挙、対象0件、起動・stderr・終了・タイムアウトを検証。対象は製品src、test/spec/__tests__を除外。
- .tools/similarityへ明示導入。macOS ARM64公式archiveのSHA-256 d5a6abcf915b87061857c23a1934883a99b93970a66c627cc8b7f3286c0ba916を照合。グローバル・Rust自体・commit時ダウンロードなし。
- tests/similarity.test.mjsで正常・リネームした構造クローン（jscpd合格／similarity不合格）・未導入・版違い・対象0件・解析不能を検証。commit拒否も実Gitで確認。
- macOS ARM64のみ実検証。Linux配布物・Cargo経路・Windows/Intel Macの動作は未検証として明記。
  未解決事項: なし。
