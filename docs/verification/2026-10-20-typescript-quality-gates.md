# TypeScript 品質ゲートの検証記録

> 作成日・最終更新：2026-10-20。出所：固定版の公式ソース、実CLI、隔離Git試験、独立レビュー。
> 目的：新規TypeScriptプロジェクトで、保守性の検査に不合格なら通常のcommitを停止する設定を確認します。

## 目次

1. 結論
2. 決定事項
3. 実行結果
4. レビュー対応と判断
5. 検証できたこと・未検証のこと
6. 次のアクション・残る空白
7. 出典・決定ログ

# 1．結論

全4用途で、複雑度・関数長・ネスト・重複率・構造的類似度を検査する設定を追加しました。commit前は変更ファイルだけでなく全体のcheckを実行します。GitHub側CI、既存プロジェクトへの適用、この設定集自身のフック有効化は対象外です。

【確度：高】下記の実行結果がある範囲に限った判定です。稼働中のScaffold Profileへの反映や、全OSの動作を示すものではありません。

# 2．決定事項

| 論点         | 決定                              | 理由・補足                                                                        |
| ------------ | --------------------------------- | --------------------------------------------------------------------------------- |
| 循環複雑度   | **10まで**                        | ESLint classic。製品srcとテストに適用します。                                     |
| 関数の長さ   | **50行まで**                      | 空行・コメントを除外し、IIFEも検査します。                                        |
| ネスト       | **3段まで**                       | ESLintのmax-depthです。                                                           |
| コード重複   | **jscpd 5.4.1、重複率0%**         | 5行以上かつ50トークン以上。製品srcのみです。                                      |
| 構造的類似度 | **similarity-ts 0.5.0を併用**     | 90%以上、ASTノード50以上の関数。型比較とfast pre-filterはoffです。                |
| 解析失敗     | **oxc-parser 0.73.2で事前解析**   | 固定ReleaseのCargo.lockと同版。CLI内の黙示的なparse error skipを補います。        |
| toolの導入   | **プロジェクト内へ明示導入**      | 版・OS/CPU・SHA-256を確認します。グローバル導入やcommit時ダウンロードはしません。 |
| commit前     | **pnpm check全体を要求**          | 型→Lint→重複→類似度→書式→単体→build。3Dは本番build＋E2Eも含みます。               |
| stageの整合  | **不一致・隠すindexフラグを拒否** | 自動stash・整形・stage・フラグ解除はしません。                                    |
| globalフック | **既存dispatcherを保持**          | local hooksPathで隠さず、現在のworktreeの.huskyへ委譲します。                     |

# 3．実行結果

実環境はmacOS ARM64、Node v26.10.0、pnpm 12.6.0です。検証用Chromiumは専用保存先を使い、本人のChromeプロファイルは使っていません。

## lang-boilerplates

実行：`pnpm test`。最終ログ：`.verification/logs/accepted-full-suite.log`。

```text
# test:static
ℹ tests 6
ℹ pass 6
ℹ fail 0
ℹ skipped 0

# test:integration
ℹ tests 92
ℹ pass 92
ℹ fail 0
ℹ skipped 0
```

Prettierは変更した設定・JS/TS・README・テスト・計画を検査し、`All matched files use Prettier code style!`でした。pnpm-lock.yamlはpnpmの生成書式を保持しました。整形前後の全YAMLドキュメントを比較して内容不変を確認し、`pnpm install --lockfile-only --ignore-scripts --frozen-lockfile`もexit 0でした。既存のpackage-manager設定部分は元のbytesへ戻し、lock差分は新依存の追加310行だけです。

実Git試験には、正常commit、型・Lint・書式・テスト・類似クローンによるcommit拒否、HEAD不変、未stage・未追跡の拒否、検査中の作業内容/index変更、隠すindexフラグの拒否を含めています。global dispatcherのbytesと設定を保ち、local hooksPathを追加しない経路を全4用途で検証しました。別worktreeとローカルbare remoteも使用し、GitHubへの試験pushはしていません。

3D用途は実WebGLの画素、Rapier WASM、接触、入力、resize、開発サーバーと本番preview、失敗時の不合格を含みます。検証用の長い関数は分割し、Lint上限は緩めていません。

## scaffold-profiles

実行：`npm run generate`、`npm run check`、`npm run typecheck`、`npm test`。
ログ：lang-boilerplates側の`.verification/logs/scaffold-repaired.log`と、実pre-commit経由の` .verification/logs/scaffold-commit.log`。

```text
ok: 35 files
ℹ tests 115
ℹ pass 115
ℹ fail 0
ℹ skipped 0
```

原本からPi/Claude両方のdistを生成しました。文書内の実shell snippetを実行し、pre-commit欠落・pre-push欠落では共有wrapperを設置せず失敗、両方がある場合だけ設置することを検証しました。

LSPの能動照会は5ファイルすべてinconclusiveでした。診断0件をcleanの証拠にはしていません。実型検査・Lint・統合テストの結果を判断根拠にしています。

# 4．レビュー対応と判断

別コンテキストのruntime reviewerとcontracts/tests reviewerが読み取り専用で確認しました。修正は親が行い、再現テストのRED→GREENと全suiteの再実行で検証しました。

| 指摘                                                     | 判断・対応                                                                                                                                                                                                                                                                                                                                                          | 判断が誤っていた場合の影響                                          |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| assume-unchanged/skip-worktreeで作業内容の不一致が隠れる | **修正**。indexフラグを前後で確認して拒否します。2種類とも修正前に不正commitが通り、修正後は拒否・HEAD不変を確認しました。                                                                                                                                                                                                                                          | 未検査のstage済み内容がcommitされます。                             |
| jscpdの既定1 MiB上限で大きなファイルが黙って除外される   | **修正**。製品ファイルを明示列挙し、実際の最大サイズをCLIへ渡します。新しいサイズ制限を勝手に設けず、1 MiB超の実ファイル2つで重複拒否を確認しました。                                                                                                                                                                                                               | 大きな製品コードの重複を見逃します。                                |
| .mts/.ctsの検査範囲が不一致                              | **重要と再判定して修正**。型・Lint・重複・単体探索・libraryの配布除外を揃えました。全4用途で.mts/.ctsを含む複雑度/長さ/深さの境界を、Node用途で両拡張子の実重複検出を確認しました。                                                                                                                                                                                 | TypeScriptモジュールの一部だけ検査を逃れます。                      |
| Scaffoldのtest A && test BがA欠落時にset -eで停止しない  | **重要と再判定して修正**。個別のtestへ分けました。実snippetの欠落ケースがRED→GREENです。                                                                                                                                                                                                                                                                            | 存在しないフックへの共有wrapperを設置し、他worktreeにも影響します。 |
| src自体がsymlinkの場合の検査                             | **追加で修正**。rootと入れ子のsource symlinkを拒否します。root symlinkの試験をRED→GREENとし、修正後は両scannerの拒否を確認しました。                                                                                                                                                                                                                                | 指定範囲外のsourceを検査し、有効範囲を誤認します。                  |
| Git hookから試験用GitへGIT_DIR等が漏れる                 | **修正・復元**。通常実行では合格していた試験が、実pre-commitでは元repoを参照し、core.bareをtrueに変えていました。本人の明示承認後、現在configを非公開で退避し、bareだけfalseへ復元しました。その他のbytes不変、mainのHEADと追跡ファイル不変を確認。新規テストでGIT_*を除去し、poisoned環境でRED→GREEN、実pre-commit経由でも115/115とcore.bare=falseを確認しました。 | 試験が利用者のGitメタデータを変更します。                           |

# 5．検証できたこと・未検証のこと

| 判定             | 状態                                                                                                             |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| できていること   | macOS ARM64・Node26の全4用途、実commit/push、実ブラウザ、手順書の生成とshell試験。                               |
| できていないこと | Linux/Windows/Intel Mac、Cargoでのビルド導入、Node24での再試験、Scaffoldの実AIによる新repo作成からの全工程試験。 |
| 反映状況         | 専用の2つの作業ブランチ。mainへのmerge/push、稼働Profileへの反映はこの記録の作成時点では未実施です。             |

> 判定：検証済み環境では合格です。未検証OSや、文書生成だけを実Scaffold全工程の合格とは扱いません。

# 6．次のアクション・残る空白

- [x] 2026-10-20：全体検査とレビュー指摘の再現・修正・再検証。
- [ ] mainへ統合するか、PRにするか、作業ブランチで保持するかを本人が選択。
- [ ] 必要なら稼働Scaffold Profileへの反映後に、新規repo setupの実AI試験。

**後回し（2026-10-20、Minor C2）**：重複の5行/50トークンと類似度90%付近を厳密に挟む専用fixtureの追加です。現設定は読んで確認し、実重複・96.15%の構造クローン・除外・異常系は検証していますが、今後の小さな閾値変更への回帰保護には追加の余地があります。

| リスク                       | 扱い                                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------- |
| ローカルフックの未導入・skip | 強制的には防げません。GitHub側CI・必須チェックは別の要件です。                              |
| 構造的類似が誤検出になる     | 処理の同一性・共通化すべきことの証明ではありません。必要性を調べず検査を一括offにしません。 |
| 解析器が新構文に未対応       | 黙って除外せずエラーで停止します。tool更新を別途検証します。                                |
| sparse checkout              | skip-worktreeを拒否するため、このcommitゲートでは未対応です。                               |

# 7．出典・決定ログ

- [ESLint complexity](https://eslint.org/docs/latest/rules/complexity)、[max-lines-per-function](https://eslint.org/docs/latest/rules/max-lines-per-function)、[max-depth](https://eslint.org/docs/latest/rules/max-depth)
- [similarity-ts v0.5.0](https://github.com/mizchi/similarity/tree/v0.5.0)、[固定版Cargo.lock](https://github.com/mizchi/similarity/blob/v0.5.0/Cargo.lock)
- [jscpd configuration](https://jscpd.dev/getting-started/configuration)。実固定版CLIのhelp/debugと実ファイル試験も照合しました。
- [実装計画](../superpowers/plans/2026-10-20-typescript-quality-gates.md)
- 独立レビュー原文：`.verification/review/runtime.md`、`.verification/review/contracts.md`。
- 2026-10-20：本人が上限・commit全体検査・Scaffold手順更新を承認。後にjscpdとsimilarity-tsの併用、固定版・ローカル導入・事前解析を追加承認。
- 作業途中に相対パスの編集先とworktreeの不一致を検出しました。元の作業ツリーへ入った今回の追加だけを元bytes一致で復元し、それ以降は絶対パスを使用しました。mainの追跡ファイル差分はなく、元からあった未追跡ファイルは保持しています。
- core.bare復元前の非公開バックアップ：`.verification/config-repair-MIS3Cw/config.before`。Git hookから渡された環境変数による試験時の漏れを示すREDログ：`.verification/logs/red-git-environment.log`。同じ不正なGIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILEを与えても、修正後の3ケースは成功しました。
