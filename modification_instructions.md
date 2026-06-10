# modification_instructions.md — colpo_annotation_ai 修正指示書

<!-- Claude Code はこのファイルの末尾に追記すること（新規ファイル作成禁止） -->

---
## [2026-06-10] 修正指示 #1 ── 承認操作の監査ログにタイムスタンプを記録する

### 改修の背景・目的
フェーズ5レビューにて、`/api/cases/<case_id>/approve` の操作ログが CURSOR_INSTRUCTIONS.md 12章のセキュリティ要件
「承認操作時に case_id・タイムスタンプ・使用端末のIPアドレスをログ出力する」を満たしていないことが判明した。
- `logging.basicConfig()` が未設定のため `logger.info(...)` はデフォルトのログレベル（WARNING）で出力されず、実質無効なコードになっている。
- 代替で出力されている `print(f"[APPROVE] ...")` にはタイムスタンプが含まれていない。

### 影響範囲
- 対象ファイル: `app.py`
- 影響する既存機能: なし（ログ出力のみの変更。APIレスポンス・DB操作には影響しない）
- DB スキーマ変更: なし

### 修正内容詳細
- `app.py` 冒頭（`logger = logging.getLogger(__name__)` の前）に
  `logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")` を追加し、
  `logger.info(...)` がタイムスタンプ付きで出力されるようにする。
- `api_approve` 内の冗長な `print(f"[APPROVE] case_id={case_id}, ip={client_ip}", flush=True)` を削除し、
  `logger.info("承認操作: case_id=%s, ip=%s", case_id, client_ip)` に一本化する。

### 注意事項
- `logging.basicConfig` の追加が、AI解析エラー時の `app.logger.error(...)` 出力など既存のログ動作に悪影響を与えないことを確認すること。
- 修正後、承認操作時にタイムスタンプ・case_id・IPアドレスを含むログが出力されることを確認すること。
---
