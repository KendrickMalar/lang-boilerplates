# Swift App Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** macOS15／iOS17向けにSwift6品質設定と標準Xcode/xcconfig接続を用意し、Mac/Simulator fixtureで検証します。

**Architecture:** swift/macosとswift/iosを1つずつproject rootへコピーします。共通品質は複製して自己完結させ、platform/署名検証設定は分離します。Xcode projectと最小SwiftUI sourceは保守fixtureだけに生成します。

**Tech Stack:** Swift6 mode、SwiftLint0.65.1候補、公式swift-format、Xcode27検証候補、Python3、POSIX shell

**Spec:** `docs/superpowers/specs/2026-10-10-native-app-settings-design.md`（ユーザーレビュー承認済み）

## Global Constraints

- 配布は設定・README・LICENSE・build/check補助だけ。製品source・fixture/cache・画像・証明書・秘密情報を配布しません。
- 各用途を自己完結させ、READMEの相対リンクとコピー先を明示します。親・兄弟設定から補完しません。
- コードは専用feature worktree、1cwdにつきwriter1人。既存main/他worktree/ユーザー変更を上書きしません。
- 依存/tool取得・OS/global設定・署名/公開/main統合・push/Profile更新は実行直前に別承認。Rustupの自動導入を勝手に起動しません。
- fixtureとHOME/cache/target/DerivedDataはtask専用Git管理外領域。無許可で消さず、実出力・版・exitを保存します。
- 検証不合格・未検証をskip/ignore-exit/validation bypassで成功扱いにしません。コミットにAI帰属行を付けません。

- 最小OSはmacOS15／iOS17、iOS/iPad device family1,2。XcodeGen/Tuistは導入しません。
- Swift6 language mode、warnings-as-errors、4スペース・LF。全moduleのdefault isolationをMainActorへ変更しません。
- SwiftLint strict＋empty_count/contains_over_first_not_nil/force_unwrapping。empty sourceを許可せず、force系一括offなし。
- fixtureだけVerifyUnsignedを明示適用。製品署名・Team/証明書/entitlements、release/archive/App Storeは対象外です。

## Review Focus

1. xcconfigは存在してもprojectへ未接続ならSwift6/警告設定が効かない（Task1）。
2. CLTとXcodeのcompiler/formatter/SourceKitを混在させない（Task1）。
3. empty test/skipped testをxcodebuild exit0だけで合格としない（Task1/2）。
4. Simulator SDK/runtime存在をapp test実行と混同しない（Task2）。
5. unsigned検証を製品releaseへ誤適用しない（Task1/2）。

### Task 1: macOS品質設定とXcode fixture

**Files:**
- Create: `swift/README.md`、`swift/macos/README.md`、`swift/macos/LICENSE`、`swift/macos/.swift-format`、`swift/macos/.swiftlint.yml`、`swift/macos/.editorconfig`、`swift/macos/.gitignore`
- Create: `swift/macos/Config/Quality.xcconfig`、`Debug.xcconfig`、`Release.xcconfig`、`VerifyUnsigned.xcconfig`
- Create: `swift/macos/scripts/check.sh`
- Test/Create: `tests/native/swift_helpers.py`、`tests/native/test_static_swift.py`、`tests/native/test_swift_macos.py`

**Interfaces:**
- Produces: `copy_swift_fixture(platform: Literal["macos","ios"]) -> Path`、`make_app_project(root: Path, platform: Literal["macos","ios"], *, connect_quality: bool = True, include_test: bool = True) -> tuple[Path,str]`、`run_swift(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]`（swift_helpers.py）。
- Produces: `scripts/check.sh [format|lint|settings|test|build|all]`。projectは `NATIVE_APP_PROJECT`、schemeは `NATIVE_APP_SCHEME`、source directoryは `NATIVE_APP_SOURCE_DIR`、destinationは `NATIVE_APP_DESTINATION` で明示指定。project root外や欠落を拒否します。
- Tool選択: callerがDEVELOPER_DIR、SWIFTLINT_BINを指定。formatterは同環境のxcrunから解決し、実path/version/hashを記録します。global xcode-selectを変更しません。

- [ ] Step 1: `test_each_leaf_links_and_includes_are_local`、`test_quality_unconnected_rejected`、`test_mode_warning_and_deployment_settings`、`test_clean_macos_app`、`test_bad_format_lint_actor_and_test_rejected`、`test_missing_tool_source_project_scheme_test_rejected` を作り、static欠落のREDを記録します。
- [ ] Step 2: SwiftLint取得asset/version/hash/実行場所、package cache、DerivedData、VerifyUnsigned適用対象を提示して許可を得ます。Xcode selection・署名をglobal変更しません。formatter main表示は安定版保証にせず、known minimal syntax正常/不正の実結果とtool fingerprintを記録します。不整合は相談します。
- [ ] Step 3: Python helperはstandard pbxproj/schemeをfixture内へ生成します。製品project/sourceには触れず、App/AppTestsに最小SwiftUI/XCTestを生成します。target Base ConfigurationにコピーしたConfig/Debug又はReleaseを接続し、SwiftPM-onlyで代用しません。
- [ ] Step 4: QualityにSWIFT_VERSION=6とSWIFT_TREAT_WARNINGS_AS_ERRORS=YES、macOS15を指定。Debugは-Onone/ENABLE_TESTABILITY、Releaseは通常の最適化を選びます。OTHER_SWIFT_FLAGS等を上書きするときは$(inherited)を維持します。Team/bundle/sandbox権限は製品依存とし、汎用setに特定サービス権限を含めません。
- [ ] Step 5: formatter JSONは4スペース/LF/幅100を基準とし、SwiftLint default＋指定opt-in/strict、generated/cacheを除外します。sourceなしをsuccessへしません。formatとLintの競合を正常fixtureで確認し、構文無視/lenient/ignore-exitを入れません。
- [ ] Step 6: settings段階はxcodebuild -showBuildSettingsを読む。mode6・warnings-as-errors・macOS15が不一致なら停止。testでは結果bundleを記録し、選択Xcodeのxcresulttool test-results summaryでtotalTestCount>0/failedTests=0をassertし、0 test・skipだけを合格へしません。
- [ ] Step 7: `python3 -m unittest discover -s tests/native -p 'test_swift_macos.py' -v` を実行。format/lint/actor violation/失敗testの非0と後続停止、正常app test/buildの0を保存します。macOS testで必要なapp起動等の副作用は許可したfixture範囲のみです。
- [ ] Step 8: `feat: add macOS Swift quality settings` でlocal commitします。

### Task 2: iOS/iPadOSの自己完結設定とSimulator実検証

**Files:**
- Create: `swift/ios/README.md`、`LICENSE`、`.swift-format`、`.swiftlint.yml`、`.editorconfig`、`.gitignore`
- Create: `swift/ios/Config/Quality.xcconfig`、`Debug.xcconfig`、`Release.xcconfig`、`VerifyUnsigned.xcconfig`、`swift/ios/scripts/check.sh`
- Test/Create: `tests/native/test_swift_ios.py`
- Modify: `tests/native/swift_helpers.py`、`tests/native/test_static_swift.py`、`swift/README.md`

**Interfaces:**
- Consumes: Task1のcopy/project/run API。platform="ios"でiOS targetを生成し、他leafから設定を補完しません。
- Produces: iOS17/device family1,2の実効settings、Simulator destination選定/実test/buildとresult summary。

- [ ] Step 1: iOS leaf欠落のstatic REDと `test_ios_quality_is_connected`、`test_ios_clean_app_test_and_build`、`test_ios_actor_and_test_failure_rejected`、`test_missing_or_wrong_destination_rejected` を作ります。
- [ ] Step 2: quality fileを同梱し、minimum iOS17/device family1,2へ設定。macOS設定へのincludeやparent/sibling importを含めません。検証scriptのplatform/destinationだけを変え、qualityの抜けを作りません。
- [ ] Step 3: 既存runtimeとavailable deviceを読む。利用Simulatorのidentifier・OS・boot/fixture app配置/testの副作用を提示し承認します。runtime不足で無断download/OS設定変更をせず、実機署名やpush通知登録を行いません。
- [ ] Step 4: xcodebuildの実test/result bundleを取り、対象runtime/destinationとtotalTestCount>0/failedTests=0をassertします。iPhone/iPadをサポートするbuild settingsを確認し、実測したdevice範囲だけを報告します。実device全組合せやUI導線を検証したと述べません。
- [ ] Step 5: `python3 -m unittest discover -s tests/native -p 'test_swift_ios.py' -v` とSwift static/macOS suiteを再実行し、正常0・異常非0を確認します。
- [ ] Step 6: `feat: add iOS Swift app settings` でlocal commitします。

## Handoff

統合計画へ、commit、toolchain/formatter/SwiftLint/SDK版とhash、実destination、settings、test count、正常/異常の出力、署名状態保全を渡します。SwiftPMやSDKの存在だけでapp受入れを合格にしません。
