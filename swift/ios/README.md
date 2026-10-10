# iOS/iPadOS Swift quality settings

Swift 6 mode / iOS 17 / device families 1,2 / warnings as errors, for an existing standard Xcode app.
No app source or Xcode project is supplied. SwiftPM alone does not verify an app.

## Safe copy and connection

Read existing files, symlinks, Base Configurations and Git hooks first; present a
merge diff and obtain approval before overwriting. Copy these files to the same
relative paths in your **app project root**:

- [.swift-format](.swift-format), [.swiftlint.yml](.swiftlint.yml)
- [.editorconfig](.editorconfig), [.gitignore](.gitignore)
- [Config/Quality.xcconfig](Config/Quality.xcconfig)
- [Config/Debug.xcconfig](Config/Debug.xcconfig), [Config/Release.xcconfig](Config/Release.xcconfig)
- [Config/VerifyUnsigned.xcconfig](Config/VerifyUnsigned.xcconfig) (fixture only)
- [scripts/check.sh](scripts/check.sh)
- [.githooks/pre-commit](.githooks/pre-commit), [.githooks/pre-push](.githooks/pre-push)
- [LICENSE](LICENSE) as `LICENSE.lang-boilerplates` (retain MIT notice; do not change your product license)

This README is guidance, not a replacement for your product README. Add Config
files to Xcode, then select Debug/Release as **Base Configuration for every Swift
app/test target**, including project configurations when appropriate. Merge existing
xcconfig files rather than discard them. Target overrides can defeat the settings;
`settings` reads back Debug and Release values. Copying alone does not enable them.
Team, bundle identifier, capabilities, sandbox and entitlements remain product
responsibilities. No default module-wide MainActor isolation or service permission
is imposed. Do not attach VerifyUnsigned to product Release/archive configurations.

## Check

Requires macOS, full Xcode with Swift compiler >=6, official `swift-format` from
that Xcode, SwiftLint **0.65.1**, Python >=3.9, and xcrun/xcodebuild/shasum.
Obtain tools only with separate approval. No auto-install or global xcode-select
change is performed. Formatter `main` version is not a stable release guarantee:
validate your syntax against the selected tool and stop on incompatibility.

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
export SWIFTLINT_BIN=/approved/path/to/swiftlint
export NATIVE_APP_PROJECT=YourApp.xcodeproj
export NATIVE_APP_SCHEME=YourApp
export NATIVE_APP_SOURCE_DIR=Sources # include app AND test sources, no generated/cache files
export NATIVE_APP_DESTINATION='platform=iOS Simulator,id=YOUR-APPROVED-DEVICE-UUID'
sh scripts/check.sh all
```

Modes: `format|lint|settings|test|build|all`. `all` stops at the first failure in
format(strict) → SwiftLint(strict) → settings → app test → native build.
Project/source paths must resolve inside the copied project root. Missing/empty
source, missing project/scheme/destination/tool and zero/only-skipped tests fail.
No `ignore-exit`, lenient syntax or validation bypass is used. Formatter never
modifies source in this check. Keep generated sources/caches outside SOURCE_DIR.

Results, Debug/Release build settings and fingerprints (path/version/SHA256) are
saved in `.native-check/` (or root-local `NATIVE_APP_WORK_DIR`). DerivedData and
Swift package clones are local there. External package dependencies require their own approval and the project-local
`project.xcworkspace/xcshareddata/swiftpm/Package.resolved` lock (absence fails).
Xcode can fetch dependencies pinned by that lock; the script disables automatic
version resolution, but is not an approval gate or package auditing tool.
The maintainer fixture uses no external packages.

Only for an isolated **approved fixture**, set `NATIVE_APP_VERIFY_UNSIGNED=1` and
create `.native-app-fixture` containing `approved-isolated-fixture`. This explicitly
passes VerifyUnsigned to this invocation; it never changes global signing, Team,
certificates or product settings. This marker is an acknowledgement, not a sandbox.
Request approval before launching tests in a new product/app environment.

## Simulator approval and results

Read available devices/runtimes first using the selected Xcode:
`xcrun simctl list devices available -j` and `xcrun simctl list runtimes -j`.
Choose a concrete iOS Simulator UUID. Missing/unavailable, generic, real-device
and macOS destinations fail. The script does not create/download runtimes/devices
or explicitly boot them. Xcode test can boot the selected device, install and
launch the app and test bundle. Present device UUID/OS and these side effects,
then obtain permission before execution; never modify existing devices unapproved.
The result bundle summary must contain passing tests and no failed tests;
SDK presence, build-only, zero or skipped-only tests do not count as app testing.

## Scope and references

Maintainer tests generate minimal SwiftUI/XCTest projects outside this leaf and
verify iOS Simulator hosted app test/build on dedicated iPhone 17 and iPad (A16)
devices with iOS 27.0 and Xcode 27.0. iOS 17 is the deployment setting, not a
runtime tested here. Real devices, every device/OS combination, macOS app,
SwiftPM-only, product signing/release/archive, App Store and UI flows are **not verified**.
Git hooks are optional and manually enabled as described below.

Original MIT configuration/helper code; no third-party product source copied.
References: [Swift concurrency](https://www.swift.org/documentation/concurrency/),
[swift-format](https://github.com/swiftlang/swift-format),
[SwiftLint](https://github.com/realm/SwiftLint),
[Xcode configuration](https://developer.apple.com/documentation/xcode/adding-a-build-configuration-file-to-your-project).

## 手動 Git フック（別承認で有効化）

コピー/install/check は hooksPath を変更しません。Node/Husky は不要です。
プロジェクト root で、まず有効な設定の全 origin と既存フックを読み取り確認します。

```sh
git config --show-origin --get-all core.hooksPath
git rev-parse --git-path hooks
```

設定が未定義の場合の最初のコマンドは exit 1 です。既存フック、global hooksPath、
symlink があれば**有効化を停止して相談**し、既存内容・差分を提示してください。
local hooksPath は global の既存フックも隠すため、無断で置き換え/連結しません。
既存フックなし、又は承認済みの統合方針がある場合に限り、変更の別承認後に実行します。
以下は配布フックを選ぶ場合の例で、既存フックの統合コマンドではありません。

```sh
chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks
```

pre-commit は `sh scripts/check.sh format`（書換えなし）、pre-push は
`sh scripts/check.sh all` を実行し、不合格は非0で commit/push を止めます。
README の tool/lock/source/test と環境変数を hook 実行環境にも用意してください。
IDE の Git も同じ環境が必要です。iOS test の Simulator boot/app 配置や依存取得は
フック有効化だけで承認されたことになりません。実行の副作用も先に承認してください。
手動 check を先に検証し、ローカル bare remote で正常/異常を検査します。
GitHub への試験 push、global Git 設定変更、`--no-verify` による回避は行いません。
Windows/Linux の native hook 動作は未実行です。
