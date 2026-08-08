"""Entry point: fetch posts, filter, notify about new matches, persist state."""
from __future__ import annotations

import json
import pathlib
import time

import yaml

from criteria import matches_criteria
from notify import notify_new_post
from scraper import build_listing_url, close_browser, fetch_detail_text, fetch_posts, page_url

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "data" / "seen.json"

# Safety cap on how many new posts get a detail-page fetch in one run,
# to avoid hammering the site if a lot of new posts appear at once.
MAX_DETAIL_FETCHES_PER_RUN = 30
# Fetches now go through a real browser (page load itself takes a few
# seconds), so this is just a small courtesy pause, not the main throttle.
DETAIL_FETCH_DELAY_SECONDS = 0.5

# Listing is sorted by "date renewed/bumped" (not by creation date), so we
# page forward only until we hit a post we've already recorded, or run out
# of pages / hit this safety cap.
MAX_LISTING_PAGES = 10


def fetch_new_listing_posts(base_url: str, seen_ids: set[str]) -> list[dict]:
    all_posts: list[dict] = []
    for page in range(1, MAX_LISTING_PAGES + 1):
        posts = fetch_posts(page_url(base_url, page))
        if not posts:
            break
        all_posts.extend(posts)
        if any(p["id"] in seen_ids for p in posts):
            break
    return all_posts


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> tuple[set[str], int]:
    if not STATE_PATH.exists():
        return set(), 0
    with open(STATE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("seen_ids", [])), int(data.get("max_known_id", 0))


def save_state(seen_ids: set[str], max_known_id: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"seen_ids": sorted(seen_ids), "max_known_id": max_known_id},
            f,
            ensure_ascii=False,
            indent=2,
        )


def numeric_id(post: dict) -> int | None:
    try:
        return int(post["id"])
    except (TypeError, ValueError):
        return None


def matches_filters(text: str, profile: dict) -> bool:
    haystack = text.lower()

    exclude_any = profile.get("exclude_any", [])
    if any(word.lower() in haystack for word in exclude_any):
        return False

    for group in profile.get("must_include", []):
        candidates = group.get("any_of", [])
        if not any(word.lower() in haystack for word in candidates):
            return False

    return True


def matched_filter_names(post: dict, filters: list[dict]) -> list[str]:
    """Names of every filter profile (from config.yaml `filters:`) that
    this post matches. A post can match more than one profile."""
    names = []
    for profile in filters:
        if matches_filters(post["text"], profile) and matches_criteria(post, profile.get("criteria", {})):
            names.append(profile.get("name", "(без имени)"))
    return names


def fetch_posts_for_all_filters(filters: list[dict], seen_ids: set[str]) -> list[dict]:
    """Each filter profile has its own `site` (category/URL) - fetch each
    distinct listing URL once and pool the results, deduped by post id."""
    urls = {build_listing_url(profile["site"]) for profile in filters}
    posts_by_id: dict[str, dict] = {}
    for url in urls:
        for post in fetch_new_listing_posts(url, seen_ids):
            posts_by_id.setdefault(post["id"], post)
    return list(posts_by_id.values())


def main() -> None:
    config = load_config()
    is_first_run = not STATE_PATH.exists()
    seen_ids, max_known_id = load_state()

    try:
        posts = fetch_posts_for_all_filters(config.get("filters", []), seen_ids)

        # A post only counts as genuinely new if we haven't recorded its id
        # before AND its id is higher than any id we've seen so far. The
        # second condition weeds out old ads that were merely renewed/bumped
        # back to the top of the (renewal-sorted) listing — those aren't
        # "new posts".
        genuinely_new = [
            p
            for p in posts
            if p["id"] not in seen_ids
            and (numeric_id(p) is None or numeric_id(p) > max_known_id)
        ]

        matched = []
        if is_first_run:
            print("First run: establishing baseline, no notifications will be sent.")
        else:
            for post in genuinely_new[:MAX_DETAIL_FETCHES_PER_RUN]:
                try:
                    detail_text = fetch_detail_text(post["url"])
                except Exception as exc:  # noqa: BLE001 - keep the run going for other posts
                    print(f"Failed to fetch detail page for {post['url']}: {exc}")
                    detail_text = ""
                post["text"] = f"{post['title']} {detail_text}"

                names = matched_filter_names(post, config.get("filters", []))
                if names:
                    post["matched_filters"] = names
                    matched.append(post)

                time.sleep(DETAIL_FETCH_DELAY_SECONDS)

            for post in matched:
                notify_new_post(post)
    finally:
        close_browser()

    # Record everything we fetched (matched or not, new or just a bumped
    # old ad) so future runs don't re-check or re-notify about it.
    seen_ids.update(p["id"] for p in posts)
    fetched_ids = [n for n in (numeric_id(p) for p in posts) if n is not None]
    new_max_known_id = max([max_known_id, *fetched_ids])
    save_state(seen_ids, new_max_known_id)

    print(
        f"Fetched {len(posts)} posts, {len(genuinely_new)} genuinely new, "
        f"{len(matched)} matched filters."
    )


if __name__ == "__main__":
    main()
