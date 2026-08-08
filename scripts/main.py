"""Entry point: fetch posts, filter, notify about new matches, persist state."""
from __future__ import annotations

import json
import pathlib
import time

import yaml

from notify import notify_new_post
from scraper import fetch_detail_text, fetch_posts, page_url

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "data" / "seen.json"

# Safety cap on how many new posts get a detail-page fetch in one run,
# to avoid hammering the site if a lot of new posts appear at once.
MAX_DETAIL_FETCHES_PER_RUN = 30
DETAIL_FETCH_DELAY_SECONDS = 1.5

# Listing is sorted newest-first, so we page forward only until we hit a
# post we've already seen (or run out of pages / hit this safety cap).
MAX_LISTING_PAGES = 10


def fetch_new_listing_posts(base_url: str, seen: set[str]) -> list[dict]:
    all_posts: list[dict] = []
    for page in range(1, MAX_LISTING_PAGES + 1):
        posts = fetch_posts(page_url(base_url, page))
        if not posts:
            break
        all_posts.extend(posts)
        if any(p["id"] in seen for p in posts):
            break
    return all_posts


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    with open(STATE_PATH, encoding="utf-8") as f:
        return set(json.load(f))


def save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def matches_filters(text: str, filters: list[dict]) -> bool:
    haystack = text.lower()
    for group in filters:
        candidates = group.get("any_of", [])
        if not any(word.lower() in haystack for word in candidates):
            return False
    return True


def main() -> None:
    config = load_config()
    seen = load_seen()

    posts = fetch_new_listing_posts(config["url"], seen)
    new_posts = [p for p in posts if p["id"] not in seen]

    matched = []
    for post in new_posts[:MAX_DETAIL_FETCHES_PER_RUN]:
        try:
            detail_text = fetch_detail_text(post["url"])
        except Exception as exc:  # noqa: BLE001 - keep the run going for other posts
            print(f"Failed to fetch detail page for {post['url']}: {exc}")
            detail_text = ""
        post["text"] = f"{post['title']} {detail_text}"

        if matches_filters(post["text"], config.get("filters", [])):
            matched.append(post)

        time.sleep(DETAIL_FETCH_DELAY_SECONDS)

    for post in matched:
        notify_new_post(post)

    # Mark ALL fetched posts as seen (not just matched ones) so we don't
    # re-check or re-notify about them on later runs.
    seen.update(p["id"] for p in posts)
    save_seen(seen)

    print(f"Fetched {len(posts)} posts, {len(new_posts)} new, {len(matched)} matched filters.")


if __name__ == "__main__":
    main()
