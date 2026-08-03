"""
PornHub module for NSFW-Scraper.
Extracts video URLs from PornHub (free content).
"""

import subprocess
import json
from pathlib import Path
from typing import List, Dict
from config import USER_AGENTS, DOWNLOADS_DIR, generate_hash, classify_media

DESCRIPTION = "PornHub - Free videos (via yt-dlp)"

async def scrape(url: str) -> List[Dict]:
    """
    Extract video URLs from PornHub.
    Args:
        url: PornHub video URL (e.g., https://www.pornhub.com/view_video.php?viewkey=abc123).
    Returns:
        List of media dictionaries.
    """
    print(f"\n🔍 Extracting URLs from PornHub: {url}")

    # Use yt-dlp to get video info
    cmd = [
        "yt-dlp",
        "--no-check-certificate",
        "-j",  # JSON output
        "--flat-playlist",  # Single video
        "--user-agent", USER_AGENTS[0],
        url
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        stdout, stderr = proc.communicate()
    except subprocess.TimeoutExpired:
        print("❌ Timeout: yt-dlp took too long.")
        return []
    except Exception as e:
        print(f"❌ Error running yt-dlp: {e}")
        return []

    if proc.returncode != 0:
        print(f"❌ yt-dlp error: {stderr.decode().strip()}")
        return []

    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError:
        print("❌ Invalid JSON output from yt-dlp.")
        return []

    media_url = data.get("url")
    if not media_url:
        print("❌ No download URL found.")
        return []

    title = data.get("title", "unknown").replace("/", "_").replace("\\", "_")
    ext = data.get("ext", "mp4")
    media_id = generate_hash(media_url)
    filename = f"ph_{title[:50]}_{media_id}.{ext}"
    target_dir = DOWNLOADS_DIR / "ph"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = str(target_dir / filename)

    return [{
        "media_id": media_id,
        "album_url": url,
        "media_url": media_url,
        "filename": filename,
        "type": "video",
        "status": "PENDING",
        "target_path": target_path,
        "module": "ph"
    }]
