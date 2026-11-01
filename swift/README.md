# Swift app settings

- [macOS](macos/README.md): Swift 6 mode, minimum macOS 15.
- [iOS/iPadOS](ios/README.md): Swift 6 mode, minimum iOS 17, device families 1,2.

Use a standard Xcode project/xcconfig. Copy only the chosen leaf to the app
project root; each is self-contained. No product source, project, certificates,
fixtures or caches are distributed. Simulator testing is not real-device or
product signing/release verification.

各 leaf の README に全配布ファイルとコピー先、手動 check、任意 Git フックの
有効化手順があります。コピーだけで hooksPath を変更しません。既存フックを
読み取り確認し、変更の別承認後のみ project-local に有効化します。
保守 suite は repository root の `pnpm test:native:static` と言語/platform 別の
`test:native:macos` / `test:native:ios` から明示実行します。
未実行 native suite は既存 TypeScript suite の成功と分けて記録します。
