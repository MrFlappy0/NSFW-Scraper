#!/usr/bin/env python3
"""
Stealth-Scraper CLI Autonome (Édition Parfaite)
- Extraction asynchrone avec Spinner visuel (Anti-Freeze).
- Injection de User-Agents furtifs dans Gallery-DL.
- Auto-Mise à jour des extracteurs pour contrer Cloudflare.
- Affichage détaillé du type de médias rétabli.
"""

import os
import sys
import json
import asyncio
import hashlib
import logging
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

# ====================== CONFIGURATION & DÉPENDANCES ======================
REQUIRED_PACKAGES = [
    "aiohttp",
    "aiofiles",
    "aiosqlite",
    "yt-dlp",
    "gallery-dl",
    "tqdm",
]

class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def setup_environment():
    """Vérifie les dépendances et force la MAJ des extracteurs critiques."""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)
            
    if missing:
        print(f"[\033[94mACTION\033[0m] Installation : {', '.join(missing)}...")
        subprocess.call([sys.executable, "-m", "pip", "install", "-U", "--break-system-packages"] + missing, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Force l'update des extracteurs en arrière-plan (très rapide) pour contrer les patchs Bunkr
    subprocess.Popen([sys.executable, "-m", "pip", "install", "-U", "gallery-dl", "yt-dlp", "--break-system-packages"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
    try:
        subprocess.check_call(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"[{Colors.CYAN}ACTION{Colors.RESET}] FFmpeg manquant. Installation automatique via Homebrew...")
        try:
            subprocess.check_call(["brew", "install", "ffmpeg"])
        except Exception:
            print(f"[{Colors.RED}ERREUR{Colors.RESET}] Échec de l'installation de FFmpeg. Tapez 'brew install ffmpeg' manuellement.")

setup_environment()

import aiohttp
import aiofiles
import aiosqlite
from tqdm.asyncio import tqdm

# ====================== ARBORESCENCE & CONSTANTES ======================
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "config.json"
BASE_DIR = SCRIPT_DIR / "scrap"
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"
DB_DIR = BASE_DIR / "database"
LOG_FILE = LOGS_DIR / "scrap_system.log"
DB_FILE = DB_DIR / "scrap_resume.sqlite"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def get_random_headers(url: str, start: int, end: int) -> dict:
    spoofed_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    return {
        "Referer": url,
        "User-Agent": random.choice(USER_AGENTS),
        "Range": f"bytes={start}-{end}",
        "X-Forwarded-For": spoofed_ip,
        "X-Real-IP": spoofed_ip,
        "Accept-Encoding": "identity"
    }

# ====================== INITIALISATION ======================

def init_directories():
    for d in [BASE_DIR, DOWNLOADS_DIR, LOGS_DIR, DB_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def setup_logger():
    init_directories()
    logger = logging.getLogger("ScraperLogger")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s'))
        logger.addHandler(fh)
    return logger

LOGGER = setup_logger()

async def init_database():
    init_directories()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medias (
                media_id TEXT PRIMARY KEY,
                album_url TEXT,
                media_url TEXT,
                filename TEXT,
                media_type TEXT,
                status TEXT,
                target_path TEXT
            )
        """)
        await db.commit()

def generate_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]

def classify_media(url: str) -> str:
    url_lower = url.lower()
    if any(ext in url_lower for ext in VIDEO_EXTS) or "stream" in url_lower or "/v/" in url_lower:
        return "video"
    if any(ext in url_lower for ext in IMAGE_EXTS):
        return "image"
    return "file"

def clean_console():
    os.system('cls' if os.name == 'nt' else 'clear')

# ====================== INTÉGRITÉ & YT-DLP ======================

async def verify_video_integrity(file_path: Path) -> bool:
    if file_path.suffix.lower() not in VIDEO_EXTS:
        return True 
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=codec_type", "-of", "default=nw=1:nk=1", str(file_path)
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return "video" in stdout.decode().strip().lower()
    except Exception:
        return True

async def download_ytdlp_native(url: str, platform: str):
    target_dir = DOWNLOADS_DIR / platform
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{Colors.CYAN}🚀 Lancement yt-dlp pour {platform}...{Colors.RESET}")
    
    cmd = [
        "yt-dlp", "--no-check-certificate", "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4", "-o", f"{target_dir}/%(title)s [%(id)s].%(ext)s",
        "--console-title", url
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    if proc.returncode == 0:
        print(f"\n{Colors.GREEN}✅ Téléchargement terminé !{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}❌ Erreur yt-dlp.{Colors.RESET}")

# ====================== MOTEUR CRUISE CONTROL (FURTIF CONSTANT) ======================

async def update_media_status(media_id: str, status: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE medias SET status = ? WHERE media_id = ?", (status, media_id))
        await db.commit()

async def get_file_size(url: str, session: aiohttp.ClientSession) -> int:
    headers = {"Referer": url, "User-Agent": random.choice(USER_AGENTS), "Range": "bytes=0-0"}
    try:
        async with session.get(url, headers=headers, timeout=15) as resp:
            if resp.status == 206:
                cr = resp.headers.get("Content-Range", "")
                if "/" in cr: return int(cr.split("/")[1])
            elif resp.status == 200:
                return int(resp.headers.get("Content-Length", 0))
    except Exception:
        pass
    return 0

async def stealth_worker(queue: asyncio.Queue, session: aiohttp.ClientSession, url: str, pbar: tqdm):
    while True:
        try:
            start, end, part_path, attempt = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        expected_size = end - start + 1
        if part_path.exists() and part_path.stat().st_size == expected_size:
            pbar.update(expected_size)
            queue.task_done()
            continue

        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        headers = get_random_headers(url, start, end)
        success = False
        
        try:
            timeout = aiohttp.ClientTimeout(total=60, sock_read=30)
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status in (200, 206):
                    data = await resp.read()
                    if len(data) == expected_size:
                        async with aiofiles.open(part_path, 'wb') as f:
                            await f.write(data)
                        pbar.update(expected_size)
                        success = True
                elif resp.status in (403, 429):
                    await asyncio.sleep(5)
        except Exception:
            pass

        if not success:
            if attempt < 15:
                queue.put_nowait((start, end, part_path, attempt + 1))
            else:
                LOGGER.error(f"Abandon du segment {start}-{end}")

        queue.task_done()

async def download_file_stealth(media: Dict) -> bool:
    media_id = media["media_id"]
    url = media["media_url"]
    filename = media["filename"]
    output_path = Path(media["target_path"])
    
    await update_media_status(media_id, "DOWNLOADING")
    
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        total_size = await get_file_size(url, session)
        
        if total_size == 0:
            await update_media_status(media_id, "FAILED")
            return False

        CHUNK_SIZE = 10 * 1024 * 1024 
        WORKERS_COUNT = 3             

        queue = asyncio.Queue()
        num_chunks = 0
        
        for start in range(0, total_size, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE - 1, total_size - 1)
            part_path = Path(f"{output_path}.part{num_chunks}")
            queue.put_nowait((start, end, part_path, 0))
            num_chunks += 1

        short_name = filename[:30] + ".." if len(filename) > 32 else filename.ljust(32)
        pbar = tqdm(total=total_size, unit="o", unit_scale=True, unit_divisor=1024, desc=f"🚀 {short_name}", leave=True)

        tasks = [asyncio.create_task(stealth_worker(queue, session, url, pbar)) for _ in range(WORKERS_COUNT)]
        await queue.join()
        for task in tasks:
            task.cancel()
        pbar.close()

    missing_parts = any(not Path(f"{output_path}.part{i}").exists() for i in range(num_chunks))

    if not missing_parts:
        tqdm.write(f"{Colors.CYAN}⏳ Assemblage NVMe en cours...{Colors.RESET}")
        async with aiofiles.open(output_path, "wb") as outfile:
            for i in range(num_chunks):
                part_path = Path(f"{output_path}.part{i}")
                async with aiofiles.open(part_path, "rb") as infile:
                    await outfile.write(await infile.read())
                part_path.unlink()
        
        is_valid = await verify_video_integrity(output_path)
        if not is_valid:
            tqdm.write(f"{Colors.RED}❌ Fichier illisible détecté : {filename}. Suppression.{Colors.RESET}")
            output_path.unlink()
            await update_media_status(media_id, "FAILED")
            return False
            
        tqdm.write(f"{Colors.GREEN}✅ Terminé : {filename}{Colors.RESET}")
        await update_media_status(media_id, "COMPLETED")
        return True
    else:
        tqdm.write(f"{Colors.RED}❌ Échec de l'assemblage : {filename}{Colors.RESET}")
        await update_media_status(media_id, "FAILED")
        return False

# ====================== EXTRACTION AMÉLIORÉE (AVEC SPINNER) ======================

async def register_medias_in_db(album_url: str, target_dir: Path, raw_urls: List[str]) -> List[Dict]:
    medias = []
    async with aiosqlite.connect(DB_FILE) as db:
        for src in set(raw_urls):
            if not src or not src.startswith("http"): continue
            m_type = classify_media(src)
            ext = Path(urlparse(src).path).suffix.lower() or (".mp4" if m_type == "video" else ".png")
            media_id = generate_hash(src)
            filename = f"media_{m_type}_{media_id}{ext}"
            target_path = str(target_dir / filename)

            cursor = await db.execute("SELECT status FROM medias WHERE media_id = ?", (media_id,))
            row = await cursor.fetchone()
            media_dict = {"media_id": media_id, "album_url": album_url, "media_url": src, "filename": filename, "type": m_type, "status": "PENDING", "target_path": target_path}

            if row and row[0] == "COMPLETED" and Path(target_path).exists():
                continue 
            else:
                if not row:
                    await db.execute("INSERT INTO medias (media_id, album_url, media_url, filename, media_type, status, target_path) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                     (media_id, album_url, src, filename, m_type, "PENDING", target_path))
                medias.append(media_dict)
        await db.commit()
    return medias

async def show_spinner(message: str):
    """Animation visuelle pour prouver que l'extraction tourne."""
    chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    try:
        while True:
            sys.stdout.write(f"\r{Colors.YELLOW}{message} {chars[i % len(chars)]}{Colors.RESET}")
            sys.stdout.flush()
            await asyncio.sleep(0.1)
            i += 1
    except asyncio.CancelledError:
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

async def scrape_gallery_dl(url: str, platform: str) -> List[Dict]:
    if platform == "bunkr" and not url.startswith("http"): 
        url = f"https://bunkr.cr/a/{url}"
        
    print(f"\n{Colors.CYAN}🔍 Démarrage de l'extraction pour {platform}...{Colors.RESET}")
    
    spinner_task = asyncio.create_task(show_spinner("Analyse approfondie (Contournement Cloudflare en cours)"))
    
    cmd = [
        "gallery-dl", 
        "-g", 
        "--user-agent", random.choice(USER_AGENTS),
        url
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        spinner_task.cancel()
        print(f"{Colors.RED}❌ L'extraction a pris trop de temps (Timeout Cloudflare). Bunkr restreint ton accès temporairement.{Colors.RESET}")
        return []
    finally:
        spinner_task.cancel()
        await asyncio.sleep(0.1)
    
    if proc.returncode != 0:
        print(f"{Colors.RED}❌ Erreur d'extraction. Profil/Album introuvable ou protégé agressivement.{Colors.RESET}")
        return []

    target_dir = DOWNLOADS_DIR / platform
    target_dir.mkdir(parents=True, exist_ok=True)
    return await register_medias_in_db(url, target_dir, stdout.decode().strip().split('\n'))

async def process_downloads(medias: List[Dict]):
    if not medias:
        print(f"\n{Colors.GREEN}✔ Tous les fichiers sont déjà téléchargés.{Colors.RESET}")
        return

    videos = sum(1 for m in medias if m["type"] == "video")
    images = sum(1 for m in medias if m["type"] == "image")

    print("\n" + "=" * 55)
    print(f"{Colors.BOLD}{Colors.GREEN}📊 MÉDIAS EN ATTENTE{Colors.RESET}")
    print("=" * 55)
    print(f"🎬 Vidéos  : {Colors.BOLD}{videos}{Colors.RESET}")
    print(f"🖼️ Images  : {Colors.BOLD}{images}{Colors.RESET}")
    print(f"📦 Total   : {Colors.BOLD}{len(medias)}{Colors.RESET}")
    print("=" * 55)
    
    if input(f"\n{Colors.BOLD}Lancer le téléchargement ? (o/n) : {Colors.RESET}").strip().lower() in ["n", "no"]:
        return

    clean_console()
    print(f"{Colors.GREEN}🚀 Lancement du téléchargement (Cruise Control)...{Colors.RESET}\n")
    
    for i, media in enumerate(medias, start=1):
        print(f"\n{Colors.CYAN}Fichier {i}/{len(medias)}{Colors.RESET}")
        await download_file_stealth(media)

# ====================== MENU CLI ======================

async def main_loop():
    await init_database()
    while True:
        print("\n" + "=" * 65)
        print(f"{Colors.BOLD}{Colors.RED}🔥 STEALTH-SCRAPER (CRUISE CONTROL) 🔥{Colors.RESET}")
        print("=" * 65)
        print("1. Sites Streaming -> [Natif yt-dlp]")
        print("2. Bunkr / Albums  -> [Moteur Furtif Constant]")
        print("3. Quitter")
        print("=" * 65)
        
        choice = input("Choisissez une option : ").strip()
        if choice == "3": break
        if choice not in ["1", "2"]: continue
            
        url = input(f"\n{Colors.BOLD}URL exacte : {Colors.RESET}").strip()
        if choice == "1":
            await download_ytdlp_native(url, "streaming")
        elif choice == "2":
            medias = await scrape_gallery_dl(url, "bunkr")
            await process_downloads(medias)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        sys.exit(0)