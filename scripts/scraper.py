"""Fetch and parse post listings from the target site.

NOTE: The selectors below are placeholders. They must be adjusted to match
the real HTML structure of the target page before this will find any posts.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class ScraperNotConfigured(RuntimeError):
    pass


def fetch_posts(url: str) -> list[dict]:
    """Return a list of posts: {"id": str, "title": str, "url": str, "text": str}.

    "id" must be a stable identifier for the post (e.g. its URL) so we can
    detect which posts were already seen on previous runs.
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # TODO: replace with real selectors once the page markup is known.
    raise ScraperNotConfigured(
        "scraper.py: selectors are not configured yet for this site. "
        "Inspect the page HTML and update fetch_posts() in scripts/scraper.py."
    )
