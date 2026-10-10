# Rust／Tauri・Swiftアプリ用設定集 — 設計

> 作成日・最終更新: 2026-10-10
> 出所: ユーザーの要件・構成確認、deep調査の固定commit実設定と公式資料。
> 目的: Scaffoldが言語別READMEから、用途に合う自己完結した設定セットを選び、既存データ・権限を保護して導入できるようにします。

## 目次

1. 要約と決定事項
2. 配置・コピー契約
3. Rust／Tauri
4. Swiftアプリ
5. チェックとGitフック
6. 合格基準・検証範囲
7. 状態・次のアクション
8. リスク・残論点
9. 参考元と決定ログ

## 1. 要約と決定事項

Rust/Tauri backend、Swift/macOS、Swift/iOSの3セットを追加します。各セットは設定・README・LICENSE・補助スクリプトを同梱し、親や兄弟の設定に依存しません。製品sourceは利用側が用意します。初期版ではmacOSでRust/Tauriを実検証し、Windows/Linuxは手順を用意して未実行と明記します。

| 論点 | 決定 | 理由・補足 |
| --- | --- | --- |
| 配布 | **設定・READMEのみ** | 製品source、画像、証明書、秘密情報は配布しません。build.rs等のbuild/check補助は設定として含めます。 |
| Rust用途 | **Tauri desktopのRust/backend側のみ** | macOS/Windows/Linuxが対象。TypeScript frontend設定は同梱しません。 |
| Rust構成 | **src-tauriの単体crate** | workspaceや複数crateは初期対象外です。 |
| Swift用途 | **macOSとiOS/iPadOSの2セット** | 各platformの設定を混ぜません。 |
| 最小OS | **macOS15／iOS17** | ユーザー選択の初期値です。SDK版・compiler版とは別です。 |
| Swift project | **標準Xcode project＋xcconfig** | XcodeGen/Tuist等の追加project生成CLIは使いません。 |
| Rust検証 | **macOS実検証、Windows/Linuxは未実行明記** | 2026-10-10改訂: 全3OS実検証を必須とした回答をユーザーが訂正しました。未実行を成功にしません。 |
| 進め方 | **計画モードなしで設計** | モード例外は確認済みです。設計文書・実装計画のレビューと実装開始は別です。 |
| 環境・外部操作 | **導入・署名・OS/global設定・公開は別承認** | 今回の構成承認はインストールやmain統合・pushの許可ではありません。 |

## 2. 配置・コピー契約

```text
rust/
  README.md
  tauri/
    README.md
    LICENSE
    rust-toolchain.toml
    rustfmt.toml
    .editorconfig
    .gitignore
    .cargo/config.toml
    scripts/check.sh
    scripts/check.ps1
    .githooks/pre-commit
    .githooks/pre-push
    src-tauri/
      Cargo.toml
      build.rs
      tauri.conf.json
      capabilities/main.json
swift/
  README.md
  macos/
    README.md
    LICENSE
    .swift-format
    .swiftlint.yml
    .editorconfig
    .gitignore
    Config/Quality.xcconfig
    Config/Debug.xcconfig
    Config/Release.xcconfig
    Config/VerifyUnsigned.xcconfig
    scripts/check.sh
    .githooks/pre-commit
    .githooks/pre-push
  ios/
    同じ品質ファイル・補助一式（iOS/iPadOS用のxcconfigと検証手順）
```

Rustセットはプロジェクトrootへ配置し、src-tauri配下の設定は同じ相対位置へ導入します。Swiftセットは対象アプリのproject rootへ導入します。全コピー対象とコピー先をREADMEに列挙し、ドットファイル・フック・LICENSEを省略しません。READMEは読むための入口で、製品READMEを上書きする必要はありません。

既存ファイル・symlink・manifest・フックがある場合は読み取り確認と差分提示を先に行い、承認前に上書きしません。Cargo.tomlやproject設定を既存のものへ適用する場合は差分統合します。LICENSEは例えばLICENSE.lang-boilerplatesとして保存し、利用製品のライセンスを変更しません。

言語別READMEは選択入口です。リポジトリroot READMEにRust/Swiftを追加します。Development Profileの言語別表へのRust/Swiftリンク追加は、公開内容を確認した後、対象と変更を提示して別承認します。TypeScript設定と既存Profileルールは今回変更しません。

保守テストはroot testsへ追加し、製品source・Xcode fixture・frontend fixture・Cargo/Swift cacheはGit管理外の作業用領域へ生成します。これらは配布しません。

## 3. Rust／Tauri

### 版・構造

初期の設計基準はRust1.92.0、edition2024、tauri2.12.2、tauri-build2.7.1です。crate直接MSRVは1.90を確認していますが、推移依存まで1.92で動くと検証済みではありません。Cargo.lockで解決した全依存の要求を確認して実buildします。不整合が出た場合は停止し、版変更案と影響を提示します。

rust-toolchain.tomlは基準版とrustfmt/clippyを明示します。現在のdefault stableは1.92ですが、Rustupのnamed toolchain一覧には1.95.0もあり、1.92.0のexact名は確認できていません。無許可のRustup自動導入は行いません。実装前に、選んだ検証用toolchainが利用可能か確認し、必要な取得は隔離範囲を示して承認します。

src-tauri/Cargo.tomlは単体crateのmanifestで、製品名・identifier・source entryは利用側へ合わせます。製品src/main.rs・src/lib.rsは含めません。build.rsはTauri build補助で、custom app commandのmanifest登録をどこで設定するか明示します。frontend成果物・dev URLは利用側が用意し、READMEで接続確認を要求します。frontend build/install commandを自動実行する初期設定にはしません。

### 品質方針

- stable rustfmtの設定を使います。edition2024、幅100、4スペース、LF、import整列を初期方針とします。nightly-only設定は使いません。
- Clippy既定allと警告不合格を基盤にします。groupのpriorityを低くし、必要な個別設定と衝突させません。
- manifestではrustのunsafe_code/unused_must_useをdeny、Clippyのallをwarn（priority -1）、unwrap_used/expect_used/todo/dbg_macroをdenyとします。checkの-D warningsで残る警告も不合格にします。boot/build helperはResultによるerror伝搬で正常系を成立させます。fixtureで必要な最小例外が見つかった場合は理由と狭い対象を記録し、無断で全体緩和しません。
- pedantic/restriction全groupは有効化せず、追加lintを選びます。missing_docsをアプリ全体へ無条件に強制しません。
- fmt/check/Clippy/test/buildを分け、依存はlockを生成・保存して検査します。all-featuresは同時有効化可能性を確認せず使いません。
- Cargo1.97以降のbuild.warnings方式を1.92へ適用しません。基準版で利用可能な-D warnings等を使用します。

### Tauri安全境界

capabilityはmain windowなど利用側が定めたidentifierと必要permissionだけを候補にし、tauri.confで使用identifierを明示します。remote API、広いfilesystem/shell/process/updater、全window wildcardは既定で許可しません。接続先・CSPも製品ごとの確認対象です。

custom Rust app commandはTauri既定では広く使用可能で、capability JSONだけではcommand実装の安全性を保証しません。build補助/READMEはAppManifest::commands等の接続箇所を説明し、利用側のcommand名・permission・input/path/scope検査を要求します。検証fixtureで許可/拒否境界を確認します。全ての任意製品commandが安全になるとは説明しません。

## 4. Swiftアプリ

### compiler・quality

- Swift6 language modeを明示し、data-race安全検査を基盤にします。Swift6 compilerの使用だけでmode6とみなしません。
- Swiftの警告をエラー扱いにする方針です。Swift5移行向けStrictConcurrency設定とSwift6 modeの既定検査を区別します。
- 新規セットで全moduleのdefault actor isolationを無条件にMainActorへ変更しません。UIやbackground作業のactor/Sendable設計は製品コードの責任です。
- 整形は公式swiftlang/swift-format、LintはSwiftLint strictを初期候補にします。formatterのlintはstrictで、構文エラーを無視しません。SwiftLintは既定規則にempty_count/contains_over_first_not_nil/force_unwrappingをopt-inとして追加し、empty sourceを許可しません。force系を作者のlegacy例外だけで一括offにしません。
- 4スペース・LF・明示的な整形設定を初期方針にし、SwiftLintの空白規則との競合をfixtureで検査します。nilやerror処理の規則と単なる好みの整形を分けます。
- SwiftLintの候補は0.65.1です。SourceKit/SwiftSyntaxと使用compilerの互換性、配布binaryのhashを確認します。取得・実行導入は別承認です。

### Xcode接続とplatform分離

Quality.xcconfigは共通のSwift品質設定、Debug/Releaseは品質設定を同じセット内からincludeします。macosはmacOS15、iosはiOS17/device family1,2を初期値にします。製品名・bundle ID・team・entitlements・app groupは利用側が決めます。

xcconfigはXcodeのproject/targetのBase Configurationへ接続する手順を記載し、showBuildSettings等でSwift mode・warning設定・最小OSを読み戻します。コピーしただけでは有効と宣言しません。Package.swiftだけでアプリtargetを完成させず、SwiftPM unit testとapp target build/testの結果を分けます。UI frameworkは設定側で製品sourceを強制せず、検証fixtureに最小SwiftUI appを使う候補です。

VerifyUnsigned.xcconfigは隔離fixture/検証用だけに適用する候補です。既存の製品署名・entitlements・証明書を消しません。release署名、archive、実機配信、App Store操作は対象外です。macro/plugin validation skip、ignore exit、構文無視を既定checkへ入れません。

### 検証環境

現在確認できた候補はper-command DEVELOPER_DIRで既存Xcode27.0/build27A266a、Swift6.4、macOS/iOS SDKを使用する環境です。global xcode-selectはCLTのまま変更しません。CLTはSwift/formatter6.2.3、Xcode側formatter表示はmainなので、両者を無意識に混在させません。

検証ではcompiler/SDK/formatterの実path・version・binary hashを記録し、同じ環境を明示してformat/lint/build/testを行います。main表示を安定releaseの互換保証としません。使用構文・規則が一致しない場合は停止し、固定release formatter等の代替案を提示します。以前のSourceKit crashや古いXcodeの検証回避を流用しません。

## 5. チェックとGitフック

まず手動checkを成立させ、その後に既存hooksPath/フックを調べ、有効化の別許可を取ります。Rust/SwiftだけのcheckへNode/Huskyを必須追加しません。.githooksを配布し、GitのローカルhooksPath変更は既存フックなし又は承認済み統合方針がある場合に限ります。

RustはPOSIX shellとPowerShellのcheck補助を候補にし、選択toolchainとmanifest/lock/source/testの存在を確認します。fmt検査→Clippy→test→native buildの順で、最初の不合格で停止します。Windows/Linuxの補助は静的に検査し、OS固有の未実行をREADMEに明記します。

Swiftはproject/scheme/destination・tool実path・source/testを確認し、format(strict)→SwiftLint(strict)→app test/buildの順で停止します。sourceなし、testなし、tool不在、未接続xcconfig、SDK不一致を成功扱いにしません。失敗をtrueやskipで隠しません。iOS Simulatorのboot/アプリ配置・テストは、対象fixtureと副作用を提示して承認後に行います。

## 6. 合格基準・検証範囲

- A1: 3セットを1つずつ隔離projectへコピーして、READMEの全相対リンク・設定include/import/script参照がセット内で解決する。親・兄弟からの補完を行わない。
- A2: Rust正常fixtureでfmt/Clippy/test/buildが終了0。整形違反・unwrap等の選定違反・未処理Result・失敗testは意図した診断で非0となり、後続段階を実行しない。
- A3: Tauri fixtureで有効capability/window/permissionを検証し、許可した操作と未許可操作を分ける。custom app commandとplugin ACLの違いを検査し、JSON検査だけでbackend安全を保証しない。
- A4: SwiftのmacOS/iOS fixtureで実効build settingsがmode6・warnings error・最小OS15/17と一致。Xcode targetへ接続されていない設定を検出する。
- A5: 正常Swift fixtureのformat/lint/app test/buildが終了0。整形違反・選定Lint違反・data-race又はactor isolation違反・失敗testは意図した診断で非0となる。
- A6: iOSは利用する実runtime/destinationを記録し、iPhone/iPadOS対象の設定を検査する。SDK/runtime存在だけを実test成功とみなさない。
- A7: tool不在・sourceなし・testなし・manifest/project/scheme不在・未対応OS・署名検証設定の誤適用を非0又は明示未検証とし、合格へ隠さない。
- A8: 隔離HOME/CARGO_HOME/target/DerivedData/Swift package cacheを使い、既存コード・global Gitフック・xcode-select・証明書・製品署名を変更しない。既存フックを無許可で上書きしない。
- A9: Git hookをローカルfixtureで検証し、不合格commit/pushが停止してHEAD/ローカルbare remote refが不変。GitHubへ試験pushしない。
- A10: 配布treeに製品source・fixture・cache・秘密情報・署名assetを含めず、参考元とlicense条件を記録する。FSL/独自licenseをMITへ自動移植しない。
- A11: 既存TypeScriptの全suiteを新機能統合後にも実行し、退行がないことを確認する。現在のTypeScript設定は変更しない。
- A12: Rust/TauriのWindows/Linuxはnative検証未実施と明記。macOSの成功を全3OSへ一般化しない。Swiftの検証結果はmacOS app/iOS Simulator/SwiftPMを分けて記録する。

## 7. 状態・次のアクション

| 項目 | できていること | できていないこと |
| --- | --- | --- |
| 要件・参考元 | deep調査、3セットと最小OS/構成/検証範囲の確認済み | 保存済み設計文書のユーザーレビュー |
| 環境 | version/SDK/runtimeのread-only確認済み | tool固定、crate/SwiftLint取得、fixture build/test |
| 実装 | 文書化のみ | 設定ファイル・script・testの実装 |
| 公開 | 既存repoはPublic/MIT | 今回変更のmain統合・push・Profile表追加の承認 |

- [ ] 保存済み設計文書をユーザーがレビューします。
- [ ] 承認後、実装計画を作り、実行方式を選びます。
- [ ] 導入するtool/dependency・fixtureの副作用を提示して承認します。
- [ ] 検証を先に書いて実装し、実出力と差分を確認します。
- [ ] 独立レビューと統合検証後、承認されたmain統合・pushを行います。
- [ ] 公開内容を読み戻し、別承認後に言語別Profile表を追加します。

## 8. リスク・残論点

| リスク | 対応・停止条件 |
| --- | --- |
| 推移依存MSRVが候補Rustを超える | 解決後に要求を確認。不整合なら無断upgrade/overrideせず相談 |
| SwiftLint/SourceKit/formatterとXcodeの不一致 | actual path/version/hashとfixtureで確認。構文無視・validation skipで回避しない |
| Tauri custom commandの過大な権限保証 | 製品command登録/input/scopeの責任とfixture境界を明記 |
| xcconfigの未接続/上書き | 実効build settingsをassertする |
|署名/OS/global設定への波及 | 隔離scopeとVerifyUnsignedを明示し、外部影響は別承認 |
| OS未検証 | 初期版のWindows/Linuxは未実行を明記し、all-platform passingと宣言しない |

現時点でtool依存導入やアプリ実行の許可はありません。実装・tool調達・公開へ進む前に、その段階の対象を再確認します。単体sourceを配布しないことと、build/check補助コードを含めることをREADMEで区別します。

## 9. 参考元と決定ログ

- Tauri公式の固定snapshot: https://github.com/tauri-apps/tauri/tree/7fcd8a743497f1895b999bb8c8d9c1241662a476
- GitButler（考え方の参考、FSL原文確認）: https://github.com/gitbutlerapp/gitbutler/tree/3049d6b8f512aeba070b7121ca50a5febb99ee51
- CodeEdit（MIT）: https://github.com/CodeEditApp/CodeEdit/tree/fa2aebd86373211c78626074b53ab75010767575
- NetNewsWire（MIT）: https://github.com/Ranchero-Software/NetNewsWire/tree/c76856b18b9fb464c7c731c9c16e5e5082f55095
- isowords（考え方の参考、独自原文確認）: https://github.com/pointfreeco/isowords/tree/c727d3a7c49cf0c98f2fa4f24c562f81e30165f7
- Cargo/Clippy: https://doc.rust-lang.org/cargo/reference/workspaces.html 、 https://doc.rust-lang.org/clippy/usage.html
- Tauri境界: https://v2.tauri.app/security/capabilities/ 、 https://v2.tauri.app/develop/tests/
- Swift6: https://www.swift.org/documentation/concurrency/
- Swift formatter: https://github.com/swiftlang/swift-format/tree/b15dd59fad21f1770cdc888b1ca6e2937490001a
- SwiftLint: https://github.com/realm/SwiftLint/tree/ec4691d9e813a1d3358e82917326b56b0a71d3c9
- Xcode接続: https://developer.apple.com/documentation/xcode/adding-a-build-configuration-file-to-your-project

2026-10-10決定: deep調査、設定/READMEのみ、Tauri desktop3OS/Rust側のみ、Swift macOS/iOS、最小OS15/17、標準Xcode/xcconfig、単体crate。検証範囲は最新の訂正でmacOS実検証・Windows/Linux未実行明記へ変更。設計文書化を承認済みですが、保存済み文書と実装計画のレビュー・実装開始はこれからです。
