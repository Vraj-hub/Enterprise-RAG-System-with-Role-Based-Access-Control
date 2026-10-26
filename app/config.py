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

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-please-0123456789")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

EMBEDDER = os.getenv("EMBEDDER", "ollama").strip().lower()
ST_MODEL = os.getenv("ST_MODEL", "all-MiniLM-L6-v2")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

TOP_K = 5
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
