"""
Bunkr module for NSFW-Scraper.
Extracts media URLs from Bunkr albums (often used for leaks).
"""

import subprocess
from pathlib import Path
from typing import List, Dict
from config import USER_AGENTS, DOWNLOADS_DIR, generate_hash, classify_media

DESCRIPTION = "Bunkr - Albums and media (Cloudflare bypass, often used for leaks)"

async def scrape(url: str) -> List[Dict]:
    """
    Extract media URLs from a Bunkr album.
    Args:
        url: Bunkr album URL (e.g., https://bunkr.cr/a/abc123).
    Returns:
        List of media dictionaries with keys:
        - media_id: Unique ID (hash)
        - album_url: URL of the album
        - media_url: URL of the media
        - filename: Filename
        - type: "video" or "image"
        - status: "PENDING"
        - target_path: Destination path
        - module: "bunkr"
    """
    if not url.startswith("http"):
        url = f"https://bunkr.cr/a/{url}"

    print(f"\n🔍 Extracting URLs from Bunkr: {url}")

    # Use gallery-dl to extract URLs
    cmd = [
        "gallery-dl",
        "-g",
        "--user-agent", USER_AGENTS[0],
        "--get-urls",  # Critical option to get URLs
        url
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120  # Bunkr can be slow
        )
        stdout, stderr = proc.communicate()
    except subprocess.TimeoutExpired:
        print("❌ Timeout: gallery-dl took too long (Bunkr may be rate-limiting).")
        return []
    except Exception as e:
        print(f"❌ Error running gallery-dl: {e}")
        return []

    if proc.returncode != 0:
        print(f"❌ gallery-dl error: {stderr.decode().strip()}")
        return []

    # Parse URLs
    urls = [line.strip() for line in stdout.decode().split('\n') if line.strip() and line.startswith("http")]
    if not urls:
        print("❌ No media found. Album may be private or empty.")
        return []

    # Prepare media list
    medias = []
    target_dir = DOWNLOADS_DIR / "bunkr"
    target_dir.mkdir(parents=True, exist_ok=True)

    for src in urls:
        m_type = classify_media(src)
        ext = Path(src).suffix.lower() or (".mp4" if m_type == "video" else ".jpg")
        media_id = generate_hash(src)
        filename = f"bunkr_{media_id}{ext}"
        target_path = str(target_dir / filename)

        medias.append({
            "media_id": media_id,
            "album_url": url,
            "media_url": src,
            "filename": filename,
            "type": m_type,
            "status": "PENDING",
            "target_path": target_path,
            "module": "bunkr"
        })

    return medias
