# Rust 設定

- [Tauri desktop の Rust/backend 品質設定](tauri/README.md): 単体 `src-tauri` crate、
  Rust 1.92.0 / edition2024。frontend の TypeScript 設定は含みません。
- [サーバー権威のリアルタイム対戦の品質設定](game-realtime/README.md): 数値・キャスト・添字・時刻・
  既定 hasher を禁止、release は LTO 最大。Rust 1.99.1 / edition2024。品質設定のみ（依存・source なし）。
- [ルーム制・WebSocket サーバーの品質設定](game-room/README.md): 容量なしキューと `.await` を
  またぐロックを禁止、actix を ban。Rust 1.99.1 / edition2024。品質設定のみ。
- [ソシャゲ型 HTTP API の品質設定](game-social/README.md): 生の `sqlx::query`・timeout なしの
  `reqwest::Client::new`・`reqwest::get` を禁止、native-tls を ban、`SQLX_OFFLINE` 既定。Rust 1.99.1 / edition2024。品質設定のみ。

3種類を併用するときは game-realtime を土台にして、room・social の規則を次のとおり足します。

- `Cargo.toml` の `[workspace.lints.clippy]`: room から `await_holding_lock`・`await_holding_refcell_ref`・
  `await_holding_invalid_type`・`large_futures`、social から `await_holding_lock`・`await_holding_refcell_ref`（deny）。
- `clippy.toml` の `disallowed-methods`: room の `tokio::sync::mpsc::unbounded_channel`・`futures::channel::mpsc::unbounded`、
  social の `sqlx::query`・`sqlx::query_as`・`reqwest::Client::new`・`reqwest::get` を足します。まだ依存に無い crate の path なので、
  各エントリに `allow-invalid = true` を付けたままにします。
- `deny.toml` の `[bans]`: room の `actix`、social の `native-tls` を足します。
- `scripts/check.sh`: social の `SQLX_OFFLINE` の4行を足します。足し忘れると、commit 時に sqlx のマクロが DB に接続しようとして落ちます。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。
コピー先と既存ファイル保護の手順は leaf README を参照してください。
macOS 実検証が対象で、Windows/Linux native 検証は未実施です。

各 leaf の README に全配布ファイルとコピー先、手動 check、任意 Git フックの
有効化手順があります。コピーだけで hooksPath を変更しません。既存フックを
読み取り確認し、変更の別承認後のみ project-local に有効化します。
保守 suite は repository root の `pnpm test:native:static` と言語/platform 別の
`test:native:rust` / `test:native:rust-game` / `test:native:macos` / `test:native:ios` から明示実行します。
未実行 native suite は既存 TypeScript suite の成功と分けて記録します。
