"""
Global configuration for NSFW-Scraper.
This file contains all shared constants and settings used across modules.
"""

import sys
from pathlib import Path

# ====================== PATHS ======================
# Base directory for all scraped data
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR / "scrap"
DOWNLOADS_DIR = BASE_DIR / "downloads"  # Downloaded media
LOGS_DIR = BASE_DIR / "logs"             # Log files
DB_DIR = BASE_DIR / "database"           # SQLite database
DB_FILE = DB_DIR / "scrap_resume.sqlite" # Database file
LOG_FILE = LOGS_DIR / "scrap_system.log" # Main log file

# ====================== DEPENDENCIES ======================
# List of required Python packages (installed automatically if missing)
REQUIRED_PACKAGES = [
    "aiohttp",      # Async HTTP requests
    "aiofiles",     # Async file I/O
    "aiosqlite",    # Async SQLite
    "yt-dlp",       # Video downloader (YouTube, PornHub, etc.)
    "gallery-dl",   # Image/album downloader (Bunkr, etc.)
    "tqdm",         # Progress bars
    "Pillow",       # Image verification
]

# ====================== USER AGENTS ======================
# Rotating user agents to avoid bot detection
# Updated with latest Chrome/Firefox/Safari versions (2024)
USER_AGENTS = [
    # Chrome (Mac/Windows)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    # Firefox (Mac/Windows)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
]

# ====================== FILE EXTENSIONS ======================
# Supported video and image extensions
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".flv", ".wmv", ".3gp"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

# ====================== DOWNLOAD SETTINGS ======================
# Default chunk size for segmented downloads (10 MB)
CHUNK_SIZE = 10 * 1024 * 1024
# Maximum number of parallel workers
MAX_WORKERS = 4
# Maximum retry attempts for failed segments
RETRY_ATTEMPTS = 15
# Timeout for HTTP requests (seconds)
TIMEOUT = 120
# Minimum chunk size for small files (1 MB)
MIN_CHUNK_SIZE = 1 * 1024 * 1024
