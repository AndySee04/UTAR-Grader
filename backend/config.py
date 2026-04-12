import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

def _try_set_env(key: str, value: str) -> None:
    """Set from .env only if missing or empty (so real OS env wins; empty placeholders can be filled)."""
    if not key:
        return
    v = value.strip().strip('"').strip("'")
    cur = os.environ.get(key)
    if cur is None or (isinstance(cur, str) and cur.strip() == ""):
        os.environ[key] = v


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        _try_set_env(key.strip(), value)


# Project root .env, then backend/.env (fills vars missing from the first file).
_BACKEND_DIR = Path(__file__).resolve().parent
_load_env_file(BASE_DIR / ".env")
_load_env_file(_BACKEND_DIR / ".env")

# Database stored in backend folder
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/backend/auto_grade.db")

# Normalize relative sqlite URLs from .env so startup is stable regardless of cwd.
# Example: sqlite:///./backend/auto_grade.db -> absolute path under project root.
if DATABASE_URL.startswith("sqlite:///./"):
    rel_part = DATABASE_URL[len("sqlite:///./"):]
    abs_part = (BASE_DIR / rel_part).resolve()
    DATABASE_URL = f"sqlite:///{abs_part.as_posix()}"

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")


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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Public site URL for links in emails (no trailing slash).
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").strip().rstrip("/")

# Gmail: use an App Password (Google Account → Security → 2-Step → App passwords).
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = _env_int("SMTP_PORT", 465)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
# Use 1 with SMTP_PORT=587 if SSL on 465 is blocked (Gmail supports both).
SMTP_USE_STARTTLS = os.getenv("SMTP_USE_STARTTLS", "").strip().lower() in {"1", "true", "yes", "on"}


def smtp_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)
