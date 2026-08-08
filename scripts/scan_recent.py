"""One-off manual scan: check a broad slice of a filter profile's category
against that profile, and send the results as a single numbered-link
digest instead of one notification per post. Doesn't touch data/seen.json
or the regular new-post detection - purely a manual "what's out there"
check.

The site doesn't expose per-item post/renewal dates in the listing
markup, so there's no exact way to cut off "the last month" - this scans
a bounded number of listing pages (newest first, per the site's own
default sort) instead, which is an approximation, not an exact date filter.
"""
from __future__ import annotations

import os
import time

import yaml

from criteria import matches_criteria, parse_price_eur
from main import matches_filters
from notify import notify_digest
from scraper import build_listing_url, fetch_detail_text, fetch_posts, page_url

CONFIG_PATH = "config.yaml"
FILTER_NAME = os.environ.get("SCAN_FILTER_NAME", "Карбоновый Мтб до 1000е")
MAX_PAGES = int(os.environ.get("SCAN_MAX_PAGES", "15"))
DETAIL_FETCH_DELAY_SECONDS = 1.5


def load_profile(name: str) -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    for profile in config.get("filters", []):
        if profile.get("name") == name:
            return profile
    known = ", ".join(p.get("name", "?") for p in config.get("filters", []))
    raise SystemExit(f"Filter profile '{name}' not found in config.yaml. Known: {known}")


def quick_reject(post: dict, criteria: dict) -> bool:
    """Reject without a detail-page fetch when the listing price alone
    already disqualifies the post, regardless of what the description says."""
    price_max = criteria.get("price_eur_max")
    if price_max is not None:
        price = parse_price_eur(post.get("price", ""))
        if price is not None and price > price_max:
            return True
    return False


def main() -> None:
    profile = load_profile(FILTER_NAME)
    url = build_listing_url(profile["site"])
    criteria = profile.get("criteria", {})

    matches: list[dict] = []
    total_scanned = 0
    for page in range(1, MAX_PAGES + 1):
        posts = fetch_posts(page_url(url, page))
        if not posts:
            break
        for post in posts:
            total_scanned += 1
            if quick_reject(post, criteria):
                continue
            try:
                detail_text = fetch_detail_text(post["url"])
            except Exception as exc:  # noqa: BLE001 - keep scanning the rest
                print(f"Failed to fetch detail page for {post['url']}: {exc}")
                detail_text = ""
            post["text"] = f"{post['title']} {detail_text}"

            if matches_filters(post["text"], profile) and matches_criteria(post, criteria):
                matches.append(post)

            time.sleep(DETAIL_FETCH_DELAY_SECONDS)

    print(f"Scanned {total_scanned} listings across up to {MAX_PAGES} pages, {len(matches)} matched '{FILTER_NAME}'.")
    digest_title = f"Скан: {FILTER_NAME} (последние ~{total_scanned} объявлений в категории)"
    notify_digest(digest_title, matches)


if __name__ == "__main__":
    main()
