"""Numeric/structural criteria: battery capacity, mileage, frame size,
frame material, price. The site doesn't expose these as filters, so we
parse them out of the ad's text/price with regexes.

All of these are heuristics, not exact parsing, and all follow the same
soft rule: a criterion only REJECTS a post when the ad clearly states a
value that violates it. If the seller simply didn't mention battery
capacity, frame size, frame material, or price at all, that is not
evidence against the post - it stays in, so a real match never gets
silently dropped over an incomplete ad.
"""
from __future__ import annotations

import re

_BATTERY_WH_RE = re.compile(r"(\d{3,4})\s*wh\b", re.IGNORECASE)
_MILEAGE_KM_RE = re.compile(r"(\d{1,6})\s*km\b(?!\s*/\s*h)", re.IGNORECASE)
_TOKEN_TEMPLATE = r"(?<![a-zA-Zа-яА-Я0-9])({token})(?![a-zA-Zа-яА-Я0-9])"

_ALL_FRAME_SIZES = ["xxs", "xs", "s", "m", "l", "xl", "xxl"]

_FRAME_MATERIALS = {
    "carbon": ["carbon", "karbon", "karbonska", "karbonski", "carbon fiber", "karbon rama"],
    "aluminum": ["aluminijum", "aluminijumski", "alu rama", "alu okvir", "aluminum"],
    "steel": ["celik", "čelik", "celicna", "čelična", "cromoly", "chromoly", "krom-molibden"],
    "titanium": ["titan", "titanijum"],
}

_PRICE_EUR_RE = re.compile(r"([\d](?:[\d.,]*\d)?)\s*eur", re.IGNORECASE)


def _mentions_token(text: str, token: str) -> bool:
    pattern = re.compile(_TOKEN_TEMPLATE.format(token=re.escape(token)), re.IGNORECASE)
    return bool(pattern.search(text))


def max_battery_wh(text: str) -> int | None:
    values = [int(m) for m in _BATTERY_WH_RE.findall(text)]
    return max(values) if values else None


def mileage_candidates_km(text: str) -> list[int]:
    """All "<number> km" mentions in the text, excluding "km/h" speed specs."""
    return [int(m) for m in _MILEAGE_KM_RE.findall(text)]


def mentioned_frame_sizes(text: str) -> set[str]:
    """Which known frame-size letters (XXS..XXL) are mentioned in the text."""
    return {size.upper() for size in _ALL_FRAME_SIZES if _mentions_token(text, size)}


def mentioned_frame_materials(text: str) -> set[str]:
    """Which known frame materials are mentioned in the text."""
    haystack = text.lower()
    return {material for material, words in _FRAME_MATERIALS.items() if any(w in haystack for w in words)}


def parse_price_eur(price_text: str) -> float | None:
    """Parse a price like "1.100 EUR" (Serbian thousands-separator ".") into
    1100.0. Returns None if no EUR price is present (e.g. "BEZ CENE" or a
    price stated in another currency)."""
    if not price_text:
        return None
    m = _PRICE_EUR_RE.search(price_text)
    if not m:
        return None
    number = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def matches_criteria(post: dict, criteria: dict) -> bool:
    text = post.get("text", "")

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
    if frame_sizes:
        allowed = {s.upper() for s in frame_sizes}
        mentioned = mentioned_frame_sizes(text)
        # Reject only if the ad explicitly states a size and it's not one
        # of the allowed ones. No size mentioned at all -> not rejected.
        if mentioned and not (mentioned & allowed):
            return False

    frame_materials = criteria.get("frame_materials") or []
    if frame_materials:
        allowed = {m.lower() for m in frame_materials}
        mentioned = mentioned_frame_materials(text)
        # Same soft rule: reject only if a material IS stated and it's not
        # one of the allowed ones. Unstated material -> not rejected.
        if mentioned and not (mentioned & allowed):
            return False

    price_max = criteria.get("price_eur_max")
    if price_max is not None:
        price = parse_price_eur(post.get("price", ""))
        if price is not None and price > price_max:
            return False

    return True
