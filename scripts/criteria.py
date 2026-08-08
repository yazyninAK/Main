"""Numeric/structural criteria: battery capacity, mileage, frame size.

The site doesn't expose these as filters, so we parse them out of the ad's
text with regexes. This is a heuristic, not exact parsing: a criterion only
REJECTS a post when a value IS found in the text and it violates the
threshold. A missing/unclear mention never rejects on its own - better to
show a possible match than silently drop a real one due to a parsing miss.
"""
from __future__ import annotations

import re

_BATTERY_WH_RE = re.compile(r"(\d{3,4})\s*wh\b", re.IGNORECASE)
_MILEAGE_KM_RE = re.compile(r"(\d{1,6})\s*km\b(?!\s*/\s*h)", re.IGNORECASE)
_FRAME_SIZE_TEMPLATE = r"(?<![a-zA-Zа-яА-Я0-9])({size})(?![a-zA-Zа-яА-Я0-9])"


def max_battery_wh(text: str) -> int | None:
    values = [int(m) for m in _BATTERY_WH_RE.findall(text)]
    return max(values) if values else None


def mileage_candidates_km(text: str) -> list[int]:
    """All "<number> km" mentions in the text, excluding "km/h" speed specs."""
    return [int(m) for m in _MILEAGE_KM_RE.findall(text)]


def mentions_frame_size(text: str, size: str) -> bool:
    pattern = re.compile(_FRAME_SIZE_TEMPLATE.format(size=re.escape(size)), re.IGNORECASE)
    return bool(pattern.search(text))


def matches_criteria(text: str, criteria: dict) -> bool:
    battery_min = criteria.get("battery_wh_min")
    if battery_min is not None:
        found = max_battery_wh(text)
        if found is not None and found < battery_min:
            return False

    mileage_max = criteria.get("mileage_km_max")
    if mileage_max is not None:
        candidates = mileage_candidates_km(text)
        # Reject only if EVERY "km" figure in the text is over the cap -
        # a single low number (delivery radius, a missed "km/h" variant,
        # etc.) is treated as noise rather than proof the bike is fine.
        if candidates and min(candidates) > mileage_max:
            return False

    frame_sizes = criteria.get("frame_sizes") or []
    if frame_sizes and not any(mentions_frame_size(text, size) for size in frame_sizes):
        return False

    return True
