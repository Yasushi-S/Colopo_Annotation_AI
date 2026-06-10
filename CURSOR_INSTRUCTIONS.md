# CURSOR_INSTRUCTIONS.md — Colpo Annotation AI 新規開発発注書

作成日: 2026-06-10
作成者: Claude Code（ヒアリング・設計）
コーディング担当: Cursor

> 本書は `Colpo Annotation AI 設計書`（2026-06-10、ユーザー作成）に基づき、Version 1 の発注内容を具体化したものです。
> Version 1 では設計書 Version1（手動アノテーション基盤）と Version2（AI候補点提示）を統合し、**AIが候補点を提示し、医師が修正・承認する**所まで実装します。

---

## 1. アプリ概要・目的

酢酸加工後のコルポスコピー静止画像に対し、Vision LLM（GPT-4o / Claude / Demo）が生検候補点（最大3点、座標・半径・所見ラベル・confidence・理由）を自動推定し、画像上に円形マーキングとして提示する。

医師は提示された候補点を確認し、**位置・半径・ラベル・所見・コメント・採否を自由に修正**できる。「承認」操作を行ったデータのみ、症例情報（細胞診・HPV・病理結果等）と紐付けて保存し、将来の検出モデル学習用データとして蓄積する。

- 本アプリは**診断確定AIではない**
- 最終判断は必ず医師が行う
- AIの候補点はあくまで「たたき台」であり、医師による修正を前提とする

---

## 2. 主な利用者・利用シーン

- 産婦人科医（コルポスコピー専門）
- 院内ネットワーク内の複数端末から Google Chrome でアクセス
- 1症例ずつ、検査直後または後日まとめてアノテーション作業を行う

---

## 3. 機能一覧（Version 1）

1. **症例一覧**: 登録済み症例の一覧表示（検査日・細胞診結果・HPV結果・ステータス）
2. **新規症例登録**: 画像アップロード＋症例メタデータ入力
3. **AI解析実行**: Vision LLM（GPT-4o / Claude / Demo）が候補点（最大3点）を自動生成
4. **アノテーション編集**:
   - 候補点の位置（ドラッグ）・半径（リサイズ）の変更
   - 候補点の追加（手動）・削除
   - 所見ラベル・所見タグ・医師コメントの編集
   - 各点の採用／不採用フラグ
5. **承認保存**: 承認時点のアノテーション状態をDBに保存し、アノテーション付き画像を生成・保存
6. **症例詳細の再閲覧・再編集**: 一度保存した症例も後から開いて編集・再承認できる

### Version 1 の範囲外（将来バージョン）

- 病理結果入力専用画面（設計書 Version3） — ただしDBカラムは本バージョンで先行作成する
- YOLO/COCO形式エクスポート（設計書 Version4）
- SAM2による補助マスク生成（設計書 Version5）
- 認証機能（院内ネットワーク限定のため、現時点では未実装。現行 Colpo_AI と同様の扱い）

---

## 4. 画面構成

### 4.1 症例一覧画面（`GET /`）

表示項目（テーブル形式）:

| 列 | 内容 |
|---|---|
| 症例ID | `case_id`（例: `COLPO_000001`） |
| 検査日 | `exam_date` |
| 画像種別 | `image_type`（酢酸後／ヨード後／通常光） |
| 細胞診結果 | `cytology_result` |
| HPV結果 | `hpv_result` |
| ステータス | `uploaded`（未解析）／`ai_analyzed`（AI解析済み・未承認）／`approved`（承認済み） |
| 操作 | 「開く」ボタン → `/cases/<case_id>` |

右上に「新規症例登録」ボタン → `/cases/new`

### 4.2 新規症例登録画面（`GET /cases/new`）

入力フォーム:

- 画像ファイル（PNG/JPG、必須）
- 患者ID（匿名化ID、テキスト、必須）
- 検査日（日付、デフォルト: 当日）
- 画像種別（セレクト: 酢酸後 `acetowhite` ／ ヨード後 `iodine` ／ 通常光 `white_light`、デフォルト: 酢酸後）
- 細胞診結果（テキスト、任意）
- HPV結果（テキスト、任意）
- メモ（テキストエリア、任意）

「保存して解析へ」ボタン → `POST /cases` → 症例レコード作成・画像保存 → `/cases/<case_id>` へリダイレクト

### 4.3 症例詳細・AI解析・アノテーション編集画面（`GET /cases/<case_id>`）

レイアウトは現行 Colpo_AI の左右2ペイン構成を踏襲する。

**左ペイン: 画像 + Canvas アノテーション**

- 元画像を `<canvas>` に描画
- 候補点を円として描画（中心 `x_ratio×W, y_ratio×H`、半径 `radius_ratio×W`）
  - `rank=1` → 赤 `#ef4444`
  - `rank=2` → 黄 `#eab308`
  - `rank=3` → 青 `#3b82f6`
  - 手動追加点（rank未設定）→ 灰 `#94a3b8`
  - `doctor_confirmed=false` の点は半透明（不採用であることが視覚的にわかるようにする）
- 操作:
  - 円の中心付近をドラッグ → 位置移動（`x_ratio`, `y_ratio` 更新）
  - 円周付近をドラッグ → 半径変更（`radius_ratio` 更新、最小値 `0.02`）
  - 「点を追加」モードON → 画像クリックで新規点を追加（初期値: `radius_ratio=0.05`, `label="LSIL_like"`, `findings=[]`, `source="manual"`, `ai_confidence=null`, `doctor_confirmed=true`）
  - 点をクリックして選択 → 右ペインの編集フォームに該当データを表示
- ツールバー:
  - プロバイダー選択（GPT-4o / Claude / Demo） — 現行 Colpo_AI の `#provider-select` と同一仕様（`/api/provider`, `/api/provider/set` を流用）
  - 「AI解析実行」ボタン
  - 「点を追加」トグルボタン

**右ペイン: 候補点リスト + 症例情報**

- 候補点カード一覧（rank順）:
  - rankバッジ（色分け）
  - `label`（セレクト、5択）
  - `findings`（チェックボックス、9項目、複数選択）
  - `ai_confidence`（AI由来のみ表示、手動追加は「手動追加」と表示）
  - `reason`（テキストエリア、編集可）
  - `doctor_comment`（テキストエリア）
  - 採用／不採用トグル（`doctor_confirmed`）
  - 削除ボタン
- 症例情報セクション（`cytology_result`, `hpv_result`, `memo` を表示・編集可能。再保存時にDB更新）
- 「承認して保存」ボタン → 現在のアノテーション状態をDB保存 + canvasを画像化して `annotated.<ext>` として保存 + `case.status = "approved"`

---

## 5. データ構造（SQLite）

DBファイル: `data/colpo_annotation.db`（`.gitignore` 対象）

```sql
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT UNIQUE NOT NULL,              -- 例: "COLPO_000001"
    patient_id TEXT NOT NULL,                  -- 匿名化ID（医師が入力）
    exam_date TEXT NOT NULL,                   -- "YYYY-MM-DD"
    image_type TEXT NOT NULL,                  -- acetowhite / iodine / white_light
    cytology_result TEXT,
    hpv_result TEXT,
    biopsy_result TEXT,                        -- Version3で入力画面を追加予定。カラムのみ先行作成
    final_diagnosis TEXT,                      -- NILM/LSIL/HSIL/AIS/SCC/その他。Version3で入力予定
    memo TEXT,
    original_image_path TEXT NOT NULL,         -- "static/cases/<case_id>/original.<ext>"
    annotated_image_path TEXT,                 -- 承認後に設定。"static/cases/<case_id>/annotated.<ext>"
    image_width INTEGER NOT NULL,
    image_height INTEGER NOT NULL,
    ai_provider TEXT,                          -- 直近のAI解析に使用したプロバイダー
    status TEXT NOT NULL DEFAULT 'uploaded',   -- uploaded / ai_analyzed / approved
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    point_id INTEGER NOT NULL,                 -- 症例内の通し番号（1から採番）
    rank INTEGER,                              -- 1/2/3。手動追加点はNULL可
    x_ratio REAL NOT NULL,                     -- 0.0-1.0（画像左上が原点）
    y_ratio REAL NOT NULL,
    radius_ratio REAL NOT NULL,                -- 画像幅に対する比率
    label TEXT NOT NULL,                       -- LSIL_like / HSIL_suspicious / cancer_suspicious / inflammation_like / metaplasia_like
    findings TEXT NOT NULL DEFAULT '[]',       -- JSON配列文字列。例: '["dense_acetowhite","sharp_margin"]'
    ai_confidence REAL,                        -- AI由来のみ。手動追加はNULL
    reason TEXT,
    source TEXT NOT NULL,                      -- 'ai' または 'manual'
    doctor_confirmed INTEGER NOT NULL DEFAULT 1,  -- 採用フラグ（0/1）
    doctor_comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_annotations_case_id ON annotations(case_id);
```

### 採番ルール

- `case_id`: `cases` テーブルの最大 `id` + 1 を `COLPO_%06d` 形式で生成（例: `COLPO_000001`）
- `point_id`: 症例内で `annotations` の最大 `point_id` + 1（削除されても再利用しない）

### AI再解析時の扱い

「AI解析実行」を再度押した場合:
- `source='ai'` かつ `doctor_confirmed=0`（不採用）の既存annotationsは削除
- `source='ai'` かつ `doctor_confirmed=1`（採用済み）および `source='manual'` の annotations はそのまま残す
- 新しい候補点を追加（`point_id` は採番ルールに従う）
- `case.ai_provider` を今回使用したプロバイダーで更新、`case.status` を `ai_analyzed` に更新（`approved` だった場合は `ai_analyzed` に戻す）

---

## 6. AI推論仕様

### 6.1 既存資産の流用

以下は現行 `Colpo_AI`（`C:\Users\shita\github\Colpo_AI\`）のパターンをそのまま踏襲すること:

- `app.py` の `_engine_cache` / `_current_provider` / `_get_engine()` によるプロバイダー切替パターン
- `/api/provider`（GET）/ `/api/provider/set`（POST）エンドポイント仕様
- `inference/base.py` の抽象クラス構成
- `inference/vlm.py` の `_image_to_base64()` / `_extract_json()` ユーティリティ（そのまま流用可）

ただし出力スキーマ・プロンプト・dataclass は本書の内容に置き換える。

### 6.2 データクラス（`models/annotation.py`）

```python
from dataclasses import dataclass, field


@dataclass
class AnnotationCandidate:
    rank: int | None          # 1, 2, 3 のいずれか（AI由来）。手動追加時はNone
    x_ratio: float            # 0.0-1.0
    y_ratio: float            # 0.0-1.0
    radius_ratio: float       # 画像幅に対する比率
    label: str                # LSIL_like / HSIL_suspicious / cancer_suspicious / inflammation_like / metaplasia_like
    findings: list[str]       # 所見タグのリスト（後述9項目から）
    confidence: float | None  # AI由来のみ。手動追加はNone
    reason: str


@dataclass
class AnnotationResult:
    candidates: list[AnnotationCandidate]
    overall_comment: str = ""
```

### 6.3 抽象インターフェース（`inference/base.py`）

```python
class AbstractAnnotationInference(ABC):
    @abstractmethod
    def analyze(self, image: Image.Image) -> AnnotationResult:
        ...
```

`OpenAIAnnotationInference` / `AnthropicAnnotationInference` / `DummyAnnotationInference` を実装する。

### 6.4 ラベル体系

#### 所見タグ（`findings`、複数選択可）

| タグ | 臨床的意味 |
|---|---|
| `dense_acetowhite` | 境界明瞭で濃い酢酸白色上皮（Major変化） |
| `sharp_margin` | 鋭い境界・内境界(inner border sign)・隆起境界(ridge sign) |
| `coarse_mosaic` | 粗大モザイクパターン（Major変化） |
| `coarse_punctation` | 粗大点状血管（Major変化） |
| `atypical_vessel` | 異型血管（corkscrew/hairpin/不規則分岐。浸潤疑いのサイン） |
| `glandular_involvement` | 腺開口部・頸管内への病変波及疑い |
| `suspicious_invasion` | 易出血性・不整潰瘍など浸潤を疑う所見 |
| `inflammation_like` | 炎症性変化（偽陽性所見の可能性） |
| `immature_metaplasia_like` | 未熟化生様の変化（偽陽性所見の可能性） |

#### 総合分類ラベル（`label`、1点につき1つ）

| ラベル | 臨床的意味 |
|---|---|
| `LSIL_like` | Minor変化主体（薄い白色上皮・fine mosaic・fine punctation）。CIN1相当を示唆 |
| `HSIL_suspicious` | Major変化を含む。CIN2/3相当を示唆 |
| `cancer_suspicious` | 異型血管・易出血・不整潰瘍など浸潤を疑う所見を含む |
| `inflammation_like` | 炎症性変化が主体で腫瘍性変化に乏しい |
| `metaplasia_like` | 未熟化生など生理的変化が主体で腫瘍性変化に乏しい |

迷う場合はより上位のリスク（`HSIL_suspicious`側）を選択する（見逃しは過剰診断より危険）— 現行 Colpo_AI のプロンプト方針を踏襲。

### 6.5 プロンプト（`inference/prompts.py`）

```python
SYSTEM_PROMPT = """
あなたはコルポスコピー読影の専門医アシスタントです。
提示された画像は酢酸塗布後に撮影されたコルポスコピー画像です。

## 役割
- 生検すべき部位の「候補点」を医師に提示する
- 確定診断は行わない。最終判断・最終的な点の採否は医師が行う
- 見逃しを避けるため、わずかでも所見があれば候補点として提示すること

## 候補点の数
- 最大3点（rank 1〜3）。rank 1（赤）が最も生検優先度の高い部位
- 所見が乏しい場合も、最も注視すべき部位を最低1点は提示すること
- 明らかに正常で所見が皆無の場合のみ candidates を空配列にしてよい

## 所見タグ（findings、複数選択可）
- dense_acetowhite: 境界明瞭で濃い酢酸白色上皮（Major変化）
- sharp_margin: 鋭い境界・内境界(inner border sign)・隆起境界(ridge sign)
- coarse_mosaic: 粗大モザイクパターン（Major変化）
- coarse_punctation: 粗大点状血管（Major変化）
- atypical_vessel: 異型血管（corkscrew/hairpin/不規則分岐。浸潤疑いのサイン）
- glandular_involvement: 腺開口部・頸管内への病変波及疑い
- suspicious_invasion: 易出血性・不整潰瘍など浸潤を疑う所見
- inflammation_like: 炎症性変化（偽陽性所見の可能性を考慮）
- immature_metaplasia_like: 未熟化生様の変化（偽陽性所見の可能性を考慮）

## 総合分類ラベル（label、1点につき1つ）
- LSIL_like: Minor変化主体。CIN1相当を示唆
- HSIL_suspicious: Major変化を含む。CIN2/3相当を示唆
- cancer_suspicious: 異型血管・易出血・不整潰瘍など浸潤を疑う所見を含む
- inflammation_like: 炎症性変化が主体で腫瘍性変化に乏しい
- metaplasia_like: 未熟化生など生理的変化が主体で腫瘍性変化に乏しい

迷った場合はより上位のリスク（HSIL_suspicious側）を選択すること（見逃しは過剰診断より危険）。

## 座標
- x_ratio, y_ratio: 画像左上を(0,0)、右下を(1,1)とした所見中心位置の比率（0.0-1.0）
- radius_ratio: 所見の広がりを画像幅に対する比率で示す
  - 限局した所見: 0.03〜0.06
  - 広範囲な所見: 0.08〜0.15

## 限界の認識
- 画像中の腟壁・腟円蓋と子宮頸部の境界を完全に区別できない可能性がある
- 座標・範囲は目安であり、医師が後で位置・範囲を修正することを前提とする
"""

ANALYSIS_PROMPT = """
この酢酸塗布後コルポスコピー画像を解析し、生検候補点を最大3点抽出してください。

以下のJSONフォーマットのみで回答してください。必ず ```json ... ``` で囲んでください。

```json
{
  "candidates": [
    {
      "rank": 1,
      "x_ratio": 0.55,
      "y_ratio": 0.45,
      "radius_ratio": 0.06,
      "label": "LSIL_like または HSIL_suspicious または cancer_suspicious または inflammation_like または metaplasia_like",
      "findings": ["dense_acetowhite", "sharp_margin"],
      "confidence": 0.82,
      "reason": "この部位を候補とする理由（2〜3文）"
    }
  ],
  "overall_comment": "画像全体・画質に関するコメント（任意、1〜2文）"
}
```

所見が全くない場合は "candidates": [] としてください。
"""
```

`temperature=0.2` を維持すること（現行 Colpo_AI と同じ理由: 医療補助用途のため再現性を優先）。

---

## 7. ファイル構成

```
colpo_annotation_ai/
├── app.py
├── config.py
├── db.py                       # SQLite接続・初期化（CREATE TABLE実行）
├── models/
│   ├── __init__.py
│   └── annotation.py           # AnnotationCandidate, AnnotationResult
├── inference/
│   ├── __init__.py
│   ├── base.py                 # AbstractAnnotationInference
│   ├── dummy.py                # DummyAnnotationInference
│   ├── prompts.py              # SYSTEM_PROMPT, ANALYSIS_PROMPT
│   └── vlm.py                  # OpenAIAnnotationInference, AnthropicAnnotationInference
├── templates/
│   ├── base.html
│   ├── case_list.html
│   ├── case_new.html
│   └── case_detail.html
├── static/
│   ├── css/style.css
│   ├── js/
│   │   ├── case_list.js
│   │   ├── case_new.js
│   │   └── case_detail.js      # canvas編集ロジック
│   └── cases/                  # 症例ごとの画像保存先（.gitignore対象、起動時に自動作成）
├── data/                        # SQLite DB格納先（.gitignore対象、起動時に自動作成）
├── requirements.txt
├── .env.example
├── .gitignore
├── start_app.bat
├── CLAUDE.md                    # 作成済み
├── CURSOR_INSTRUCTIONS.md       # 本書（作成済み）
├── modification_instructions.md
├── modification_log.md
└── .cursor/
    └── rules
```

### 画像ストレージ

- `static/cases/<case_id>/original.<ext>`: アップロード元画像
- `static/cases/<case_id>/annotated.<ext>`: 承認時にcanvasから生成した画像（クライアント側で `canvas.toDataURL()` → base64 で `/api/cases/<case_id>/approve` にPOST → サーバー側でデコードして保存）

---

## 8. API エンドポイント一覧

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/` | 症例一覧画面 |
| GET | `/cases/new` | 新規症例登録フォーム画面 |
| POST | `/cases` | 症例作成（multipart: 画像＋フォーム）。成功後 `/cases/<case_id>` へリダイレクト |
| GET | `/cases/<case_id>` | 症例詳細・編集画面 |
| GET | `/api/cases/<case_id>` | 症例情報＋annotations一覧をJSONで返す |
| PATCH | `/api/cases/<case_id>` | 症例メタ情報更新（cytology_result, hpv_result, memo） |
| POST | `/api/cases/<case_id>/analyze` | AI解析実行。body: `{"provider": "openai\|anthropic\|dummy"}` |
| POST | `/api/cases/<case_id>/annotations` | annotation手動追加 |
| PATCH | `/api/cases/<case_id>/annotations/<id>` | annotation更新（位置・半径・label・findings・comment・doctor_confirmed） |
| DELETE | `/api/cases/<case_id>/annotations/<id>` | annotation削除 |
| POST | `/api/cases/<case_id>/approve` | 承認。body: `{"annotated_image": "data:image/jpeg;base64,..."}` |
| GET | `/api/provider` | 現在のプロバイダー取得（現行Colpo_AIと同一仕様） |
| POST | `/api/provider/set` | プロバイダー切替（現行Colpo_AIと同一仕様） |

---

## 9. セットアップ手順

1. `python -m venv venv`
2. `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. `.env.example` を `.env` にコピーし、`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `SECRET_KEY` を設定
5. 初回起動時に `db.py` の `init_db()` が `data/colpo_annotation.db` を自動作成（テーブルが存在しなければ作成）
6. `python app.py` で起動 → `http://<ホストPCのIP>:50012/`

### requirements.txt

```
flask>=3.0
pillow>=10.0
python-dotenv>=1.0
openai>=1.30
anthropic>=0.28
```

（OpenCV・SAM2は将来バージョンで必要になった時点で追加する。Version 1では不要）

### .env.example

```
VLM_PROVIDER=dummy
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
VLM_FALLBACK_TO_DUMMY=true
SECRET_KEY=change-me-in-.env
```

### config.py

現行 Colpo_AI の `config.py` と同様の構成とする（`UPLOAD_FOLDER` の代わりに `CASES_FOLDER = "static/cases"`、`DB_PATH = "data/colpo_annotation.db"` を追加）。

---

## 10. 必須ファイルの作成指示

### .gitignore

```
venv/
__pycache__/
*.pyc
.env
*.db
instance/
.DS_Store
static/cases/
data/
```

### start_app.bat

```bat
@echo off
cd /d "%~dp0"
call "%~dp0venv\Scripts\activate.bat"
python app.py
```

### app.py 末尾

```python
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=50012)
```

### .cursor/rules

```
# Cursor ルール（colpo_annotation_ai）

## 基本方針
- CURSOR_INSTRUCTIONS.md（初回実装）/ modification_instructions.md（以降の修正）の指示に従い、忠実にコーディングを行う
- DB スキーマ・既存データへの変更を伴う場合は、必ず作業前にユーザーに確認を取る
- コーディング完了後、modification_log.md の末尾に実施内容を追記する（新規ファイル作成禁止）
- 修正対象ファイルを必ず読んでから変更する（読まずに変更禁止）
- 指示書に記載のない変更（リファクタリング・コメント追加等）は行わない
- SQL クエリはパラメータバインディングを使用（f-string での SQL 組み立て禁止）
- シークレットキー・API キーをコードにハードコードしない（必ず .env から読み込む）
- Claude Code のレビューが完了するまで git commit しない

## 実行記録フォーマット（modification_log.md）
---
## [YYYY-MM-DD] 実行 #N ── <一行要約>

### 対応した指示
- （CURSOR_INSTRUCTIONS.md または modification_instructions.md の #N）

### 実施内容詳細
（実際に行った変更を箇条書きで記載）

### 確認事項・備考
（問題があれば記載、なければ「なし」）
---

## メインファイル
- app.py（Flask アプリ本体）

## ドキュメント
- CURSOR_INSTRUCTIONS.md（新規開発発注書）
- modification_instructions.md（修正指示）
- modification_log.md（実行記録）
```

### modification_instructions.md / modification_log.md

それぞれ以下のヘッダーのみを持つ空ファイルとして作成する（以降の修正で末尾追記していく）:

```
# modification_instructions.md — colpo_annotation_ai 修正指示書

<!-- Claude Code はこのファイルの末尾に追記すること（新規ファイル作成禁止） -->
```

```
# modification_log.md — colpo_annotation_ai 変更履歴

<!-- Cursor はコーディング完了後、このファイルの末尾に実施内容を追記すること（新規ファイル作成禁止） -->
```

初回実装完了時、`modification_log.md` に「実行 #1 ── CURSOR_INSTRUCTIONS.md に基づく Version 1 実装」として記録すること。

---

## 11. タスクスケジューラ登録手順（参考・本番運用時）

- トリガー: コンピューターの起動時
- 操作: `start_app.bat` を実行
- 全般設定: 最上位の特権で実行にチェック、ユーザーがログオンしていなくても実行

---

## 12. セキュリティ要件（院内ネットワーク限定アプリ）

- `SECRET_KEY` は `.env` で管理し、コードにハードコードしない
- `app.run(debug=False, host="0.0.0.0", port=50012)`。`0.0.0.0` バインドのため、ファイアウォールで外部（インターネット）アクセスを遮断すること（運用者側の対応。発注書に明記のみ）
- SQLite操作は必ずパラメータバインディング（`?`プレースホルダ）を使用し、文字列結合でSQLを組み立てない
- アップロード画像は拡張子（png/jpg/jpeg）とPillowでの再読み込み検証を行い、`static/cases/<case_id>/` 配下に保存する
- 操作ログ: 「承認」操作が行われた際、`case_id` ・タイムスタンプ・使用端末のIPアドレス（`request.remote_addr`）をログ出力する（認証機構がないため、ユーザー識別はIPアドレスで代替）
- 患者の実名・カルテ番号等の個人情報は入力させない（`patient_id` は匿名化IDのみ）

---

## 13. 注意事項（デグレード防止・実装上の留意点）

1. **VLMの座標精度には限界がある**ことを前提とする。AIが返す `x_ratio`/`y_ratio`/`radius_ratio` は「たたき台」であり、医師が必ず位置・範囲を確認・修正する前提のUIとすること（ドラッグ操作を最優先で実装すること）。
2. **既存 `Colpo_AI` のコードは変更しない**。本プロジェクトは別リポジトリ・別ディレクトリの新規開発であり、`Colpo_AI` から参照・流用するのはコードパターンのみ（コピーして適応する）。
3. `findings` カラムはSQLiteにJSON文字列として保存し、Python側で `json.loads`/`json.dumps` する。直接SQLに配列を埋め込まない。
4. AI再解析時の既存annotations取り扱い（5章「AI再解析時の扱い」）を必ず実装すること。これを誤ると医師が一度承認した点が消える事故につながる。
5. `static/cases/` と `data/` は初回起動時に存在しなければ自動作成する（`os.makedirs(..., exist_ok=True)`）。
6. 承認画像生成（`annotated.<ext>`）はクライアント側 `canvas.toDataURL()` を用い、サーバー側で重複した描画ロジックを持たない。
7. 実装完了後、`modification_log.md` の末尾に実施内容を追記すること。

---

## 14. ポート番号

`50012`（`port_list.txt` に登録予定: `50012 | colpo_annotation_ai`）
