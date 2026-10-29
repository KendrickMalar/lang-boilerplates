# 全言語 Husky 統一の検証記録

> 作成日・最終更新：2026-10-28。対象：main `be210c7` からの変更。
> 目的：全言語で commit / push 前の全体検査を行う設定を配布します。

## 1．結論

全言語のフックを Husky に統一しました。実 Git・実 Husky による拒否動作、既存 TypeScript の回帰、生成設定の検査が合格しました。
各言語の実アプリ・実機の動作まで合格したという記録ではありません。

## 2．決定事項

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| 配置 | **Git root に Husky 1つ** | 複数言語は root の check に集約します |
| commit / push | **テストを含む全体検査** | 失敗なら commit / push を拒否します |
| 有効化 | **明示実行** | install・コピーで既存 hooksPath を変えません |
| 既存環境 | **変更しません** | 既存プロジェクトの移行・CI追加は対象外です |

pnpm 12.6.0 は子へ `pnpm_config_verify_deps_before_run=false` を渡すため、フックの pnpm 子環境で `error` を指定します。
単独 Node 実行では通る検証が pnpm 経由では失敗したことから再現・修正しました。
Roblox の既存 guard は維持し、必須追跡対象を Husky・Node の入力へ更新しました。
別プロジェクトのフックを呼んだときは、対象 root の不一致で拒否します。

## 3．検証結果

環境：macOS Apple Silicon、Node 26.10.0、pnpm 12.6.0、Husky 9.1.7。

| 検証 | 出力 | 終了コード |
| --- | --- | --- |
| `PLAYWRIGHT_BROWSERS_PATH=... pnpm test` | static 6件、integration **108 passed / 0 failed / 0 skipped** | 0 |
| `pnpm test:native:static` | **Ran 35 tests / OK** | 0 |
| `LUNE_BIN=... pnpm test:husky:luau` | **Ran 1 test / OK**。6種の必須入力の追跡漏れを拒否 | 0 |
| Lune 0.10.5 の `scripts/test-helpers.luau` | **helper tests: 10 passed** | 0 |
| StyLua 2.5.2 の guard 書式検査 | 違反なし | 0 |
| 変更した JS の Prettier 検査 | **All matched files use Prettier code style!** | 0 |
| `git diff --check` | 違反なし | 0 |

integration に含まれる Husky 16件は、正常系、各 native leaf の不正 commit / push、HEAD / remote ref 不変、
未stage・未追跡・隠すindex flag・検査中変更、複数言語、stdin引継ぎ、global bridge・linked worktree、
foreign hook、依存不整合時の非0とlock不変を検証しています。
コンパイラ・native test command はこの16件では代替し、Git・Husky・pnpm は実物を使います。

最終の全体実行以前に、pnpm の親環境による依存検査無効化と、ディスク容量不足による中断がありました。
両方を切り分け、容量回復後の全体再実行で上記の合格結果を取得しました。

## 4．未検証・制約

- Swift/Xcode、Rust/Tauri、Godot、Blender、Roblox Studio の製品全体の実 build / test は、この変更では再実行していません。
- Node の全対応版・Windows/Linux の実行結果ではありません。
- 独立担当によるコードレビューと、新規実モデルによる scaffold 手順遵守評価は未実施です。差分の自己レビューを行っています。
- ローカルフックは利用者の明示スキップや未導入端末を強制的に防げません。GitHub 必須チェックは追加していません。

## 5．関連資料

- 各言語・用途の README がコピー・統合・有効化の手順の正本です。
- scaffold-profiles の `src/profile/skills/scaffold/references/basic-design.md` と `implementation.md` も対応する変更を行っています。
