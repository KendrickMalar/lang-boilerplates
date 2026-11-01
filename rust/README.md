# Rust 設定

| 用途 | 設定・導入手順 |
| --- | --- |
| リアルタイム対戦・ルーム制（WebSocket）のゲームサーバー | [game/README.md](game/README.md) |
| ソシャゲ型の Web ゲーム API サーバー | [web-game/README.md](web-game/README.md) |
| 一般の HTTP API サーバー | [web/README.md](web/README.md) |

- [game](game/README.md): 数値・キャスト・添字・時刻・既定 hasher を禁止（決定的なシミュレーション）、release は LTO 最大。
  容量なしキューと `.await` をまたぐロックも禁止し、actix を ban。Rust 1.99.1 / edition2024。品質設定のみ（依存・source なし）。
- [web-game](web-game/README.md): 生の `sqlx::query`・timeout なしの `reqwest::Client::new`・`reqwest::get` を禁止、
  native-tls を ban、`SQLX_OFFLINE` 既定。Rust 1.99.1 / edition2024。品質設定のみ。
- [web](web/README.md): web-game と同じ設定ファイルで、ソシャゲ固有の記述を除いた一般の HTTP API 用。品質設定のみ。

game と web-game（または web）を1つの workspace で併用するときは、game を土台にして web-game の規則を次のとおり足します。

- `clippy.toml` の `disallowed-methods`: web-game の `sqlx::query`・`sqlx::query_as`・`reqwest::Client::new`・`reqwest::get` を足します。
  まだ依存に無い crate の path なので、各エントリに `allow-invalid = true` を付けたままにします。
- `deny.toml` の `[bans]`: web-game の `native-tls` を足します。
- `scripts/check.sh`: web-game の `SQLX_OFFLINE` の4行を足します。足し忘れると、commit 時に sqlx のマクロが DB に接続しようとして落ちます。
- `Cargo.toml` の `[workspace.lints.clippy]`: web-game の `await_holding_lock`・`await_holding_refcell_ref` は game に既にあります。

各 leaf は自己完結し、製品 source・fixture・cache は配布しません。
コピー先と既存ファイル保護の手順は leaf README を参照してください。
macOS 実検証が対象で、Windows/Linux native 検証は未実施です。

各 leaf の README に全配布ファイルとコピー先、手動 check、任意 Git フックの
有効化手順があります。コピーだけで hooksPath を変更しません。既存フックを
読み取り確認し、変更の別承認後のみ project-local に有効化します。
保守 suite は repository root の `pnpm test:native:static` と `test:native:rust-game` から明示実行します。
未実行 native suite は既存 TypeScript suite の成功と分けて記録します。
