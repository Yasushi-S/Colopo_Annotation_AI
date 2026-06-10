import base64
import json
import logging
import os
import re
import traceback
from datetime import date

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from PIL import Image

import config
from db import get_db, init_db

app = Flask(__name__)
app.config.from_object(config)

os.makedirs(config.CASES_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
init_db()

_LABEL_MAP = {"openai": "GPT-4o", "anthropic": "Claude", "dummy": "Demo (ダミー)"}
_ALLOWED_PROVIDERS = {"openai", "anthropic", "dummy"}

_engine_cache: dict = {}
_current_provider: str = os.getenv("VLM_PROVIDER", "dummy").strip().lower()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _get_engine(provider: str):
    if provider not in _engine_cache:
        if provider == "openai":
            from inference.vlm import OpenAIAnnotationInference
            _engine_cache[provider] = OpenAIAnnotationInference()
        elif provider == "anthropic":
            from inference.vlm import AnthropicAnnotationInference
            _engine_cache[provider] = AnthropicAnnotationInference()
        else:
            from inference.dummy import DummyAnnotationInference
            _engine_cache[provider] = DummyAnnotationInference()
    return _engine_cache[provider]


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def _generate_case_id(conn) -> str:
    row = conn.execute("SELECT MAX(id) AS max_id FROM cases").fetchone()
    next_id = (row["max_id"] or 0) + 1
    return f"COLPO_{next_id:06d}"


def _next_point_id(conn, case_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(point_id) AS max_pid FROM annotations WHERE case_id = ?",
        (case_id,),
    ).fetchone()
    return (row["max_pid"] or 0) + 1


def _get_case_or_404(conn, case_id: str):
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return row


def _row_to_case_dict(row) -> dict:
    d = dict(row)
    d["image_type_label"] = config.IMAGE_TYPES.get(d["image_type"], d["image_type"])
    d["status_label"] = config.STATUS_LABELS.get(d["status"], d["status"])
    return d


def _row_to_annotation_dict(row) -> dict:
    d = dict(row)
    try:
        d["findings"] = json.loads(d["findings"] or "[]")
    except json.JSONDecodeError:
        d["findings"] = []
    d["doctor_confirmed"] = bool(d["doctor_confirmed"])
    return d


def _touch_case(conn, case_id: str) -> None:
    conn.execute(
        "UPDATE cases SET updated_at = datetime('now','localtime') WHERE case_id = ?",
        (case_id,),
    )


@app.route("/")
def case_list():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()
        cases = [_row_to_case_dict(r) for r in rows]
    return render_template("case_list.html", cases=cases)


@app.route("/cases/new")
def case_new():
    return render_template(
        "case_new.html",
        image_types=config.IMAGE_TYPES,
        today=date.today().isoformat(),
    )


@app.route("/cases", methods=["POST"])
def case_create():
    def _form_error(msg: str):
        flash(msg, "error")
        return redirect(url_for("case_new"))

    if "image" not in request.files:
        return _form_error("画像ファイルが選択されていません")

    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return _form_error("対応していないファイル形式です（PNG / JPG のみ）")

    patient_id = (request.form.get("patient_id") or "").strip()
    exam_date = (request.form.get("exam_date") or "").strip()
    image_type = (request.form.get("image_type") or "acetowhite").strip()

    if not patient_id:
        return _form_error("患者ID（匿名化ID）を入力してください")
    if not exam_date:
        return _form_error("検査日を入力してください")
    if image_type not in config.IMAGE_TYPES:
        return _form_error("画像種別が不正です")

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext == "jpeg":
        ext = "jpg"

    try:
        image = Image.open(file.stream).convert("RGB")
    except Exception:
        return _form_error("画像ファイルを読み込めませんでした")

    width, height = image.size

    with get_db() as conn:
        case_id = _generate_case_id(conn)
        case_dir = os.path.join(config.CASES_FOLDER, case_id)
        os.makedirs(case_dir, exist_ok=True)
        rel_path = f"{config.CASES_FOLDER}/{case_id}/original.{ext}"
        abs_path = os.path.join(case_dir, f"original.{ext}")
        image.save(abs_path)

        conn.execute(
            """
            INSERT INTO cases (
                case_id, patient_id, exam_date, image_type,
                cytology_result, hpv_result, memo,
                original_image_path, image_width, image_height, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded')
            """,
            (
                case_id,
                patient_id,
                exam_date,
                image_type,
                (request.form.get("cytology_result") or "").strip() or None,
                (request.form.get("hpv_result") or "").strip() or None,
                (request.form.get("memo") or "").strip() or None,
                rel_path.replace("\\", "/"),
                width,
                height,
            ),
        )

    return redirect(url_for("case_detail", case_id=case_id))


@app.route("/cases/<case_id>")
def case_detail(case_id: str):
    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return "症例が見つかりません", 404
        case = _row_to_case_dict(row)
        annotations = conn.execute(
            "SELECT * FROM annotations WHERE case_id = ? ORDER BY rank IS NULL, rank, point_id",
            (case_id,),
        ).fetchall()
        annotation_list = [_row_to_annotation_dict(a) for a in annotations]

    return render_template(
        "case_detail.html",
        case=case,
        annotations=annotation_list,
        image_types=config.IMAGE_TYPES,
        label_options=config.LABEL_OPTIONS,
        finding_options=config.FINDING_OPTIONS,
        finding_labels=config.FINDING_LABELS,
    )


@app.route("/api/cases/<case_id>")
def api_get_case(case_id: str):
    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return jsonify({"error": "症例が見つかりません"}), 404
        case = _row_to_case_dict(row)
        annotations = conn.execute(
            "SELECT * FROM annotations WHERE case_id = ? ORDER BY rank IS NULL, rank, point_id",
            (case_id,),
        ).fetchall()
        annotation_list = [_row_to_annotation_dict(a) for a in annotations]

    return jsonify({"case": case, "annotations": annotation_list})


@app.route("/api/cases/<case_id>", methods=["PATCH"])
def api_update_case(case_id: str):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return jsonify({"error": "症例が見つかりません"}), 404

        conn.execute(
            """
            UPDATE cases SET
                cytology_result = ?,
                hpv_result = ?,
                memo = ?,
                updated_at = datetime('now','localtime')
            WHERE case_id = ?
            """,
            (
                data.get("cytology_result"),
                data.get("hpv_result"),
                data.get("memo"),
                case_id,
            ),
        )
        updated = _get_case_or_404(conn, case_id)
    return jsonify({"case": _row_to_case_dict(updated)})


@app.route("/api/cases/<case_id>/analyze", methods=["POST"])
def api_analyze(case_id: str):
    data = request.get_json(silent=True) or {}
    provider = str(data.get("provider", _current_provider)).strip().lower()
    if provider not in _ALLOWED_PROVIDERS:
        return jsonify({"error": f"不明なプロバイダー: {provider}"}), 400

    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return jsonify({"error": "症例が見つかりません"}), 404

        image_path = row["original_image_path"]
        if not os.path.isfile(image_path):
            return jsonify({"error": "元画像が見つかりません"}), 404

        try:
            image = Image.open(image_path).convert("RGB")
            result = _get_engine(provider).analyze(image)
        except Exception as e:
            tb = traceback.format_exc()
            app.logger.error("推論エラー: %s\n%s", e, tb)
            return jsonify({"error": f"解析中にエラーが発生しました: {str(e)}"}), 500

        conn.execute(
            "DELETE FROM annotations WHERE case_id = ? AND source = 'ai' AND doctor_confirmed = 0",
            (case_id,),
        )

        for candidate in result.candidates:
            point_id = _next_point_id(conn, case_id)
            conn.execute(
                """
                INSERT INTO annotations (
                    case_id, point_id, rank, x_ratio, y_ratio, radius_ratio,
                    label, findings, ai_confidence, reason, source, doctor_confirmed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai', 1)
                """,
                (
                    case_id,
                    point_id,
                    candidate.rank,
                    candidate.x_ratio,
                    candidate.y_ratio,
                    candidate.radius_ratio,
                    candidate.label,
                    json.dumps(candidate.findings, ensure_ascii=False),
                    candidate.confidence,
                    candidate.reason,
                ),
            )

        conn.execute(
            """
            UPDATE cases SET
                ai_provider = ?,
                status = 'ai_analyzed',
                updated_at = datetime('now','localtime')
            WHERE case_id = ?
            """,
            (provider, case_id),
        )

        annotations = conn.execute(
            "SELECT * FROM annotations WHERE case_id = ? ORDER BY rank IS NULL, rank, point_id",
            (case_id,),
        ).fetchall()
        annotation_list = [_row_to_annotation_dict(a) for a in annotations]
        updated = _get_case_or_404(conn, case_id)

    return jsonify({
        "case": _row_to_case_dict(updated),
        "annotations": annotation_list,
        "overall_comment": result.overall_comment,
    })


@app.route("/api/cases/<case_id>/annotations", methods=["POST"])
def api_add_annotation(case_id: str):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return jsonify({"error": "症例が見つかりません"}), 404

        x_ratio = float(data.get("x_ratio", 0.5))
        y_ratio = float(data.get("y_ratio", 0.5))
        radius_ratio = max(0.02, float(data.get("radius_ratio", 0.05)))
        label = data.get("label", "LSIL_like")
        if label not in config.LABEL_OPTIONS:
            label = "LSIL_like"
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            findings = []

        point_id = _next_point_id(conn, case_id)
        cursor = conn.execute(
            """
            INSERT INTO annotations (
                case_id, point_id, rank, x_ratio, y_ratio, radius_ratio,
                label, findings, ai_confidence, reason, source, doctor_confirmed
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, NULL, ?, 'manual', 1)
            """,
            (
                case_id,
                point_id,
                x_ratio,
                y_ratio,
                radius_ratio,
                label,
                json.dumps(findings, ensure_ascii=False),
                data.get("reason", ""),
            ),
        )
        ann_id = cursor.lastrowid
        _touch_case(conn, case_id)

        if row["status"] == "uploaded":
            conn.execute(
                "UPDATE cases SET status = 'ai_analyzed', updated_at = datetime('now','localtime') WHERE case_id = ?",
                (case_id,),
            )

        ann = conn.execute(
            "SELECT * FROM annotations WHERE id = ?", (ann_id,)
        ).fetchone()

    return jsonify({"annotation": _row_to_annotation_dict(ann)}), 201


@app.route("/api/cases/<case_id>/annotations/<int:ann_id>", methods=["PATCH"])
def api_update_annotation(case_id: str, ann_id: int):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        ann = conn.execute(
            "SELECT * FROM annotations WHERE id = ? AND case_id = ?",
            (ann_id, case_id),
        ).fetchone()
        if not ann:
            return jsonify({"error": "アノテーションが見つかりません"}), 404

        x_ratio = data.get("x_ratio", ann["x_ratio"])
        y_ratio = data.get("y_ratio", ann["y_ratio"])
        radius_ratio = max(0.02, float(data.get("radius_ratio", ann["radius_ratio"])))
        label = data.get("label", ann["label"])
        if label not in config.LABEL_OPTIONS:
            label = ann["label"]
        reason = data.get("reason", ann["reason"])
        doctor_comment = data.get("doctor_comment", ann["doctor_comment"])
        findings_raw = ann["findings"]
        try:
            findings_list = json.loads(findings_raw or "[]")
        except json.JSONDecodeError:
            findings_list = []
        if "findings" in data and isinstance(data["findings"], list):
            findings_list = data["findings"]
        doctor_confirmed = ann["doctor_confirmed"]
        if "doctor_confirmed" in data:
            doctor_confirmed = 1 if data["doctor_confirmed"] else 0

        conn.execute(
            """
            UPDATE annotations SET
                x_ratio = ?, y_ratio = ?, radius_ratio = ?,
                label = ?, findings = ?, reason = ?,
                doctor_comment = ?, doctor_confirmed = ?,
                updated_at = datetime('now','localtime')
            WHERE id = ? AND case_id = ?
            """,
            (
                float(x_ratio),
                float(y_ratio),
                radius_ratio,
                label,
                json.dumps(findings_list, ensure_ascii=False),
                reason,
                doctor_comment,
                doctor_confirmed,
                ann_id,
                case_id,
            ),
        )
        _touch_case(conn, case_id)
        updated = conn.execute(
            "SELECT * FROM annotations WHERE id = ?", (ann_id,)
        ).fetchone()

    return jsonify({"annotation": _row_to_annotation_dict(updated)})


@app.route("/api/cases/<case_id>/annotations/<int:ann_id>", methods=["DELETE"])
def api_delete_annotation(case_id: str, ann_id: int):
    with get_db() as conn:
        ann = conn.execute(
            "SELECT * FROM annotations WHERE id = ? AND case_id = ?",
            (ann_id, case_id),
        ).fetchone()
        if not ann:
            return jsonify({"error": "アノテーションが見つかりません"}), 404
        conn.execute(
            "DELETE FROM annotations WHERE id = ? AND case_id = ?",
            (ann_id, case_id),
        )
        _touch_case(conn, case_id)
    return jsonify({"ok": True})


@app.route("/api/cases/<case_id>/approve", methods=["POST"])
def api_approve(case_id: str):
    data = request.get_json(silent=True) or {}
    annotated_image = data.get("annotated_image", "")

    if not annotated_image or not annotated_image.startswith("data:image/"):
        return jsonify({"error": "アノテーション付き画像データが必要です"}), 400

    match = re.match(r"data:image/(\w+);base64,(.+)", annotated_image)
    if not match:
        return jsonify({"error": "画像データの形式が不正です"}), 400

    img_format = match.group(1).lower()
    if img_format == "jpeg":
        ext = "jpg"
    elif img_format in ("png", "jpg"):
        ext = img_format
    else:
        return jsonify({"error": "対応していない画像形式です"}), 400

    try:
        img_bytes = base64.b64decode(match.group(2))
        image = Image.open(__import__("io").BytesIO(img_bytes))
        image.verify()
    except Exception:
        return jsonify({"error": "画像データをデコードできませんでした"}), 400

    client_ip = request.remote_addr or "unknown"
    logger.info("承認操作: case_id=%s, ip=%s", case_id, client_ip)

    with get_db() as conn:
        row = _get_case_or_404(conn, case_id)
        if not row:
            return jsonify({"error": "症例が見つかりません"}), 404

        case_dir = os.path.join(config.CASES_FOLDER, case_id)
        os.makedirs(case_dir, exist_ok=True)
        rel_path = f"{config.CASES_FOLDER}/{case_id}/annotated.{ext}"
        abs_path = os.path.join(case_dir, f"annotated.{ext}")

        img_bytes = base64.b64decode(match.group(2))
        with open(abs_path, "wb") as f:
            f.write(img_bytes)

        conn.execute(
            """
            UPDATE cases SET
                annotated_image_path = ?,
                status = 'approved',
                updated_at = datetime('now','localtime')
            WHERE case_id = ?
            """,
            (rel_path.replace("\\", "/"), case_id),
        )
        updated = _get_case_or_404(conn, case_id)

    return jsonify({"case": _row_to_case_dict(updated)})


@app.route("/api/provider")
def get_provider():
    return jsonify({
        "provider": _current_provider,
        "label": _LABEL_MAP.get(_current_provider, _current_provider),
        "available": sorted(_ALLOWED_PROVIDERS),
    })


@app.route("/api/provider/set", methods=["POST"])
def set_provider():
    global _current_provider
    data = request.get_json(silent=True) or {}
    provider = str(data.get("provider", "")).strip().lower()
    if provider not in _ALLOWED_PROVIDERS:
        return jsonify({"error": f"不明なプロバイダー: {provider}"}), 400
    try:
        _get_engine(provider)
    except Exception as e:
        return jsonify({"error": f"初期化失敗: {str(e)}"}), 500
    _current_provider = provider
    return jsonify({"provider": provider, "label": _LABEL_MAP.get(provider, provider)})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=50012)
