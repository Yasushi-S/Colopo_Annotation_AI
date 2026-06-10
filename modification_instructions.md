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

---
## [2026-06-10] 修正指示 #2 ── 症例詳細画面の候補点キャンバス表示不具合の修正

### 改修の背景・目的
症例詳細画面（`/cases/<case_id>`）で以下2点の表示不具合が確認された。

1. **候補点の円が薄くて見えにくい**
   - `static/js/case_detail.js` の `drawCanvas()` で円の線幅を `ctx.lineWidth = isSelected ? 4 : 2;` と固定値（canvas内部解像度基準のpx）で描画している。
   - canvasの内部解像度は元画像の解像度（`canvas.width = img.naturalWidth` 等）になる一方、画面表示はCSSで縮小される（`#annotation-canvas { max-height: min(70vh, 640px); }` + Tailwindの`w-full`）。
   - 元画像の解像度が大きいほど、線幅2pxが表示上1px未満に縮小され、円・中心点・rank番号が非常に薄く・小さく見えてしまう。

2. **画像が元画像に比べて横に伸びて表示される**
   - `loadImage()` で canvasの内部解像度（`canvas.width`/`canvas.height`）は元画像のアスペクト比に設定されるが、CSS側（`width:100%` + `max-height: min(70vh, 640px)`）には**表示box自体のアスペクト比を元画像に合わせる指定がない**。
   - そのため表示box（横幅100%・高さ最大640px）のアスペクト比と、canvas内部ピクセルのアスペクト比が一致せず、描画内容が横方向に引き伸ばされて表示される。

### 影響範囲
- 対象ファイル: `static/js/case_detail.js`
- 影響する既存機能:
  - 候補点（AI解析結果・手動追加点）の表示の見た目のみ。座標データ（`x_ratio`/`y_ratio`/`radius_ratio`）やDB保存内容には影響しない
  - クリック・ドラッグでの点の追加・移動・リサイズ判定（`canvasCoords()`/`hitTest()`）は、表示boxのアスペクト比修正後も `canvas.getBoundingClientRect()` を用いた比率計算のため、引き続き正しく動作する見込み
- DB スキーマ変更: なし

### 修正内容詳細
1. `loadImage()` の画像読み込み完了時（`img.onload`）に、
   `canvas.style.aspectRatio = img.naturalWidth + " / " + img.naturalHeight;`
   を追加し、canvasの表示box自体のアスペクト比を元画像に一致させる（横伸び解消）。

2. `drawCanvas()` 内に、canvas内部解像度に応じたスケール係数
   `const scale = Math.max(1, canvas.width / 1000);`
   を追加し、以下の描画サイズに乗算する：
   - 円の線幅: `ctx.lineWidth = (isSelected ? 4 : 2) * scale;`
   - 中心点の半径: `ctx.arc(cx, cy, 4 * scale, 0, Math.PI * 2)`
   - rank番号のフォントサイズ・描画位置: `"bold " + (14 * scale) + "px sans-serif"`、`cx - 4 * scale`、`cy - r - 6 * scale`

   解像度1000px以下の画像では従来どおり（scale=1）の見た目を維持し、それ以上の解像度では比例して太く・大きく描画する。

### 注意事項
- 採用未確定（`doctor_confirmed = 0`）の点を半透明（`alpha = 0.4`）で表示する既存仕様は変更しない。
- ブラウザのキャッシュにより `case_detail.js` の変更が反映されない場合があるため、動作確認時はハード再読み込み（Ctrl+Shift+R等）を行うこと。
- 修正後、解像度の異なる複数の症例画像で「円の視認性」「画像のアスペクト比」「点のドラッグ編集」が正しく動作することを確認すること。
---
