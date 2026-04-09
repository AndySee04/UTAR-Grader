import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Database stored in backend folder
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/backend/auto_grade.db")

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


CRAFT_PRESET = os.getenv("CRAFT_PRESET", "balanced").strip().lower() or "balanced"
_CRAFT_PRESETS = {
    "balanced": {"text_threshold": 0.82, "link_threshold": 0.62, "low_text": 0.40},
    "faint_handwriting": {"text_threshold": 0.74, "link_threshold": 0.55, "low_text": 0.32},
    "strict": {"text_threshold": 0.88, "link_threshold": 0.68, "low_text": 0.45},
}
_active_craft = _CRAFT_PRESETS.get(CRAFT_PRESET, _CRAFT_PRESETS["balanced"])

# Numeric values in env override preset defaults.
CRAFT_TEXT_THRESHOLD = _env_float("CRAFT_TEXT_THRESHOLD", _active_craft["text_threshold"])
CRAFT_LINK_THRESHOLD = _env_float("CRAFT_LINK_THRESHOLD", _active_craft["link_threshold"])
CRAFT_LOW_TEXT = _env_float("CRAFT_LOW_TEXT", _active_craft["low_text"])
OCR_DIAGNOSTICS = os.getenv("OCR_DIAGNOSTICS", "0").strip().lower() in {"1", "true", "yes", "on"}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".pdf"}
