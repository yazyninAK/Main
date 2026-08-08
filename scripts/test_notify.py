"""Send a one-off test notification through the real notify pipeline
(Telegram + GitHub issue), without touching scraping or state. Used by the
workflow's manual "test_notification" input to verify delivery end-to-end."""
from __future__ import annotations

from notify import notify_new_post

TEST_POST = {
    "title": "Cube Reaction Pro 1x12 (XL) -800Wh,Cx5,Papiri,2026",
    "url": (
        "https://2bike.rs/cikloberza/mali-oglasi/bicikli-6/"
        "elektricni-bicikli-13/cube-reaction-pro-1x12-xl-800wh-cx5-papiri-2026"
    ),
    "price": "BEZ CENE (не указана)",
    "seller": "(aleksaloznica) - Loznica, RS",
}

if __name__ == "__main__":
    notify_new_post(TEST_POST)
    print("Test notification sent (see messages above for per-channel status).")
