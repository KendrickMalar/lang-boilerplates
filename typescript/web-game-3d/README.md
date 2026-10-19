# TypeScript Web 3D Game Boilerplate

ブラウザ3Dゲームの試作向けに、Three.js＋Rapier、Vite、単体テスト、実ブラウザ検査を組み合わせた設定です。Roblox互換エンジンではありません。描画・入力・カメラ・ゲームループ・テスト本体・HTMLは利用側で実装します。Reactは必須にしません。

このディレクトリだけで完結します。親・兄弟の設定へ依存しません。Node 24.15以上の24系またはNode26以上（Node25は対象外）、pnpm 12.6.0、ESMを前提にします。

## 1. コピーするファイル

下記を利用プロジェクトのルートへコピーします。既存ファイル・symlink・既存.huskyがあれば停止し、差分と影響を確認してから統合します。package.jsonやpnpm-workspace.yamlを丸ごと上書きしません。READMEのコピーは任意です。

| コピー元                                                       | コピー先                       |
| -------------------------------------------------------------- | ------------------------------ |
| [package.json](./package.json)                                 | `package.json`                 |
| [tsconfig.base.json](./tsconfig.base.json)                     | `tsconfig.base.json`           |
| [tsconfig.json](./tsconfig.json)                               | `tsconfig.json`                |
| [tsconfig.app.json](./tsconfig.app.json)                       | `tsconfig.app.json`            |
| [tsconfig.tools.json](./tsconfig.tools.json)                   | `tsconfig.tools.json`          |
| [tsconfig.tests.json](./tsconfig.tests.json)                   | `tsconfig.tests.json`          |
| [tsconfig.e2e.json](./tsconfig.e2e.json)                       | `tsconfig.e2e.json`            |
| [eslint.base.mjs](./eslint.base.mjs)                           | `eslint.base.mjs`              |
| [eslint.config.mjs](./eslint.config.mjs)                       | `eslint.config.mjs`            |
| [.prettierrc.json](./.prettierrc.json)                         | `.prettierrc.json`             |
| [.prettierignore](./.prettierignore)                           | `.prettierignore`              |
| [.editorconfig](./.editorconfig)                               | `.editorconfig`                |
| [.gitignore](./.gitignore)                                     | `.gitignore`                   |
| [.node-version](./.node-version)                               | `.node-version`                |
| [lint-staged.config.mjs](./lint-staged.config.mjs)             | `lint-staged.config.mjs`       |
| [pnpm-workspace.yaml](./pnpm-workspace.yaml)                   | `pnpm-workspace.yaml`          |
| [vite.config.ts](./vite.config.ts)                             | `vite.config.ts`               |
| [vitest.config.ts](./vitest.config.ts)                         | `vitest.config.ts`             |
| [playwright.config.ts](./playwright.config.ts)                 | `playwright.config.ts`         |
| [playwright.preview.config.ts](./playwright.preview.config.ts) | `playwright.preview.config.ts` |
| [.husky/pre-commit](./.husky/pre-commit)                       | `.husky/pre-commit`            |
| [.husky/pre-push](./.husky/pre-push)                           | `.husky/pre-push`              |
| [LICENSE](./LICENSE)                                           | `LICENSE.lang-boilerplates`    |

設定はMITです。著作権表示とライセンス文を保持し、利用側のライセンスは上書きしません。ゲームコード、サンプルテスト、index.html、lock、ブラウザ本体は配布しません。設定だけ・テストなしの状態を合格にはしません。

## 2. 依存とブラウザの導入

依存はThree.js 0.186.1、@types/three 0.186.0、@dimforge/rapier3d-compat 0.21.0、Playwright 1.64.1、eslint-plugin-playwright 2.12.1で固定しています。共通検査はTypeScript 6.0.3、Vite 8.3.4、Vitest 5.0.3、typescript-eslint 8.71.1等です。Three.jsと型定義は対応するリリース系列を揃えます。

対象・保存先・ダウンロードの許可を確認し、プロジェクトルートで実行します。

```sh
pnpm install --ignore-scripts --engine-strict
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
pnpm exec playwright install chromium --only-shell
```

生成したpnpm-lock.yamlをGit管理します。`PLAYWRIGHT_BROWSERS_PATH`は後の検査時も同じ値を設定してください。ブラウザの導入は明示実行だけで、checkやinstallから自動ダウンロードしません。ユーザーのChrome・プロファイル・ログイン状態は使いません。Chromium以外のブラウザはこの標準構成の検証対象外です。

pnpmの依存安全設定（検証時の自動install禁止、公開24時間未満の拒否、未承認build scriptの拒否、esbuildのinstall script不許可）は維持します。エラーを全script許可やrelease-age例外で回避しません。OS依存が不足する環境では必要項目を確認し、OS変更を伴う`install --with-deps`を無断実行しません。

## 3. 利用側で用意するもの

- `index.html`、`src/**/*.ts`：実ゲーム。DOMとvite/client型を利用できます。Node globalsは許可しません。
- `tests/**/*.test.ts`：Vitestの単体テスト。Roblox等のサービスと分けたルール・数値・状態遷移を検査します。
- `tests/e2e/**/*.spec.ts`：Playwrightのブラウザ試験。Node側のテストコードなので、DOM操作はlocator等を使います。ブラウザ側ヘルパーはsrc側に置き、Node側テストにdocument/windowを直書きしません。
- Vite設定・Playwright設定はNode型のみ。単体とE2Eは別の型プロジェクト・別runnerで、相互に実行しません。

Rapier互換版はWASMをJSへ同梱するため、外部CDNやWASM配信プラグインを必須にしません。`await RAPIER.init()`が成功してからWorldを作ります。初期化失敗を握り潰さず、ゲームループを開始しません。Three.jsは描画、Rapierは物理です。固定時間刻み、描画位置の同期、入力、カメラは利用側の責務です。Three.jsの時間管理は非推奨のClockではなくTimer等を使います。

## 4. 検査コマンド

| コマンド                | 内容                                                  |
| ----------------------- | ----------------------------------------------------- |
| `pnpm dev`              | Vite開発サーバー                                      |
| `pnpm typecheck`        | ブラウザ・Node設定・単体・E2Eの型検査                 |
| `pnpm lint`             | 型情報Lint、単体/E2Eのonly・skip拒否。warningも不合格 |
| `pnpm format`           | 書式を適用                                            |
| `pnpm format:check`     | 書式検査                                              |
| `pnpm test`             | Vitest単体テスト。0件は不合格                         |
| `pnpm test:e2e`         | 開発サーバーでChromium試験。0件は不合格               |
| `pnpm build`            | Vite本番ビルド                                        |
| `pnpm test:e2e:preview` | 本番ビルド後、previewでChromium試験                   |
| `pnpm check`            | 型→Lint→書式→単体→本番ビルド＋E2E。最初の失敗で停止   |

開発確認と最終確認は、ブラウザの保存先を指定した同じ環境で行います。

```sh
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
pnpm test:e2e
pnpm check
```

Playwrightが127.0.0.1:4173（開発）または4174（preview）を起動・終了します。外部公開せず、既存サーバーを再利用せず、ポートが使用中なら失敗します。pnpm経由のサーバー起動では終了待ちが残る環境があったため、webServerは選定したローカルViteのCLIをNodeで直接起動します。既存プロセスを止めて回避しません。

### ブラウザ試験で必ず判定すること

PlaywrightはpageerrorやHTTP失敗を自動で不合格にしません。利用側のE2Eで、ページを開く前にpageerror・console error・requestfailed・HTTP 400以上を収集し、終わりに0件をassertしてください。WASM初期化完了、実際の描画、入力後の状態変化、resizeも期待結果までassertします。単にページが開いたことやcanvasが存在することだけでは合格にしません。

WebGLを使えるChromium実行環境が必要です。描画不可・初期化失敗をskipしたり、モックのRendererやNullEngineへ切り替えて合格にしません。trace・失敗時画像は`test-results/`へ出ます。必要な成功時画像もテストで保存します。ソフトウェア描画やエミュレーターの結果を実GPU・スマホ実機の性能と扱いません。

## 5. Gitフック

依存導入でフックを自動有効化しません。Git root、既存core.hooksPath、その先のフック、Git共通ディレクトリのhooks、既存.huskyを先に調べます。

```sh
git rev-parse --show-toplevel
git rev-parse --git-common-dir
git config --show-origin --get core.hooksPath
```

最後のexit 1は未設定を表します。既存フック・別hooksPathがある場合や、プロジェクトがGit rootと異なる場合は停止して統合方針を確認します。既存・グローバルのフックを変更しません。既存設定がなく、利用側のローカルGit設定変更が許可されている場合だけ、Git rootで`pnpm exec husky`を実行します。生成される`.husky/_`はGitへ追加しません。commit前に変更ファイルの書式・Lint、push前に`pnpm check`を実行します。push前検査にはブラウザとE2Eが必要です。不合格をhookスキップで回避しません。

## 6. 境界と検証範囲

この設定の保守試験は、配布ディレクトリだけを隔離先へコピーし、そこで生成した使い捨てゲームを検査します。実WebGLの画素、Rapierの落下・接触、キー入力、resizeを開発と本番previewで確認し、実行時エラー・HTTP失敗・WASM初期化失敗・テスト0件・型不正が非0になることを検査します。検証用ゲームは配布物ではありません。

Roblox本実装との仕様・データ・シード・シナリオの整合はゲーム側で検査します。ブラウザの合格はRobloxの物理・通信・Humanoid・保存・購入・公開品質の合格ではありません。Roblox風の敵リグ・カメラ・演出やAI試遊ランナーの実装も、この設定には含みません。

## 公式資料

- https://threejs.org/manual/pages/installation.html
- https://rapier.rs/docs/user_guides/javascript/getting_started_js/
- https://playwright.dev/docs/test-webserver
- https://playwright.dev/docs/browsers
- https://typescript-eslint.io/getting-started/typed-linting
- https://pnpm.io/settings/build
- https://typicode.github.io/husky/how-to.html
