"""Fetch and parse post listings from 2bike.rs (cikloberza mali oglasi)."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://2bike.rs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

FAV_ID_RE = re.compile(r"add_favorite_classified/(\d+)")


def _absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def page_url(url: str, page: int) -> str:
    if page <= 1:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}page={page}"


def fetch_posts(url: str) -> list[dict]:
    """Return one results page of posts: id, title, url, price, seller.

    The listing is sorted by "date posted/renewed" descending by default,
    so new posts appear at the top of page 1.
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    posts = []
    for item in soup.select("ul.itemsGrid > li"):
        title_link = item.select_one("h2 a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        post_url = _absolute_url(title_link.get("href", ""))

        fav_link = item.select_one("a.clsfdaddtofavs")
        post_id = None
        if fav_link and fav_link.get("data-href-add"):
            m = FAV_ID_RE.search(fav_link["data-href-add"])
            if m:
                post_id = m.group(1)
        if not post_id:
            post_id = post_url

        price_el = item.select_one(".strp em")
        price = price_el.get_text(" ", strip=True) if price_el else ""

        seller_el = item.select_one(".dsc span")
        seller = seller_el.get_text(" ", strip=True) if seller_el else ""

        posts.append(
            {
                "id": post_id,
                "title": title,
                "url": post_url,
                "price": price,
                "seller": seller,
                "text": title,  # replaced with full detail text for new posts
            }
        )
    return posts


def fetch_detail_text(url: str) -> str:
    """Return the visible text of a single ad's page, for keyword matching."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    return " ".join(soup.get_text(" ", strip=True).split())
