"""
Credit rating utilities for the NBFC scorecard.

Converts agency ratings (AAA through D) into an internal numeric score
where higher values indicate stronger credit quality.
"""

from __future__ import annotations

import re

# Internal score for each supported rating (0-100 scale)
RATING_SCORES: dict[str, int] = {
    "AAA": 100,
    "AA+": 95,
    "AA": 90,
    "AA-": 85,
    "A+": 80,
    "A": 75,
    "A-": 70,
    "BBB+": 65,
    "BBB": 60,
    "BBB-": 55,
    "BB+": 50,
    "BB": 45,
    "BB-": 40,
    "B+": 35,
    "B": 30,
    "B-": 25,
    "C": 15,
    "D": 0,
}

# Explicit order: longer / more specific ratings first so "AA+" matches before "AA"
_RATING_ORDER = [
    "AAA",
    "AA+",
    "AA-",
    "AA",
    "A+",
    "A-",
    "A",
    "BBB+",
    "BBB-",
    "BBB",
    "BB+",
    "BB-",
    "BB",
    "B+",
    "B-",
    "B",
    "C",
    "D",
]

# Note: word boundaries (\b) break ratings like "AA+" because "+" is non-word.
_RATING_PATTERN = re.compile(
    "(" + "|".join(re.escape(rating) for rating in _RATING_ORDER) + ")",
    re.IGNORECASE,
)


def normalize_credit_rating(value) -> str | None:
    """
    Normalize a credit rating string to standard form (e.g. 'AA+').

    Returns None when the value is empty or not a recognized rating.
    """
    if value is None:
        return None

    text = str(value).strip().upper()
    if not text or text in {"NA", "N/A", "-", "NONE", "NULL"}:
        return None

    # Exact match after removing spaces (e.g. "AA+", "BBB-")
    compact = text.replace(" ", "")
    for rating in _RATING_ORDER:
        if compact == rating.upper():
            return rating

    match = _RATING_PATTERN.search(text)
    if match:
        matched = match.group(1).upper()
        for rating in _RATING_ORDER:
            if matched == rating.upper():
                return rating

    return None


def rating_to_score(rating: str | None) -> int | None:
    """Convert a normalized credit rating to an internal score (0-100)."""
    if rating is None:
        return None

    normalized = normalize_credit_rating(rating)
    if normalized is None:
        return None

    return RATING_SCORES.get(normalized)


def extract_rating_from_text(text: str) -> str | None:
    """Find the first supported credit rating in a block of text."""
    if not text:
        return None

    match = _RATING_PATTERN.search(text)
    if match:
        return match.group(1).upper()

    return None
