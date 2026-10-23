# RobloxのLuau品質ゲート検証

> 対象はApple Silicon macOSです。private CLIのv0.1.0を固定しました。各種全競合・実ゲームの精度・他OSを保証するものではありません。

## 1．結果

| 論点         | 判定 | 根拠                                                                                  |
| ------------ | ---- | ------------------------------------------------------------------------------------- |
| 単独コピー   | 確認 | catalogの全file一覧・READMEリンク照合                                                 |
| 固定CLI      | 確認 | ReleaseRecordからversion／tag／asset／archive・binary SHA／source commitを固定        |
| 明示setup    | 確認 | 実private Release取得と全段階check。既存gh設定・既存Lune HOME不変                     |
| 検査中の取得 | なし | verifyはlocal照合のみ。setupだけprivate取得。従来の固定Roblox型定義取得は別途維持     |
| commit／push | 確認 | 全6段階。失敗時HEAD／remote ref不変、sourceやindexの自動復元なし                      |
| Node回帰     | 確認 | static 6、integration 92、失敗0                                                       |
| native保守   | 確認 | 60 unittest、skipなし、失敗0。parameterケースは別件数へ水増ししません                 |
| Lune helper  | 確認 | format／Selene／strict standard-platform解析／純粋unit 10判定。hookを再帰実行しません |

## 2．失敗から確認したこと

- 未実装verify／setupからREDを確認し、実binaryの照合、改変・版・権限・source0の拒否をGREENにしました。
- Lune 0.10.5のfs.metadataはsymlinkを追います。実fixtureで見つけ、OS標準の非追従判定を先に置きました。
- 旧pre-commitはformat／lintだけでした。全段階実行・隠すindex flag拒否のREDから変更しました。
- 他projectのhookを呼ぶとcwd側を検査してしまうREDを確認し、hook自身とGit rootの一致を必須にしました。
- helperの型違反を旧typecheckが見落とすREDを確認しました。runtime spec loaderだけ動的require境界を明示し、runtimeの値検証は維持しています。
- source／indexを検査中に変更するstub、型／test／build／類似clone、別commit push、assume-unchanged／skip-worktree、未stage／未追跡を実Gitで拒否しました。
- 実global dispatcherのbytesを試験用HOMEへコピーし、common Git directoryのbridge経由でlinked worktreeのcommit／local bare pushを確認しました。元global hook／設定／core.bareは変更しません。
- setupの認証不足・archive hash違い・既存未知directoryは失敗し、部分成果を保全しました。tokenを出すprocess stubでも親の出力にtokenを出しません。

## 3．実導入と回帰の境界

実setup試験は既存gh認証を利用します。隔離HOMEだけでは既存認証が解決せず停止することを確認しました。
型生成は常に所有領域の専用HOME/cwdです。認証先切替・token抽出・設定コピーによる回避は行いません。

新worktreeのTypeScript回帰では、既存similarity-ts 0.5.0とPlaywrightの固定browser cacheが不足しました。
既存の承認済みコピーから版・bytes一致を照合して複製しました。新しい版の導入・取得・検査弱化は行いません。

Python active LSPは4 fileで診断なし、共有test_hooks.pyにSwift側の既存platform型診断1件です。
該当Swift処理は今回変更していません。native／Node試験の成功を、全LSP診断解消の主張にはしません。

## 4．証拠

追跡外 `.verification/` 内：

- `roblox-baseline.log`、`similarity-red.log`、`setup-red.log`、`helper-types-red.log`、`git-guard-red.log`、`hook-root-red.log`、`preflight-red.log`。
- `roblox-accepted.log`、`typescript-regression.log`、`global-linked.log`、`git-blackbox.log`。
- `actual-private-setup.json`、`actual-authenticated-setup.log`、`reused-browser-cache.json`。

## 5．残る空白

- Windows／Linux、Studio実同期、Wally registry実取得は未検証です。
- 更新なしpushは空stdinとして停止する場合があります。tracked symlink／submoduleは未対応です。
- 前後のbyte照合であり、全瞬間を監視する仕組みではありません。
- private CLIは意味同値判定ではありません。実ゲーム全体の検出精度は未検証です。
- Scaffold組込みと最終独立レビューは別工程です。main統合／GitHub pushの許可にはなりません。
