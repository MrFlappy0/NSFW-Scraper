#!/usr/bin/env python3
"""
NSFW-Scraper - Modular media scraper for NSFW content.
Features:
- Interactive CLI with site selection.
- Segmented async downloads with retry logic.
- SQLite database for tracking downloads.
- Automatic dependency installation.
- Multi-OS support (Windows, Linux, macOS).

Usage:
    python main.py
"""

import os
import sys
import json
import asyncio
import hashlib
import logging
import random
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Import global config
from config import *

# ====================== COLORS ======================
# ANSI color codes for terminal output
class Colors:
    RED = "\033[91m"     # Error messages
    GREEN = "\033[92m"   # Success messages
    YELLOW = "\033[93m"  # Warnings
    CYAN = "\033[96m"    # Info messages
    BOLD = "\033[1m"     # Bold text
    RESET = "\033[0m"    # Reset to default

# ====================== MODULES ======================
# Available modules (loaded dynamically)
# Add new modules here (key = module name, value = None initially)
MODULES = {
    "bunkr": None,      # Bunkr albums
    "ph": None,         # PornHub
    "xvideos": None,    # Xvideos
    "xhamster": None,   # XHamster
    "spankbang": None,  # SpankBang
}

# ====================== INITIALIZATION ======================
def init_directories() -> None:
    """
    Create necessary directories if they don't exist.
    Also checks write permissions.
    """
    for d in [BASE_DIR, DOWNLOADS_DIR, LOGS_DIR, DB_DIR]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            test_file = d / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            print(f"{Colors.RED}❌ Permission denied for {d}. Check directory permissions.{Colors.RESET}")
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.RED}❌ Error creating {d}: {e}{Colors.RESET}")
            sys.exit(1)

def setup_logger() -> logging.Logger:
    """
    Configure the logger for the scraper.
    Logs are saved to scrap/logs/scrap_system.log.
    """
    init_directories()
    logger = logging.getLogger("ScraperLogger")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if not logger.handlers:
        try:
            fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
            logger.addHandler(fh)
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to set up logger: {e}{Colors.RESET}")

    return logger

# Initialize logger
LOGGER = setup_logger()

# ====================== DATABASE ======================
async def init_database() -> None:
    """
    Initialize SQLite database for tracking downloads.
    Creates the 'medias' table if it doesn't exist.
    """
    init_directories()
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS medias (
                    media_id TEXT PRIMARY KEY,
                    album_url TEXT,
                    media_url TEXT,
                    filename TEXT,
                    media_type TEXT,
                    status TEXT,
                    target_path TEXT,
                    module TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    except Exception as e:
        LOGGER.error(f"Database initialization failed: {e}")
        print(f"{Colors.RED}❌ Database error: {e}{Colors.RESET}")

async def update_media_status(media_id: str, status: str) -> None:
    """
    Update the status of a media in the database.
    Args:
        media_id: Unique ID of the media.
        status: New status (PENDING, DOWNLOADING, COMPLETED, FAILED).
    """
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "UPDATE medias SET status = ? WHERE media_id = ?",
                (status, media_id)
            )
            await db.commit()
    except Exception as e:
        LOGGER.error(f"Failed to update media status: {e}")

async def is_media_already_completed(media_id: str) -> bool:
    """
    Check if a media is already downloaded and valid.
    Args:
        media_id: Unique ID of the media.
    Returns:
        True if media is already completed and file exists, False otherwise.
    """
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute(
                "SELECT status, target_path FROM medias WHERE media_id = ?",
                (media_id,)
            )
            row = await cursor.fetchone()
            if row and row[0] == "COMPLETED" and Path(row[1]).exists():
                return True
    except Exception as e:
        LOGGER.error(f"Error checking media status: {e}")
    return False

async def register_media(media: Dict) -> bool:
    """
    Register a media in the database.
    Args:
        media: Dictionary containing media info (must have media_id, status, target_path).
    Returns:
        True if media was registered, False if already exists and is completed.
    """
    try:
        if await is_media_already_completed(media["media_id"]):
            return False

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                """INSERT OR REPLACE INTO medias
                (media_id, album_url, media_url, filename, media_type, status, target_path, module)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    media["media_id"],
                    media["album_url"],
                    media["media_url"],
                    media["filename"],
                    media["type"],
                    media["status"],
                    media["target_path"],
                    media["module"],
                )
            )
            await db.commit()
            return True
    except Exception as e:
        LOGGER.error(f"Failed to register media: {e}")
        return False

# ====================== UTILITIES ======================
def generate_hash(text: str) -> str:
    """
    Generate a unique hash for a media URL.
    Args:
        text: Input string (usually a URL).
    Returns:
        12-character MD5 hash.
    """
    return hashlib.md5(text.encode()).hexdigest()[:12]

def classify_media(url: str) -> str:
    """
    Classify a media URL as video, image, or file.
    Args:
        url: Media URL.
    Returns:
        "video", "image", or "file".
    """
    url_lower = url.lower()
    if any(ext in url_lower for ext in VIDEO_EXTS) or "stream" in url_lower or "/v/" in url_lower:
        return "video"
    if any(ext in url_lower for ext in IMAGE_EXTS):
        return "image"
    return "file"

def clean_console() -> None:
    """Clear the console (cross-platform)."""
    os.system('cls' if os.name == 'nt' else 'clear')

def cleanup_temp_files() -> None:
    """
    Clean up temporary files (.part*) from previous downloads.
    Called at startup and after errors.
    """
    for part_file in DOWNLOADS_DIR.glob("**/*.part*"):
        try:
            part_file.unlink()
            LOGGER.info(f"Cleaned up temp file: {part_file}")
        except Exception as e:
            LOGGER.error(f"Failed to clean up {part_file}: {e}")

# ====================== AUTO-SETUP ======================
def check_command_exists(command: str) -> bool:
    """
    Check if a command exists in the system PATH.
    Args:
        command: Command to check (e.g., "ffmpeg").
    Returns:
        True if command exists, False otherwise.
    """
    return shutil.which(command) is not None

async def install_package(package: str) -> bool:
    """
    Install a Python package using pip (async).
    Args:
        package: Package name (e.g., "aiohttp").
    Returns:
        True if installation succeeded, False otherwise.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "-U", "--break-system-packages", package,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)
        return proc.returncode == 0
    except Exception as e:
        LOGGER.error(f"Failed to install {package}: {e}")
        return False

async def install_ffmpeg() -> bool:
    """
    Install ffmpeg based on the OS (async).
    Returns:
        True if installation succeeded, False otherwise.
    """
    os_type = sys.platform
    commands = {
        "darwin": ["brew", "install", "ffmpeg"],
        "linux": ["sudo", "apt-get", "install", "-y", "ffmpeg"],
        "win32": ["powershell", "-Command", "winget install -e --id Gyan.FFmpeg"],
    }

    if os_type not in commands:
        print(f"{Colors.YELLOW}⚠️  Unsupported OS for automatic ffmpeg installation: {os_type}{Colors.RESET}")
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            *commands[os_type],
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.wait_for(proc.communicate(), timeout=120)
        return proc.returncode == 0
    except Exception as e:
        LOGGER.error(f"Failed to install ffmpeg: {e}")
        return False

async def setup_environment() -> None:
    """
    Check and install required dependencies.
    - Python packages (via pip)
    - ffmpeg (via brew/apt/winget)
    - Creates directories
    - Cleans up temp files
    """
    print(f"\n{Colors.CYAN}🔧 Checking dependencies...{Colors.RESET}")

    # Check Python packages
    missing_packages = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing_packages.append(pkg)

    if missing_packages:
        print(f"{Colors.YELLOW}⚠️  Missing packages: {', '.join(missing_packages)}{Colors.RESET}")
        print(f"{Colors.CYAN}📦 Installing missing packages...{Colors.RESET}")

        # Install packages in parallel
        tasks = [install_package(pkg) for pkg in missing_packages]
        results = await asyncio.gather(*tasks)

        if not all(results):
            print(f"{Colors.RED}❌ Some packages failed to install. Check logs for details.{Colors.RESET}")

    # Check ffmpeg
    if not check_command_exists("ffmpeg"):
        print(f"{Colors.YELLOW}⚠️  ffmpeg not found. Installing...{Colors.RESET}")
        if not await install_ffmpeg():
            print(f"{Colors.RED}❌ Failed to install ffmpeg automatically.{Colors.RESET}")
            print(f"{Colors.YELLOW}💡 Please install ffmpeg manually:{Colors.RESET}")
            if sys.platform == "darwin":
                print("   brew install ffmpeg")
            elif sys.platform == "linux":
                print("   sudo apt-get install ffmpeg")
            elif sys.platform == "win32":
                print("   winget install -e --id Gyan.FFmpeg")
    else:
        print(f"{Colors.GREEN}✅ ffmpeg is installed.{Colors.RESET}")

    # Clean up temp files
    cleanup_temp_files()

# ====================== DOWNLOAD LOGIC ======================
async def get_file_size(url: str, session) -> int:
    """
    Get the size of a file via HEAD request.
    Args:
        url: URL of the file.
        session: aiohttp ClientSession.
    Returns:
        File size in bytes, or 0 if failed.
    """
    headers = {
        "Referer": url,
        "User-Agent": random.choice(USER_AGENTS),
        "Range": "bytes=0-0"
    }
    try:
        async with session.head(url, headers=headers, timeout=15) as resp:
            if resp.status == 206:
                content_range = resp.headers.get("Content-Range", "")
                if "/" in content_range:
                    return int(content_range.split("/")[1])
            elif resp.status == 200:
                return int(resp.headers.get("Content-Length", 0))
    except Exception as e:
        LOGGER.error(f"Failed to get file size for {url}: {e}")
    return 0

def get_random_headers(url: str, start: int, end: int) -> Dict[str, str]:
    """
    Generate random headers to avoid bot detection.
    Args:
        url: URL of the file.
        start: Start byte for Range header.
        end: End byte for Range header.
    Returns:
        Dictionary of headers.
    """
    spoofed_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    return {
        "Referer": url,
        "User-Agent": random.choice(USER_AGENTS),
        "Range": f"bytes={start}-{end}",
        "X-Forwarded-For": spoofed_ip,
        "X-Real-IP": spoofed_ip,
        "Accept-Encoding": "identity",  # Avoid compression
        "Connection": "keep-alive",
    }

async def stealth_worker(
    queue: asyncio.Queue,
    session,
    url: str,
    pbar,
    module: str
) -> None:
    """
    Worker for segmented downloads.
    Args:
        queue: Queue of download tasks (start, end, part_path, attempt).
        session: aiohttp ClientSession.
        url: URL of the file.
        pbar: Progress bar.
        module: Name of the module (for logging).
    """
    while True:
        try:
            start, end, part_path, attempt = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        expected_size = end - start + 1

        # Skip if part already exists and is complete
        if part_path.exists() and part_path.stat().st_size == expected_size:
            pbar.update(expected_size)
            queue.task_done()
            continue

        # Random delay to avoid detection
        delay = min(2 ** attempt, 10)  # Exponential backoff, max 10s
        await asyncio.sleep(delay + random.uniform(0.1, 0.5))

        headers = get_random_headers(url, start, end)
        success = False

        try:
            timeout = aiohttp.ClientTimeout(total=60, sock_read=30)
            async with session.get(url, headers=headers, timeout=timeout, allow_redirects=True) as resp:
                if resp.status in (200, 206):
                    data = await resp.read()
                    if len(data) == expected_size:
                        async with aiofiles.open(part_path, 'wb') as f:
                            await f.write(data)
                        pbar.update(expected_size)
                        success = True
                elif resp.status == 429:  # Too Many Requests
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    await asyncio.sleep(retry_after)
                elif resp.status in (403, 404):
                    LOGGER.error(f"{module}: HTTP {resp.status} for {url} (segment {start}-{end})")
                else:
                    LOGGER.error(f"{module}: Unexpected status {resp.status} for {url}")
        except asyncio.TimeoutError:
            LOGGER.warning(f"{module}: Timeout for segment {start}-{end} (attempt {attempt})")
        except aiohttp.ClientError as e:
            LOGGER.error(f"{module}: aiohttp error for {url}: {e}")
        except Exception as e:
            LOGGER.error(f"{module}: Unexpected error: {e}")

        if not success:
            if attempt < RETRY_ATTEMPTS:
                queue.put_nowait((start, end, part_path, attempt + 1))
            else:
                LOGGER.error(f"{module}: Giving up on segment {start}-{end} after {RETRY_ATTEMPTS} attempts")

        queue.task_done()

async def download_file(media: Dict) -> bool:
    """
    Download a file using segmented downloads.
    Args:
        media: Dictionary with media info (url, filename, target_path, module, etc.).
    Returns:
        True if download succeeded, False otherwise.
    """
    media_id = media["media_id"]
    url = media["media_url"]
    filename = media["filename"]
    output_path = Path(media["target_path"])
    module = media["module"]

    await update_media_status(media_id, "DOWNLOADING")

    # Configure aiohttp with connection limits
    connector = aiohttp.TCPConnector(
        limit=10,               # Max 10 total connections
        limit_per_host=3,      # Max 3 connections per host
        force_close=True,      # Close connections after use
        enable_cleanup_closed=True
    )

    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT)
        ) as session:
            # Get file size
            total_size = await get_file_size(url, session)
            if total_size == 0:
                LOGGER.error(f"{module}: Failed to get file size for {url}")
                await update_media_status(media_id, "FAILED")
                return False

            # Dynamic chunk size based on file size
            if total_size < 50 * 1024 * 1024:  # < 50 MB
                chunk_size = max(MIN_CHUNK_SIZE, total_size // 3)  # At least 3 chunks
            else:
                chunk_size = CHUNK_SIZE

            num_chunks = (total_size + chunk_size - 1) // chunk_size
            workers_count = min(MAX_WORKERS, num_chunks)

            # Create queue and add chunks
            queue = asyncio.Queue()
            for i in range(num_chunks):
                start = i * chunk_size
                end = min(start + chunk_size - 1, total_size - 1)
                part_path = Path(f"{output_path}.part{i}")
                queue.put_nowait((start, end, part_path, 0))

            # Progress bar
            short_name = filename[:30] + ".." if len(filename) > 32 else filename.ljust(32)
            pbar = tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=f"🚀 {short_name} ({module})",
                leave=True
            )

            # Start workers
            tasks = [
                asyncio.create_task(stealth_worker(queue, session, url, pbar, module))
                for _ in range(workers_count)
            ]

            # Wait for all chunks to complete
            await queue.join()

            # Cancel workers
            for task in tasks:
                task.cancel()

            pbar.close()

            # Check if all parts are downloaded
            missing_parts = any(
                not Path(f"{output_path}.part{i}").exists()
                for i in range(num_chunks)
            )

            if not missing_parts:
                # Assemble parts
                tqdm.write(f"{Colors.CYAN}📦 Assembling {filename}...{Colors.RESET}")
                async with aiofiles.open(output_path, "wb") as outfile:
                    for i in range(num_chunks):
                        part_path = Path(f"{output_path}.part{i}")
                        async with aiofiles.open(part_path, "rb") as infile:
                            await outfile.write(await infile.read())
                        part_path.unlink()  # Delete part after assembly

                # Verify integrity
                is_valid = await verify_media_integrity(output_path)
                if not is_valid:
                    tqdm.write(f"{Colors.RED}❌ Corrupted file: {filename}. Deleting.{Colors.RESET}")
                    output_path.unlink()
                    await update_media_status(media_id, "FAILED")
                    return False

                tqdm.write(f"{Colors.GREEN}✅ Downloaded: {filename}{Colors.RESET}")
                await update_media_status(media_id, "COMPLETED")
                return True
            else:
                tqdm.write(f"{Colors.RED}❌ Failed to assemble: {filename}{Colors.RESET}")
                await update_media_status(media_id, "FAILED")
                return False

    except Exception as e:
        LOGGER.error(f"{module}: Download failed for {filename}: {e}")
        await update_media_status(media_id, "FAILED")
        return False

async def verify_media_integrity(file_path: Path) -> bool:
    """
    Verify the integrity of a downloaded media file.
    Args:
        file_path: Path to the file.
    Returns:
        True if file is valid, False otherwise.
    """
    if not file_path.exists() or file_path.stat().st_size == 0:
        return False

    ext = file_path.suffix.lower()

    # Check video files with ffprobe
    if ext in VIDEO_EXTS:
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=nw=1:nk=1",
                str(file_path)
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return "video" in stdout.decode().strip().lower()
        except Exception as e:
            LOGGER.error(f"ffprobe failed for {file_path}: {e}")
            return True  # Assume valid if ffprobe fails

    # Check image files with Pillow
    elif ext in IMAGE_EXTS:
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                img.verify()  # Verify integrity
            return True
        except Exception as e:
            LOGGER.error(f"Pillow verification failed for {file_path}: {e}")
            return False

    # For other files, just check size > 0
    return file_path.stat().st_size > 0

# ====================== MODULE LOADING ======================
def load_module(module_name: str):
    """
    Dynamically load a module.
    Args:
        module_name: Name of the module (e.g., "bunkr").
    Returns:
        The module object, or None if failed.
    """
    if module_name not in MODULES:
        return None

    if MODULES[module_name] is None:
        try:
            module = __import__(f"Modules.{module_name}", fromlist=[module_name])
            MODULES[module_name] = module
            return module
        except ImportError as e:
            LOGGER.error(f"Failed to load module {module_name}: {e}")
            return None

    return MODULES[module_name]

async def get_available_modules() -> List[Tuple[str, str]]:
    """
    Get list of available modules with their descriptions.
    Returns:
        List of tuples (module_name, description).
    """
    modules = []
    for module_name in MODULES:
        module = load_module(module_name)
        if module:
            description = getattr(module, "DESCRIPTION", "No description")
            modules.append((module_name, description))
    return modules

# ====================== CLI MENU ======================
async def process_module_downloads(module_name: str, url: str) -> None:
    """
    Process downloads for a given module.
    Args:
        module_name: Name of the module (e.g., "bunkr").
        url: URL to scrape.
    """
    module = load_module(module_name)
    if not module:
        print(f"{Colors.RED}❌ Module {module_name} not found or failed to load.{Colors.RESET}")
        return

    try:
        # Call the module's scrape function
        medias = await module.scrape(url)
        if not medias:
            print(f"{Colors.RED}❌ No media found for {url}.{Colors.RESET}")
            return

        # Filter out already completed medias
        new_medias = []
        for media in medias:
            if await register_media(media):
                new_medias.append(media)

        if not new_medias:
            print(f"{Colors.GREEN}✅ All media already downloaded.{Colors.RESET}")
            return

        # Display found media
        videos = sum(1 for m in new_medias if m["type"] == "video")
        images = sum(1 for m in new_medias if m["type"] == "image")
        print("\n" + "=" * 55)
        print(f"{Colors.BOLD}{Colors.GREEN}📁 MEDIA TO DOWNLOAD ({module_name.upper()}){Colors.RESET}")
        print("=" * 55)
        print(f"🎬 Videos  : {Colors.BOLD}{videos}{Colors.RESET}")
        print(f"🖼️  Images  : {Colors.BOLD}{images}{Colors.RESET}")
        print(f"📦 Total   : {Colors.BOLD}{len(new_medias)}{Colors.RESET}")
        print("=" * 55)

        # Ask for confirmation
        if input(f"\n{Colors.BOLD}Start download? (y/n): {Colors.RESET}").strip().lower() not in ["y", "yes"]:
            return

        clean_console()
        print(f"{Colors.GREEN}🚀 Starting download ({module_name})...{Colors.RESET}\n")

        # Download each media
        for i, media in enumerate(new_medias, start=1):
            print(f"\n{Colors.CYAN}File {i}/{len(new_medias)} ({module_name}){Colors.RESET}")
            await download_file(media)

    except Exception as e:
        LOGGER.error(f"Error in module {module_name}: {e}")
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")

async def show_stats() -> None:
    """
    Display download statistics from the database.
    """
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            # Total media
            cursor = await db.execute("SELECT COUNT(*) FROM medias")
            total = (await cursor.fetchone())[0]

            # Completed
            cursor = await db.execute("SELECT COUNT(*) FROM medias WHERE status = 'COMPLETED'")
            completed = (await cursor.fetchone())[0]

            # Failed
            cursor = await db.execute("SELECT COUNT(*) FROM medias WHERE status = 'FAILED'")
            failed = (await cursor.fetchone())[0]

            # By module
            cursor = await db.execute("""
                SELECT module, COUNT(*)
                FROM medias
                WHERE status = 'COMPLETED'
                GROUP BY module
            """)
            rows = await cursor.fetchall()
            module_stats = {row[0]: row[1] for row in rows}

            print("\n" + "=" * 55)
            print(f"{Colors.BOLD}📊 STATISTICS{Colors.RESET}")
            print("=" * 55)
            print(f"✅ Completed: {Colors.BOLD}{completed}{Colors.RESET}")
            print(f"❌ Failed   : {Colors.BOLD}{failed}{Colors.RESET}")
            print(f"📦 Total    : {Colors.BOLD}{total}{Colors.RESET}")

            if module_stats:
                print("\n📁 By Module:")
                for module, count in module_stats.items():
                    print(f"   - {module.upper()}: {count}")

            print("=" * 55)
    except Exception as e:
        LOGGER.error(f"Failed to show stats: {e}")
        print(f"{Colors.RED}❌ Error loading stats: {e}{Colors.RESET}")

async def main_loop() -> None:
    """
    Main CLI loop.
    Displays menu, handles user input, and processes downloads.
    """
    await init_database()
    await setup_environment()

    # Pre-load modules
    for module_name in MODULES:
        load_module(module_name)

    while True:
        clean_console()
        print("\n" + "=" * 65)
        print(f"{Colors.BOLD}{Colors.RED}🔥 NSFW-SCRAPER (MODULAR) 🔥{Colors.RESET}")
        print("=" * 65)

        # Display available modules
        modules = await get_available_modules()
        for i, (module_name, description) in enumerate(modules, start=1):
            print(f"{i}. {module_name.upper()} - {description}")

        print(f"{len(modules) + 1}. Statistics")
        print(f"{len(modules) + 2}. Exit")
        print("=" * 65)

        try:
            choice = input("Select an option: ").strip()
            if choice == str(len(modules) + 2):  # Exit
                break
            elif choice == str(len(modules) + 1):  # Stats
                await show_stats()
                input("\nPress Enter to continue...")
                continue

            choice_index = int(choice) - 1
            if 0 <= choice_index < len(modules):
                module_name, _ = modules[choice_index]
                url = input(f"\n{Colors.BOLD}URL for {module_name.upper()}: {Colors.RESET}").strip()
                await process_module_downloads(module_name, url)
            else:
                print(f"{Colors.RED}❌ Invalid choice.{Colors.RESET}")

        except ValueError:
            print(f"{Colors.RED}❌ Please enter a number.{Colors.RESET}")
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}👋 Exiting...{Colors.RESET}")
            break

        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        # Import aiohttp and others (after setup_environment)
        import aiohttp
        import aiofiles
        import aiosqlite
        from tqdm.asyncio import tqdm

        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Goodbye!{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        LOGGER.critical(f"Fatal error: {e}", exc_info=True)
        print(f"{Colors.RED}❌ Fatal error: {e}{Colors.RESET}")
        sys.exit(1)
