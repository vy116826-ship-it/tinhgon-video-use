"""Application configuration via environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Base Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
PROJECT_DIR = DATA_DIR / "projects"
OUTPUT_DIR = DATA_DIR / "outputs"
DB_DIR = DATA_DIR / "db"

# Ensure dirs exist
for d in (UPLOAD_DIR, PROJECT_DIR, OUTPUT_DIR, DB_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Database ────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DB_DIR / 'video_use.db'}")

# ── Redis / Celery ──────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ── Auth / JWT ──────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production-video-use-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours

# ── External APIs ───────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY", "")
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "elevenlabs")  # elevenlabs | google | whisper

# ── FFmpeg ──────────────────────────────────────────────────────────────
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")

# ── Upload limits ───────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5120"))  # 5 GB
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv", ".ts", ".mts"}

# ── Worker ──────────────────────────────────────────────────────────────
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))

# ── Helpers path ────────────────────────────────────────────────────────
HELPERS_DIR = Path(os.getenv("HELPERS_DIR", str(BASE_DIR.parent / "helpers")))
