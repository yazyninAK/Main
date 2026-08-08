"""Fetch and parse post listings from 2bike.rs (cikloberza mali oglasi)."""
from __future__ import annotations

import re
import time
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://2bike.rs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

FAV_ID_RE = re.compile(r"add_favorite_classified/(\d+)")

# A shared session persists cookies (some sites gate real pages behind a
# cookie set on the first visit) and TCP connections across all requests
# made in one script run.
_session = requests.Session()
_session.headers.update(HEADERS)
_warmed_up = False


def _debug_response(resp: requests.Response) -> None:
    """Print diagnostic info on a failed response, to tell apart a WAF/CDN
    block (Cloudflare etc.) from a plain server-side 403."""
    interesting_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() in ("server", "cf-ray", "cf-mitigated", "x-sucuri-id", "content-type")
    }
    print(f"DEBUG: {resp.request.method} {resp.url} -> {resp.status_code}")
    print(f"DEBUG: response headers of interest: {interesting_headers}")
    print(f"DEBUG: body snippet: {resp.text[:500]!r}")


def _warm_up() -> None:
    """Visit the homepage once per run before hitting category/detail pages,
    so any cookie the site sets on first contact is already in the session."""
    global _warmed_up
    if _warmed_up:
        return
    try:
        resp = _session.get(BASE_URL, timeout=30)
        print(f"DEBUG: warm-up GET {BASE_URL} -> {resp.status_code}")
        if not resp.ok:
            _debug_response(resp)
    except requests.RequestException as exc:
        print(f"DEBUG: warm-up request failed: {exc}")
    _warmed_up = True


def _get(url: str, retries: int = 2, backoff_seconds: float = 3.0) -> requests.Response:
    _warm_up()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, headers={"Referer": BASE_URL + "/"}, timeout=30)
            if not resp.ok:
                _debug_response(resp)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def _absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def _clean(text: str) -> str:
    """Collapse any run of whitespace (incl. stray tabs/newlines the site's
    markup sometimes leaves in a single text node) into single spaces."""
    return " ".join(text.split())

# Bicycle brand ("PROIZVOĐAČ") filter ids, as used by the site's own
# left-side filter panel (query param bra[]=<id>). Scraped from the
# category filter sidebar; extend this if the site adds a brand that's
# missing here.
BRAND_IDS = {
    "Alpina": 552, "BMC": 79, "Batavus": 575, "Bergamont": 577, "Bianchi": 536,
    "Bosch": 578, "Bulls": 537, "Cannondale": 95, "Canyon": 524, "Capriolo": 517,
    "Centurion": 579, "Cervelo": 100, "Colnago": 113, "Commencal": 115,
    "Corratec": 120, "Cube": 127, "Felt": 178, "Focus": 540, "Fuji": 199,
    "GT": 221, "Gazelle": 601, "Genesis": 542, "Ghost": 211, "Giant": 212,
    "KTM": 530, "Kettler": 602, "Koga": 258, "Kona": 259,
    "Light and Motion": 267, "Lizard Skins": 268, "Look": 271, "Merida": 526,
    "Nukeproof": 318, "Orca": 327, "Pinarello": 336, "Polar": 340,
    "Raleigh": 360, "Ridley": 372, "Scott": 394, "Scout": 584, "Shimano": 403,
    "Simplon": 585, "Specialized": 543, "Stevens": 551, "Trek": 514,
    "Univega": 588, "Vitus Bikes": 490, "Wheeler": 545, "Wilier": 589,
    "Winora": 590,
}


def build_listing_url(site_config: dict) -> str:
    """Build the listing URL from named filter fields (config.yaml `site:`).

    Mirrors the site's own left-side filter panel: hide_sold -> hideSold=1,
    hide_no_price -> hasPrice=1, brands -> bra[]=<id> (see BRAND_IDS),
    price_min/price_max/price_currency -> prfr/prto/prcu.
    """
    base = site_config["category_url"]
    params: list[tuple[str, str]] = []

    if site_config.get("hide_sold"):
        params.append(("hideSold", "1"))
    if site_config.get("hide_no_price"):
        params.append(("hasPrice", "1"))

    for brand in site_config.get("brands") or []:
        brand_id = BRAND_IDS.get(brand)
        if brand_id is None:
            known = ", ".join(sorted(BRAND_IDS))
            raise ValueError(f"Unknown brand '{brand}' in config.yaml. Known brands: {known}")
        params.append(("bra[]", str(brand_id)))

    price_min = site_config.get("price_min")
    price_max = site_config.get("price_max")
    if price_min is not None:
        params.append(("prfr", str(price_min)))
    if price_max is not None:
        params.append(("prto", str(price_max)))
    if price_min is not None or price_max is not None:
        params.append(("prcu", site_config.get("price_currency", "EUR")))

    if not params:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urlencode(params)}"


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
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    posts = []
    for item in soup.select("ul.itemsGrid > li"):
        title_link = item.select_one("h2 a")
        if not title_link:
            continue

        title = _clean(title_link.get_text(" ", strip=True))
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
        price = _clean(price_el.get_text(" ", strip=True)) if price_el else ""

        seller_el = item.select_one(".dsc span")
        seller = _clean(seller_el.get_text(" ", strip=True)) if seller_el else ""

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
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    return " ".join(soup.get_text(" ", strip=True).split())
