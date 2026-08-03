"""
Modules package for NSFW-Scraper.
Each site has its own module (e.g., bunkr.py, ph.py).
To add a new site:
1. Create a new file in this directory (e.g., newsite.py).
2. Define a `DESCRIPTION` string and an `async def scrape(url)` function.
3. Add the module name to `MODULES` dict in main.py.
"""
