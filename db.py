import sqlite3
from contextlib import contextmanager

import config


def init_db() -> None:
    import os

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                patient_id TEXT NOT NULL,
                exam_date TEXT NOT NULL,
                image_type TEXT NOT NULL,
                cytology_result TEXT,
                hpv_result TEXT,
                biopsy_result TEXT,
                final_diagnosis TEXT,
                memo TEXT,
                original_image_path TEXT NOT NULL,
                annotated_image_path TEXT,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                ai_provider TEXT,
                status TEXT NOT NULL DEFAULT 'uploaded',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                point_id INTEGER NOT NULL,
                rank INTEGER,
                x_ratio REAL NOT NULL,
                y_ratio REAL NOT NULL,
                radius_ratio REAL NOT NULL,
                label TEXT NOT NULL,
                findings TEXT NOT NULL DEFAULT '[]',
                ai_confidence REAL,
                reason TEXT,
                source TEXT NOT NULL,
                doctor_confirmed INTEGER NOT NULL DEFAULT 1,
                doctor_comment TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_annotations_case_id ON annotations(case_id);
            """
        )


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
