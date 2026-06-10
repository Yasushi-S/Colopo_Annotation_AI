import os
import secrets

from dotenv import load_dotenv

load_dotenv()

CASES_FOLDER = "static/cases"
DB_PATH = "data/colpo_annotation.db"
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

IMAGE_TYPES = {
    "acetowhite": "酢酸後",
    "iodine": "ヨード後",
    "white_light": "通常光",
}

STATUS_LABELS = {
    "uploaded": "未解析",
    "ai_analyzed": "AI解析済み・未承認",
    "approved": "承認済み",
}

LABEL_OPTIONS = [
    "LSIL_like",
    "HSIL_suspicious",
    "cancer_suspicious",
    "inflammation_like",
    "metaplasia_like",
]

FINDING_OPTIONS = [
    "dense_acetowhite",
    "sharp_margin",
    "coarse_mosaic",
    "coarse_punctation",
    "atypical_vessel",
    "glandular_involvement",
    "suspicious_invasion",
    "inflammation_like",
    "immature_metaplasia_like",
]

FINDING_LABELS = {
    "dense_acetowhite": "境界明瞭で濃い酢酸白色上皮",
    "sharp_margin": "鋭い境界・内境界・隆起境界",
    "coarse_mosaic": "粗大モザイクパターン",
    "coarse_punctation": "粗大点状血管",
    "atypical_vessel": "異型血管",
    "glandular_involvement": "腺開口部・頸管内への病変波及疑い",
    "suspicious_invasion": "易出血性・不整潰瘍など浸潤疑い",
    "inflammation_like": "炎症性変化",
    "immature_metaplasia_like": "未熟化生様の変化",
}
