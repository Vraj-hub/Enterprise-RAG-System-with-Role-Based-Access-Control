import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_data_setting = Path(os.getenv("DATA_DIR", "./data_nomic")).expanduser()
DATA_DIR = (_data_setting if _data_setting.is_absolute() else PROJECT_ROOT / _data_setting).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
CHROMA_PATH = str(DATA_DIR / "chroma")

import secrets as _secrets
_secret = os.getenv("JWT_SECRET", "")
if len(_secret) < 32 or _secret.startswith("replace-with"):
    # No public default: a random per-process secret (logins reset on restart) beats a guessable one.
    _secret = _secrets.token_urlsafe(48)
    print("[config] JWT_SECRET missing/weak: using a temporary random secret. Set a 32+ char value in .env")
JWT_SECRET = _secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

EMBEDDER = os.getenv("EMBEDDER", "ollama").strip().lower()
ST_MODEL = os.getenv("ST_MODEL", "all-MiniLM-L6-v2")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
# Set to 1 if Ollama's runner crashes on the GPU (Windows "exit status 0xc0000005"): embeddings then run on the CPU only.
OLLAMA_EMBED_CPU_ONLY = os.getenv("OLLAMA_EMBED_CPU_ONLY", "0").strip().lower() in {"1", "true", "yes"}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

TOP_K = 5
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# Retrieval tuning (calibrate on your own documents with eval/run_eval.py)
MIN_RELEVANCE = float(os.getenv("MIN_RELEVANCE", "0.35"))   # min cosine similarity for a vector-only hit
CANDIDATES = int(os.getenv("CANDIDATES", "12"))             # candidates per retriever before fusion
HISTORY_TURNS = 3


# ---- Self-service sign-up and Google sign-in
# SIGNUP_MODE: "approval" (default: new accounts wait for an admin), "open" (active immediately), "off".
SIGNUP_MODE = os.getenv("SIGNUP_MODE", "approval").strip().lower()
if SIGNUP_MODE not in {"open", "approval", "off"}:
    SIGNUP_MODE = "approval"
# New accounts are always role=employee in this department, which only sees company-wide ("all") documents.
SIGNUP_DEPARTMENT = os.getenv("SIGNUP_DEPARTMENT", "general").strip().lower() or "general"
# Optional allow-list, e.g. "company.com,corp.company.com". Empty = any email domain.
SIGNUP_EMAIL_DOMAINS = {d.strip().lower().lstrip("@") for d in os.getenv("SIGNUP_EMAIL_DOMAINS", "").split(",") if d.strip()}
SIGNUP_RATE_PER_HOUR = int(os.getenv("SIGNUP_RATE_PER_HOUR", "5"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
APP_HOST = os.getenv("APP_HOST", "127.0.0.1").strip()
APP_PORT = int(os.getenv("APP_PORT", "8080"))
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"http://127.0.0.1:{APP_PORT}/api/auth/google/callback").strip()
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)