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

---
## [2026-06-12] 修正指示 #3 ── 症例詳細画面の候補点キャンバス表示（横伸び）の再修正

### 改修の背景・目的
修正指示 #2（実行#3, commit 4556276）で候補点キャンバスの横伸び対策として `canvas.style.aspectRatio` を追加したが、実機確認で依然として画像が横に伸びて表示される問題が再現した。

原因調査の結果、`templates/case_detail.html` の `<canvas id="annotation-canvas">` 要素に
- `class="w-full"`（Tailwindの`width:100%`、幅が常に固定値）
- インライン `style="max-height: 480px;"`（`static/css/style.css` の `max-height: min(70vh, 640px)` よりCSS優先度が高く、高さが480pxに固定される）

が指定されており、幅・高さの両方が固定値（かつ元画像のアスペクト比と一致しない値）になっていた。`canvas.style.aspectRatio` は幅・高さのいずれかが`auto`の場合にのみ作用するため、この状態では効果がなく、canvasに描画されたビットマップが固定ボックスに引き伸ばされて表示されていた。

### 影響範囲
- 対象ファイル:
  - `templates/case_detail.html`
  - `static/css/style.css`
- 影響する既存機能:
  - 症例詳細画面（`/cases/<case_id>`）のキャンバス表示サイズ・見た目のみ。座標データ（`x_ratio`/`y_ratio`/`radius_ratio`）やDB保存内容、クリック・ドラッグでの点編集ロジック（`canvasCoords()`は`getBoundingClientRect()`基準のため影響なし）には影響しない
- DB スキーマ変更: なし

### 修正内容詳細
1. `templates/case_detail.html` の `<canvas id="annotation-canvas">` から
   - `class="w-full border rounded-lg bg-slate-900"` → `class="border rounded-lg bg-slate-900"`（`w-full`を削除）
   - インライン `style="max-height: 480px;"` を削除

2. `static/css/style.css` の `#annotation-canvas` ルールを以下に変更する：
   ```css
   #annotation-canvas {
     display: block;
     width: auto;
     height: auto;
     max-width: 100%;
     max-height: min(70vh, 640px);
     cursor: crosshair;
   }
   ```
   （`cursor: crosshair;` は既存指定を維持）

3. `static/js/case_detail.js` の `loadImage()` 内の `canvas.style.aspectRatio = ...` 設定はそのまま残す（canvasの内在アスペクト比（`canvas.width`/`canvas.height`）と一致するため無害）。

### 注意事項
- 上記変更後、canvasは「元画像の解像度（アスペクト比）を基準に、コンテナ幅と `min(70vh, 640px)` の高さ制約の両方を満たす最大サイズ」に自動調整される（`<img>` に `max-width:100%` を指定した場合と同様の挙動）。
- ブラウザのキャッシュにより変更が反映されない場合があるため、動作確認時はハード再読み込み（Ctrl+Shift+R）を行うこと。
- 修正後、縦長・横長・正方形など複数のアスペクト比の症例画像で、画像が伸縮せず正しい比率で表示されること、および点のドラッグ編集が正しく動作することを確認すること。
---

---
## [2026-06-12] 修正指示 #4 ── AI解析のグリッド方式による所見位置特定の改善（Stage 1：実験的）

### 改修の背景・目的
AIの解析結果（候補点の円）が、AI自身の「理由」欄の説明と一致しない位置に表示される事例が確認された
（例: 「中央部に濃い酢酸白色上皮」と記載されているのに、円は画面下端付近に表示される）。

コード調査の結果、座標変換ロジック（`x_ratio`/`y_ratio` → ピクセル変換）やプロンプトの座標系定義
（左上(0,0)・右下(1,1)）に誤りはなく、GPT-4o等のVLM自体が連続値の座標（x_ratio/y_ratio）を
正確に出力できないという、視覚的グラウンディング（visual grounding）の限界が原因と考えられる。

対策として、AIに送信する画像に4列×3行のグリッド線とセルラベル（A1〜C4）を重ね描きし、
所見位置を「連続値の座標」ではなく「最も近いセルのラベル」で回答させる（Set-of-Markプロンプティング）。
連続値を当てる代わりに選択肢から選ぶ形式にすることで、精度向上を狙う。

また、引きで撮影された画像（クスコ・腟粘膜が写り込み、子宮頸部が画像の一部にしか写っていない）への
将来対応（Stage 2: 子宮頸部部分を切り出して再解析）に向けて、AIに「子宮頸部が写っている範囲」を
グリッドセルのリストとして回答させ、その推定結果を画面上で確認できるようにする。

### 影響範囲
- 対象ファイル:
  - `inference/prompts.py`
  - `inference/vlm.py`
- 影響する既存機能:
  - AI解析結果（`candidates`の`x_ratio`/`y_ratio`の算出方法）のみ。値の範囲・型・DB保存ロジック・
    フロントエンドの描画ロジックには変更なし
  - `overall_comment`に、AIが推定した子宮頸部範囲の参考情報（例:
    「（AI推定: 子宮頸部はグリッド B2・B3・C2・C3 付近）」）が追記され、症例詳細画面に表示される
  - `inference/dummy.py`（Demoプロバイダー）・`models/annotation.py`・DBスキーマ・既存の手動追加点・
    承認済みデータには影響しない
- DB スキーマ変更: なし

### 修正内容詳細

1. `inference/prompts.py`
   - `SYSTEM_PROMPT` の「## 座標」セクションを、グリッドセル参照方式に変更する：
     - 画像に4列×3行のグリッド線とラベル（行: A〜C・列: 1〜4、例 "B2"）が重ねて表示されている旨を説明
     - 各所見について、中心位置に最も近いセルを `grid_cell`（例: "B2"）として回答するよう指示
     - `radius_ratio` の説明（限局: 0.03〜0.06／広範囲: 0.08〜0.15）は変更なしで維持
   - `SYSTEM_PROMPT` に「## 子宮頸部の範囲」セクションを追加し、子宮頸部・腟円蓋が写っている
     グリッドセルをリスト（`cervix_cells`、例: `["B2","B3","C2","C3"]`）として回答するよう指示する
   - `ANALYSIS_PROMPT` のJSON出力例を、`"x_ratio": 0.55, "y_ratio": 0.45` から `"grid_cell": "B2"` に変更し、
     トップレベルに `"cervix_cells": ["B2","B3","C2","C3"]` を追加する

2. `inference/vlm.py`
   - グリッド定数 `GRID_COLS = 4`, `GRID_ROWS = 3`, `_ROW_LABELS = "ABC"` を追加
   - `_draw_grid_overlay(image)` 関数を追加：画像のコピーに4列×3行のグリッド線とセルラベル（A1〜C4）を
     描き込んで返す（線・ラベルの色はシアン系、線幅・フォントサイズは画像サイズに比例）
   - `_grid_cell_to_ratio(cell)` 関数を追加：`"B2"` のようなセルラベル文字列を `(x_ratio, y_ratio)`
     （セル中心の比率）に変換する。不正な形式・範囲外の場合は `None` を返す
   - `_format_cervix_note(cells)` 関数を追加：`cervix_cells` のリストを画面表示用のテキスト
     （例: 「（AI推定: 子宮頸部はグリッド B2・B3・C2・C3 付近）」）に整形する。不正・空の場合は空文字を返す
   - `_dict_to_result()` を変更：
     - 各候補の `grid_cell` を `_grid_cell_to_ratio()` で変換できた場合はその値を `x_ratio`/`y_ratio` に使用し、
       変換できない場合は従来通り `item.get("x_ratio", 0.5)` / `item.get("y_ratio", 0.5)` にフォールバックする
     - トップレベルの `cervix_cells` を `_format_cervix_note()` で整形し、空でなければ `overall_comment` に
       追記する（`logger.info()` でも推定結果をログ出力する）
   - `OpenAIAnnotationInference.analyze()` / `AnthropicAnnotationInference.analyze()` の両方で、
     `_image_to_base64(image)` を `_image_to_base64(_draw_grid_overlay(image))` に変更し、
     グリッド付き画像をAIに送信する

### 注意事項
- 本機能は実験的なものであり、効果（候補点の位置精度・子宮頸部範囲推定の精度）を実症例で確認すること
- AIが `grid_cell`/`cervix_cells` を返さない、または不正な形式で返した場合は、`grid_cell` は中心(0.5, 0.5)へ
  フォールバックし、`cervix_cells` の表示は省略される（エラーにはならない）
- `overall_comment` への子宮頸部範囲の追記は検証用の一時的な表示であり、Stage 2実装時、または
  効果が見られない場合は削除を検討する
- グリッド線・ラベルはAIに送信する画像のコピーにのみ描き込まれ、症例詳細画面に表示される画像
  （`static/uploads/`配下の元画像）には影響しない
- グリッド線の色（シアン）・太さで視認性に問題があれば、`_draw_grid_overlay()` 内の色・線幅を調整すること
- フォント読み込みに失敗した場合（`arial.ttf`が見つからない等）は、PILのデフォルトフォントに
  フォールバックするため、ラベルが小さく表示される可能性がある
---
