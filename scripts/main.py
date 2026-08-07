"""Entry point: fetch posts, filter, notify about new matches, persist state."""
from __future__ import annotations

import json
import pathlib

import yaml

from notify import notify_new_post
from scraper import fetch_posts

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "data" / "seen.json"


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


def matches_filters(post: dict, filters: list[dict]) -> bool:
    haystack = f"{post.get('title', '')} {post.get('text', '')}".lower()
    for group in filters:
        candidates = group.get("any_of", [])
        if not any(word.lower() in haystack for word in candidates):
            return False
    return True


def main() -> None:
    config = load_config()
    seen = load_seen()

    posts = fetch_posts(config["url"])
    new_posts = [p for p in posts if p["id"] not in seen]

    matched = [p for p in new_posts if matches_filters(p, config.get("filters", []))]

    for post in matched:
        notify_new_post(post)

    # Mark ALL fetched posts as seen (not just matched ones) so we don't
    # re-notify about posts that didn't match, and don't re-check them later.
    seen.update(p["id"] for p in posts)
    save_seen(seen)

    print(f"Fetched {len(posts)} posts, {len(new_posts)} new, {len(matched)} matched filters.")


if __name__ == "__main__":
    main()
