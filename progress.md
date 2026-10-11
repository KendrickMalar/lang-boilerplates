# Native app settings 実行台帳

## Rust Task 1 — rust-quality

- 実装済み、独立レビュー ok（head `384644f883fad616a6291a8c1bf7ac560560e393`、全体承認ではない）。
- 開始 BASE: `8a41b1ee5219b1bf987b0040541ecff60744eb99`。
- 設定のみの自己完結 leaf、POSIX/PowerShell check、保守用隔離 Cargo fixture を追加。
- TDD: static 設定欠落 RED、check 欠落 RED、自動導入防止の追加 RED → 修正 GREEN。
- macOS: Rust static/runtime 合計9 tests 成功。実 Cargo 正常 fmt/Clippy/test/build 0、異常系は非0。
- 実ログ/版/hash: `.verification/native/rust/logs/`（Git 管理外）。
- Windows/Linux native および PowerShell parser/runtime は未実行。
- Task 2 の Tauri 製品設定/ACL/native frontend 検証は追加していない。
- `pnpm test` は依存検証段階で exit1（test 未起動）。親の指示で正式な全回帰は
  integration-validation へ引き継ぐ。root 依存導入/guard 回避は許可されていない。
- integration-validation の全回帰完了後に固定 whole-branch review artifact を保存し、
  controller が独立レビューする。公開 Task 3/main/push/Profile/CI は未実行。


### Task1 fix round 1

- 未宣言MSRVの条件付き承認に整合: 固定lock/承認集合照合・未知集合/記録不在/lock改変の停止、
  同lockの実build/testと未宣言一覧の証拠紐付けを実装。独立再レビュー待ち。
- 元fixture/共有targetで再testが全ignoredとなったため元失敗証拠を保持。
  原因は共有target再利用の疑い（未断定）。親承認のfixture専用targetで再検証する。
- 既存未所有 `rust/tauri/scripts/check.sh` 整形差分は保持し、この修正commitへ含めない。
- 固定lock（407 packages/106 MSRV未宣言）で専用targetの正常build/test成功、
  Rust static/runtime/承認gateの合計14 tests成功。
- RED/GREEN/固定承認record/実検証証拠: `.verification/native/rust/`（Git管理外）。
- TypeScript正式回帰・Windows/Linux/PowerShell・Task2/全体承認の未実施範囲は変更なし。
- 正式な Task1 fix round 1 独立再レビューは ok、head は上記 `384644f...`。
  review: `<local-review-artifacts>/c0ffa09c-9dde-42f4-8253-e4431934927c/native-app/rust-quality-review-1.json`。

## Rust Task 2 — tauri-boundary

- 実装・macOS 検証済み、独立レビュー ok-with-notes（head `b97d00ae802df54da20a222727c9438825580085`、全体承認ではない）。
- review: `<local-review-artifacts>/c0fe1a16-d04c-4602-be4f-0826dca0a20c/native-app/tauri-boundary-review-0.json`。
- BASE: `384644f883fad616a6291a8c1bf7ac560560e393`。
- build.rs Result/AppManifest 接続箇所、明示 local/main/desktop capability、frontend/CSP 設定候補を追加。
- TDD: 設定欠落・3境界test・baseline復元 helper 欠落 RED → GREEN。
- Rust static/runtime/依存承認gate 合計19 tests 成功。backend と native fixture の
  fmt/Clippy/test/build 成功、mock IPC の app/core 許可・拒否/別window/remote 拒否を実確認。
- 未登録 app command の対照試験は stale 自動permissionを別globで除外し、
  normal→ACL未接続で拒否assert失敗→normal回復を確認（単なる登録空化では旧permissionが残る）。
- 容量不足予防の親承認により class 所有の同一crate path/targetのみ再利用。
  source/config/lock bytes復元と件数・一意log/hashを検査。ignored/failed/invalid→normal回帰成功。
- 実証拠: `.verification/native/rust/task-2/green-all-final.log` と `logs/` の一意JSON/log。
  専用再実行runner: `task-2/run-owned-fixtures.py`。空き約3GiB、追加target作成は禁止のまま。
- leafに生成されたtarget/lock/genとtest pycacheは親承認で保全移動（由来未確定）。
  `task-2/auto-generated-leaf/1791625488502595000/manifest.json` に元path/hash/mtimeを記録。
- UI/WebView/CSP browser/署名・bundle/Windows/Linux/PowerShell は未実行。
- TypeScript全回帰・whole-branch artifactは integration-validation 担当のため未実行。
  全回帰後の固定diff生成・controller独立レビュー・公開Task3/main/push/Profile/CIは未実施。
- Swift追加buildの前に容量問題の解消が必要。既存check.sh整形差分は保持・commit除外。
- 上記容量警告はcleanup前の履歴。親の限定削除承認後に旧compiler成果物23件を削除済み:
  `.verification/native/rust/task-2/capacity-cleanup-1791628826730152000/summary.json`。
  Swift担当開始時の親確認・実測は28GiB。Swift担当による削除/cleanupは実施していない。

## Swift Task 1 — swift-macos

- macOS 品質 leaf と標準 Xcode fixture helper を実装済み、独立レビュー ok-with-notes（head `14dfea93be22c1afae4f45c7fd1670cf0c8684f0`、全体承認ではない）。
- review: `<local-review-artifacts>/a8b8e8e3-0ced-4e13-b045-ce59089fb256/native-app/swift-macos-review-0.json`。
- 開始 BASE: `b97d00ae802df54da20a222727c9438825580085`。
- Swift6 mode/warnings-as-errors/macOS15、Debug/Release、fixture専用VerifyUnsigned、
  formatter/SwiftLint strict/check script、自己完結README/LICENSEを追加。
- static欠落RED(2 failures)、helper欠落RED(8 failures)、package lock guard RED(1 failure) → GREEN。
- macOS static/runtime 合計12 tests成功。正常format/lint/Debug+Release実効settings/
  hosted app test(1 passed)/Release buildはexit0。整形/構文/Lint3規則/actor/失敗testは非0。
  `all` の整形→Lint→test→build順停止、zero/全skip test、tool不在/版/execute権限、
  空source/欠落scheme/project/誤destination/外部path/unsigned誤適用/lock欠落を検査。
- `.verification/native/swift/` にfixture/HOME/DerivedData/package cache/log/xcresultを保存。
  Xcode27.0(27A266a)、Swift6.4、macOS SDK27.0、formatter main、SwiftLint0.65.1。
  同じDEVELOPER_DIRとtool SHA256を各実コマンドのfingerprintへ記録。
- 正常fixtureログのAppIntents metadata未使用警告とlinkd.autoShortcut接続4097は保持。
  compiler警告ではなく、test/buildはexit0。OS設定/署名/Team/証明書は変更していない。
- `pnpm test` は ERR_PNPM_VERIFY_DEPS_BEFORE_RUN / exit1、test未起動。guardは回避しない。
  全TypeScript/Rust回帰と全branch固定diffはintegration-validation担当へ引き継ぐ。
- iOS Task2/Simulator/SwiftPM-only/製品release/archive/全branch承認/公開Task3は未実施。
- 最新容量24GiB（`.verification/native/swift/post-final-capacity.log`）。追加削除なし。
- 既存未所有Rust check.sh整形とtests/native/__pycache__は保持・commit対象外。
- 詳細reportはruntime指定の `native-app/swift-macos-writer.json`（structured acceptance report）。


## Swift Task 2 — swift-ios

- iOS/iPadOS自己完結leaf、標準Xcode fixtureのiOS対応を実装・検証済み、独立レビュー ok-with-notes。
- head: `9a6145306159cb02bb5752d946d2a3607b12f5c0`。review: `<local-review-artifacts>/a8b8e8e3-0ced-4e13-b045-ce59089fb256/native-app/swift-ios-review-0.json`。
- BASE: `14dfea93be22c1afae4f45c7fd1670cf0c8684f0`。全体承認ではない。
- Swift6 mode/warnings-as-errors/iOS17/device family1,2、Debug/Release、fixture専用unsigned。
- static欠落RED(2 failures)、iOS leaf欠落runtime RED(11 errors) → GREEN。
- iPhone17/iOS27.0全11 tests、iPad(A16)/iOS27.0正常app受入れ1 test、static3 tests成功。
  各実app summary: total1/passed1/failed0、UUID/runtime/buildnumberを実結果とassert。
- 専用Simulator UUID: iPhone `3B27929B-88E9-4D7F-B877-476563959C05`、
  iPad `0CD8EEC9-A46A-4515-87F6-2F51F66C8171`（27.0/build24A434）。
  承認範囲内で作成、Xcode testでboot/fixture app配置・起動。既存機は変更せず、削除なし。
- macOS回帰10 tests成功（worktree未所有script版）、さらに固定レビュー済みblobへ
  fixture内だけ差し替えた回帰10 testsも成功。元ファイルの変更/承認はしていない。
- iOSコピー元は上記BASEのmacos leaf、check blob `a330df960e4ae0a9e3f770dd7aaba2e0bdaa6ae4`。
  未所有Rust/macOS check差分・pycacheを保持しcommit除外。
- 最小tool版・実行権限・空source/空test/全skip/lock欠落/未接続quality/誤destination、
  format/Lint/actor/失敗testの非0と後続停止を確認。実ログ/exit/tool版/hash/xcresultを
  `.verification/native/swift/task-2/` と Swift fixture/logs 内へ保存。
- Xcode27.0/27A266a、Swift6.4、iOS Simulator SDK27.0、formatter main、SwiftLint0.65.1。
  署名/OS/global xcode-select/Git hooks/Team/証明書/製品sourceは変更していない。
- pnpm testはERR_PNPM_VERIFY_DEPS_BEFORE_RUN/exit1、tests未起動。回避せず記録。
  承認済みroot依存導入・TypeScript/Rust全回帰・受入れartifact・固定whole-branch diffは
  integration-validation担当。controllerが全branch独立レビューを担当。
- iOS17 runtime・実機・全device/OS・UI flows・製品署名/release/archive・Windows/Linuxは未検証。
  公開Task3/main/push/Profile/CI未実施。詳細reportはruntime指定swift-ios-writer.json。


## Integration Task 1 — catalog-hooks

- 実装・当該検証済み、独立レビュー待ち（全branch/公開承認ではない）。
- BASE: `9a6145306159cb02bb5752d946d2a3607b12f5c0`。
- root→rust/swift→3leaf catalog、全配布ファイル列挙、相対copy/include/script contract、
  optional pre-commit format/pre-push all hooks、明示 native suite と件数guardを追加。
- TDD: 入口/script/hook欠落のstatic 12 failures、runtime hook欠落3 failures、
  count-guard欠落1 failure → static12 tests/実Git native hook3 tests GREEN。
- Rustは親の限定承認で既存 fixture-50ncrnnd/既存専用targetを再利用、新target作成なし。
  Swiftは新規task専用fixtureでmacOS app/iPhone17 iOS27.0 appを実test/build。
- `.verification/native/catalog-hooks/` にexit/log、各Git command/HEAD/bare ref、
  global hooksPath/hash不変、script選択ref/hash、tool fingerprintを保存。
- 正常commit/push成功、整形違反commit非0/HEAD不変、整形済み失敗testはcommit成功・
  push非0/HEAD・bare ref不変、正常復元後push成功。既存global hook fixtureは初回commitを拒否。
- runtimeは NATIVE_HOOK_CHECK_REF=上記BASEで既存未所有Rust/macOS script差分を除外。
  未所有scripts/pycacheは保持・commit除外。通常harnessはworking-treeを検査する。
- 途中の追加test assertionがxcresult JSONの空白表記と不一致で2 failuresとなったが、
  実app成功ログを保持し、空白許容assertへ直して全hook3 testsを再実行成功（166.240s）。
- 既存TypeScript pnpm guard失敗（test未起動）の記録は前taskから参照。親指示で同じ失敗は
  再試行せず、正式frozen導入/全回帰/受入れartifact/固定whole-branch diffは統合担当へ残す。
- iOS failing-test診断収集でsimctl未検出(error72)警告を記録。実testAdditionは期待した失敗、
  正常caseのapp test/buildは成功。warningを隠す環境/OS変更はしていない。
- Windows/Linux/PowerShell/iPad hook/iOS17実runtime/実機/UI/製品署名・公開は未実施。
- 詳細report: runtime指定 `native-app/catalog-hooks-writer.json`。controllerの独立レビュー待ち。

## Integration Task 1 — 正式レビュー結果

- catalog-hooks: 独立レビュー ok-with-notes、head `21a9819f12fc6b2d60c9fa5afa15c3a7977f3145`。
- review: `<local-review-artifacts>/a8b8e8e3-0ced-4e13-b045-ce59089fb256/native-app/catalog-hooks-review-0.json`。
- 上の「独立レビュー待ち」は履歴。全branch/公開承認ではない。

## Integration Task 2 — integration-validation

- 統合検証・受入れartifact生成済み、whole-branch独立レビュー待ち（controller担当）。
- BASE/検証設定ref: `21a9819f12fc6b2d60c9fa5afa15c3a7977f3145`。
- 承認済みroot限定 `pnpm install --frozen-lockfile` 成功。既存lock/直接pin/pnpm guardは不変。
- 正式 `pnpm test`: static5 + integration51、56 tests passed / fail0 / skip0。
- 固定ref native回帰: static12、Rust19、Rust hook1、macOS11、iPhone17 iOS12、iPad(A16)正常app1、計56 cases成功。
- 明示 `pnpm test:native:static` も12 tests成功。runtime suiteは固定ref adapterで既存suiteを実行、Rustは既所有crate/targetを再利用。
- 各正常Swift appは実hosted XCTest total1/passed1/failed0、Release build成功。
- 最小tool版/権限/空source/空test/全ignored・skip/lock欠落/未接続quality/誤destination/unsigned誤適用・各品質異常の非0と後続停止を再確認。
- `.verification/native/integration-validation/parent-acceptance.json`: A1〜A12対応、実command/exit/log/hash、391件の新規実証拠を索引化。
- 実tool: macOS27.0/26A428 arm64、Node26.10.0、pnpm12.6.0、Python3.13.2、Rust/Cargo1.92.0、Xcode27.0/27A266a、Swift6.4、formatter main、SwiftLint0.65.1、SDK27.0。
- 専用Simulatorは既承認iPhone17 `3B27929B-88E9-4D7F-B877-476563959C05` / iPad(A16) `0CD8EEC9-A46A-4515-87F6-2F51F66C8171`、iOS27.0/build24A434。
- 元worktreeの未所有Rust/macOS check.sh差分とpycacheはhash/diff不変。fixture内のみ固定commit blob適用。global hooksPath/hash・xcode-selectも不変。
- 製品設定・test変更/新規TDD実装はなし。既存異常系を実行し、旧タスクRED/GREENをこのtaskの新規実装とは称しない。
- 保留minor: Rust証拠走査範囲肥大、AppIntents/linkdログ、iOS失敗test時simctl診断error72。raw log保存、成功へ隠蔽しない。
- Windows/Linux/PowerShell native、iOS17 runtime/実機/全device、UI/WebView/CSP、SwiftPM、製品署名/archive/配布は未実施。
- 空き約11GiB、cleanupなし。Task3/main/push/Profile/CIは未実施。
- 全回帰後の固定全branch diff: `.verification/native-whole-branch-review.txt`（基準 `8a41b1ee5219b1bf987b0040541ecff60744eb99` → この台帳commit）。
- 詳細report: runtime指定 `native-app/integration-validation-writer.json`。DONEは当該検証・artifact完了だけで、全体承認ではない。

### Integration Task 2 — A8 最終証拠補足

- 自己レビューでRust helperがCARGO_HOME/RUSTUP_HOME/targetを隔離していてもHOMEを継承することを確認。
- task専用adapter内だけでRust subprocess HOMEもfixture/homeへ限定し、Rust19 + hook1を再実行成功。初回ログは`rust-inherited-home-initial.log`/`rust-hook-initial.log`として保持。
- `.verification/native/integration-validation/rust-home-selection.jsonl`に実HOME/cache/targetを記録。製品helperの変更はしていない。
- 最終索引は485件の新規実証拠。前の391件は再実行前の履歴。global Git読み取りは元環境で照合し、不変。

## Whole-branch final fix wave

- BASE: `4cf9e570d6fb57cf5e72e13312a04752febf0699`。accepted P1と同helperのP2のみ修正、独立再レビュー/全体承認待ち。
- P1 HOME: 通常committed `rust_env/run_rust`がfixture/homeをHOME/CFFIXED_USER_HOMEへ指定。cwdなしは専用CACHE/home。Cargo/Rustup/target/offline/auto-install禁止は保持し、global Git読み取り環境は変更なし。
- P2 証拠肥大: src-tauriの任意拡張子・任意nested source/config/lockとroot tool設定/.cargo/scripts/hooks/distをhash。target/gen/cache/.cache/.git/home等は走査前に除外。旧巨大証拠は削除/縮小/上書きしていない。
- RED: `python3 -m unittest -v tests.native.test_rust.RustEnvironmentEvidenceTests` が3 failures/exit1（親HOME継承、cwdなしHOME継承、cache hash混入・root設定未記録）。GREEN:同3 tests成功、通常helperによる実subprocessが隔離HOMEにだけmarkerを書き、実環境receiptへ記録。
- 新adapterはscript固定blob/既所有Rust fixture-path/target再利用だけで、HOME monkeypatchなし。新証拠は `.verification/native/final-fix-wave/`、旧integration結果を保持。
- 全回帰: 正式pnpm test56（fail0/skip0）、pnpm native static12、固定native static12/Rust22/hook1/macOS11/iPhone12/iPad1、計59 cases成功。変更しないSwiftも今回実再実行。各command/exit/logとsource/adapter/script hashを新parent-acceptanceへ記録。
- P2 AppIntents/linkd: 既知unsigned fixture診断として保留。正常hosted app total1/passed1/failed0とRelease成功は確認したが、AppIntents登録/UI成功は保証しない。raw保存、抑制/署名/OS/製品設定変更なし。
- P2 simctl72: 読み取り調査で明示DEVELOPER_DIRのxcrun lookupはexit0、未変更のdefault CLT lookupはexit72。helper/scriptは既にper-command Xcode環境を指定。内部Xcode診断collectorの環境伝搬は未確認で、原因断定/小修正は行わない。
- 今回のiOS失敗testもXCTAssertEqualの意図した失敗/exit65/xcresultを保存しgate停止成立。追加Simulator診断はerror72のため不完全なまま。`simctl-readonly-investigation.log` / `ios-failure-diagnostics-index.log`参照。
- 保全例外: 既存untracked pycacheのrust_helpers通常版/pytest版が変更、test_rust pytest版が新規出現。開始hashと現在bytes/全before-after一覧/時刻を別artifact保存、元bytes未保存で復元不能・発生源未確定。親承認により例外記録で続行、復元/削除/commit混入なし。
- pycache初回mtime21:34:22/44 JSTは開始21:33:38後・正式pnpm回帰前、同pytest版は21:52:42にも更新。workerのnative/probeはPYTHONDONTWRITEBYTECODE=1、正式pnpm testはenv明示なしだが発生源とは断定しない。「pycache不変」「全既存bytes保持」とは宣言しない。
- source/code fingerprint probeでは実loaded rust_env/run_rust/input-hash codeとfresh source compileが一致。これはcode証拠であり、pycache発生源解明や過去全実行の無影響の断定ではない。
- 未所有Rust/macOS check.shのhash/diff、global hooksPath/hook hashes、xcode-selectは独立照合で不変。pycache変更は他の不変項目へ丸めない。
- 空き約7.8GiB、追加target/cleanup/追加依存なし。Windows/Linux/PowerShell/iOS17実runtime/実機/UI/WebView/CSP/SwiftPM/製品署名/archive/配布未実施。main/push/Profile/CI/OS変更なし。
- 新全branch diff: `.verification/native-whole-branch-review-final-fix-wave.txt`（旧artifact保持）。新fix-only review-packageはBASE→fix commitを対象に生成。

### Final fix wave — P2 path境界の追修正

- 初回`eddc0ab`自己レビューで、全階層の名前除外が正当なsrc/cache/mod.rs等を漏らし得ると判明。親承認の同wave追修正。
- 除外は具体的なCargo/Tauri生成先`src-tauri/target`と`src-tauri/gen`だけ。`.git`は全階層metadata除外。root専用HOME/Cargo cache/targetは入力走査rootに含まない。
- cache/.cacheという名前だけでは生成物と断定せずhashする。src/cache・src/nested/target・permissions/gen・scripts/target・.cargo/cache・dist/genの任意inputもhashする。
- `red-path-boundary.log`: nested/root cache入力8件の漏れで1 failure/exit1。`green-path-boundary.log`:3 tests成功。最終affected回帰はRust22/hook1/native static12成功（*-path-final.log/.exit）。
- TS56・macOS11・iPhone12・iPad1はこの同waveの直前実全回帰結果を参照。境界追修正後にこれら未変更platformを再実行したとは称しない。
- pycache例外は継続し、後続mtime/hashも別保全。旧全branch/受入れ/全回帰証拠は保持し、新final受入れ/indexへsource/ref/runの関係を記録。

## Roblox Task — roblox-rojo

- 実装済み（head `725f022`）。BASE: `3b94664`。設計 `docs/superpowers/specs/2026-10-11-roblox-rojo-settings-design.md`、計画 `docs/superpowers/plans/2026-10-11-roblox-rojo-settings.md`。
- `roblox/rojo/` に Rokit 固定の Rojo7.7.1/Wally0.3.2/Selene0.32.0/StyLua2.5.2/luau-lsp1.69.0/Lune0.10.5 設定、check.sh、Lune 最小テスト実行器、任意フックを追加。
- 事前準備（ユーザー承認済み）: Rokit 1.2.0 を `~/.rokit` に導入、6ツールを `rokit install`。Wally 0.3.2 は x86_64 のみのため、ユーザーが Rosetta 2 を導入。
- seed（Git 管理外）: `.verification/native/roblox/seed/`（roblox.yml、型定義 SHA256 一致、facts.md）。
- TDD: static 7件 RED → GREEN、runtime 15件 RED(14) → GREEN、hook 3件 RED → GREEN。
- 結果: native static 19 tests OK、native roblox 16 tests OK（正常 all、整形/Lint/strict 型/失敗 spec/非 table spec/0件/欠落 path/tool 不在/版違い/型定義 SHA 不一致/Packages 欠落/roblox.yml 欠落/空 src/未知 stage、ローカル bare remote への実 commit/push）。
- `pnpm test:native:*` は ERR_PNPM_VERIFY_DEPS_BEFORE_RUN（依存未導入）で起動せず、同一の python コマンドを直接実行。guard は回避していない。`pnpm test`（TypeScript）は未実行。
- 未検証: Roblox Studio 実同期、Windows/Linux、Wally レジストリからの実取得、Rust/Swift runtime suite の再実行。
