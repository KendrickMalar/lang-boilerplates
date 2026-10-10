# Native App Settings Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 独立したRust/Swift設定セットを言語一覧・手動Gitフックへ接続し、既存TypeScriptを保護して統合・公開します。

**Architecture:** RustとSwiftは別計画で実装・検証します。この計画は両成果のcatalog/hook/回帰/受入れをまとめ、許可されたGitHub/Profile操作だけを行います。並列writerを同じcwdへ置かず、Native実行なら順番にlinked planを完了します。

**Tech Stack:** 既存pnpm/TypeScript tests、Python3 unittest、Git、GitHub gh CLI

**Spec:** `docs/superpowers/specs/2026-10-10-native-app-settings-design.md`（ユーザーレビュー承認済み）

## Global Constraints

- 配布は設定・README・LICENSE・build/check補助だけ。製品source・fixture/cache・画像・証明書・秘密情報を配布しません。
- 各用途を自己完結させ、READMEの相対リンクとコピー先を明示します。親・兄弟設定から補完しません。
- コードは専用feature worktree、1cwdにつきwriter1人。既存main/他worktree/ユーザー変更を上書きしません。
- 依存/tool取得・OS/global設定・署名/公開/main統合・push/Profile更新は実行直前に別承認。Rustupの自動導入を勝手に起動しません。
- fixtureとHOME/cache/target/DerivedDataはtask専用Git管理外領域。無許可で消さず、実出力・版・exitを保存します。
- 検証不合格・未検証をskip/ignore-exit/validation bypassで成功扱いにしません。コミットにAI帰属行を付けません。

- 対象はRust/Tauri desktop backendのみ、Swift macOS15/iOS17。Windows/Linux nativeは未実行を明記します。
- 設計基準はRust1.92.0/edition2024/tauri2.12.2/tauri-build2.7.1、Swift6 mode/SwiftLint0.65.1候補。実装の不整合・版変更は別判断です。
- TypeScript設定と既存Profileルールは今回変更しません。
- 実装開始・tool依存取得・Simulator/app操作・署名・公開/Profile更新は、この計画の保存だけでは許可されません。

## Linked Plans / 実行順序

1. `2026-10-10-rust-tauri-settings.md`: 2task、Rust品質→Tauri boundary/native。
2. `2026-10-10-swift-app-settings.md`: 2task、macOS→iOS。
3. 本計画: catalog/hook→統合回帰/レビュー→公開/入口。

各計画が独立したtest cycleを持ちます。共通製品codeはなく、保守用harnessもRust/Swiftで分けています。1つのworktreeでのNative実行は順番に進め、Subagent-drivenを選ぶ場合もwriter範囲/別worktreeを明示します。

## Review Focus

1. 新しい言語READMEがold TSの導入やscopeを誤変更しない（Task1/2）。
2. Gitフック有効化が既存global hooksPathを消さない（Task1）。
3. Windows/Linux未実行やSDK存在をpassing表示へ丸めない（Task2）。
4. 検証fixture・tool/cache・secret/証明書が公開treeへ入らない（Task3）。
5. main/Profile公開を技術レビュー承認だけで実行しない（Task3）。

### Task 1: Catalogと手動Gitフック

**Files:**
- Modify: `README.md`、`package.json`（保守用test scriptsのみ）
- Create: `rust/tauri/.githooks/pre-commit`、`pre-push`、`swift/macos/.githooks/pre-commit`、`pre-push`、`swift/ios/.githooks/pre-commit`、`pre-push`
- Test/Create: `tests/native/test_catalog.py`、`tests/native/test_hooks.py`
- Modify: 各言語/leaf README（導入/有効化/検証説明）

**Interfaces:**
- Consumes: Rust/Swiftのcheck script API・test出力・独立copy contract。
- Produces: root→言語→leafの相対リンク、保守script名 `test:native:static`、`test:native:rust`、`test:native:macos`、`test:native:ios`。
- Existing `pnpm test`はTypeScript suiteとして保持し、native tool不在の端末で勝手に導入せず、native suiteを別commandで明示します。

- [ ] Step 1: catalog testはroot→rust/swift→leafの実在、leafの全配布ファイル列挙、include/scriptのセット内解決、製品source/secret/cache非混入をassertします。新入口/フック欠落のREDを記録します。
- [ ] Step 2: READMEにコピー先・許可境界・frontend/Xcode接続・tool版・明示未検証OSを記載します。Package-onlyやmockだけの成功をアプリ合格にしません。
- [ ] Step 3: pre-commitはformatter検査、pre-pushはmanual check all。設定copy/installでhooksPathを変えず、既存hooks確認・変更許可後だけproject-local設定を使います。Rust/SwiftにNode/Husky依存を追加しません。
- [ ] Step 4: ローカルGit fixtureで、正常commit/push成功、不合格commit/push非0かつHEAD/bare remote ref不変、global hooksPath/hash不変を検査します。既存hooks fixtureがあれば有効化を拒否/相談する説明も確認します。GitHubへの試験pushはしません。
- [ ] Step 5: root test scriptsを各Python suiteへ接続し、test0件で成功するrunnerを使いません。native suiteの未実行をTS suite成功へ統合して隠しません。
- [ ] Step 6: `feat: connect native settings catalog and manual hooks` でcommitします。

### Task 2: 統合回帰・独立レビュー

**Files:**
- Modify: 必要なaccepted fixのfiles/testsのみ。
- Create: task専用の検証/受入れartifact（Git管理外）。

**Interfaces:**
- Consumes: linked planの固定commit/OS別証拠、Spec A1〜A12。
- Produces: 選択ref・tool/runtime版・合格/不合格/未実施、command/exit/log・残リスクを明記した親受入れ。

- [ ] Step 1: `pnpm test` を既存TypeScript全suiteとして実行し、出力を確認します。旧TS変更なしとmanifest直接pin不変をdiffで確認します。
- [ ] Step 2: Python native static、Rust、Swift macOS、Swift iOS suiteを実行し、Spec12項目の証拠へ対応付けます。実tool版/OS/destination/test countを記録し、source/empty test/CI専用回避が合格へ混ざっていないことを確認します。
- [ ] Step 3: 読み取り専用のfresh whole-branch reviewerへ、固定diff・Spec/各plan・Review Focus・実出力・Rulingを渡します。writerを増やさず、review者へinstall/編集/Git変更を許可しません。
- [ ] Step 4: findingを実影響で再評価し、accepted blockerはRED回帰から修正してaffected/full suiteを再実行します。未実施/範囲外は正直に受入れへ残します。
- [ ] Step 5: 技術受入れを確定します。Windows/Linux未実行、iOS実測device範囲、署名/配布未実施を明示し、全OS passingと宣言しません。

### Task 3: 承認後のmain統合・公開・Profile入口

**Files:**
- Modify: 承認後の `~/.pi/agent/profiles/development/skills/scaffold/references/basic-design.md` の言語テーブル。
- Create: 許可/公開照合artifact（Git管理外）。

**Interfaces:**
- Consumes: Task2の受入れ済みrefと検証証拠。
- Produces: Public main上のrust/README.md、swift/README.md、別承認されたProfile表リンク。TSのリンクは維持します。

- [ ] Step 1: main/remote/feature ref・dirty状況を読んで所有を確認します。新しいuser変更を発見したら上書き/隠蔽せず相談します。fixture/cache/key・license条件を公開前に検査します。
- [ ] Step 2: 対象feature commitと影響、未検証範囲を示し、main merge --no-ffと通常pushを確認します。承認対象以外のbranch/refへ公開しません。force/既存変更上書き/branch・worktree削除は行いません。
- [ ] Step 3: 承認したmerge後refで再検証してから通常pushし、remote SHA・公開README/設定のbytes・visibility/licenseを読み戻します。成否不明の再送前に確認します。
- [ ] Step 4: Profile言語表へRust/Swift追加を確認し、backup後にその行だけ編集します。URLは `https://github.com/KendrickMalar/lang-boilerplates/blob/main/rust/README.md` と `.../swift/README.md`。他のProfile bytes不変を検証します。
- [ ] Step 5: 具体的な必須未完了があれば既存Issueを検索し、対応Issue案を用意して投稿許可を確認します。ユーザーが保留ならlocal handoffにref・証拠・次の一手を残します。無許可のcleanupは行いません。

## Execution Handoff

3計画と承認済みSpecをユーザーがレビューし、実装開始とNative/Subagent-drivenを選んでから設定実装へ進みます。Rust/Swiftの未知なnative依存・Xcode fixture・署名の境界に独立gateがあるため、Subagent-drivenを推奨します。Nativeを選ぶ場合もlinked planを順番に実行し、最後の独立reviewを省略しません。tool取得とSimulator/app操作は対象/version/保存先・副作用を実行前に別確認します。
