import sys
from pathlib import Path

# ====================== CHEMINS ======================
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR / "scrap"
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
DB_DIR = BASE_DIR / "database"
DB_FILE = DB_DIR / "scrap_resume.sqlite"
LOG_FILE = LOGS_DIR / "scrap_system.log"

# ====================== DÉPENDANCES ======================
REQUIRED_PACKAGES = [
    "aiohttp",
    "aiofiles",
    "aiosqlite",
    "yt-dlp",
    "gallery-dl",
    "tqdm",
    "Pillow",
]

# ====================== USER AGENTS ======================
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# ====================== EXTENSIONS ======================
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".flv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# ====================== PARAMÈTRES DE TÉLÉCHARGEMENT ======================
CHUNK_SIZE = 10 * 1024 * 1024  # 10 Mo
MAX_WORKERS = 4
RETRY_ATTEMPTS = 15
TIMEOUT = 120  # secondes
