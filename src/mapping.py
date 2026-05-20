"""
Financial label mapping with fuzzy matching.

Maps report-specific line items to standardized field names used
by the credit scorecard (net_income, total_equity, gnpa, etc.).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from src.config import (
    FIELD_LABEL_ALIASES,
    FUZZY_MATCH_THRESHOLD,
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    MEDIUM_CONFIDENCE,
)


def normalize_label(text: str) -> str:
    """
    Normalize a financial line-item label for matching.

    - Lowercase
    - Remove extra whitespace and line breaks
    - Remove special characters except spaces
    """
    if not text:
        return ""

    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def _compact_label(text: str) -> str:
    """Remove all spaces for compact matching."""
    return normalize_label(text).replace(" ", "")


def _build_alias_lookup() -> dict[str, tuple[str, float]]:
    """
    Build lookup: compact alias -> (standard_field, base_confidence).
    Exact alias matches get high confidence.
    """
    lookup: dict[str, tuple[str, float]] = {}

    for standard_field, aliases in FIELD_LABEL_ALIASES.items():
        lookup[_compact_label(standard_field)] = (standard_field, HIGH_CONFIDENCE)
        for alias in aliases:
            lookup[_compact_label(alias)] = (standard_field, HIGH_CONFIDENCE)

    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def _fuzzy_score(label_a: str, label_b: str) -> float:
    """Return similarity ratio between two labels (0-1)."""
    return SequenceMatcher(None, label_a, label_b).ratio()


def map_label_to_field(
    raw_label: str,
    *,
    section: str = "unknown",
) -> tuple[str | None, float]:
    """
    Map a report line-item label to a standardized field name.

    Returns:
        (standard_field, confidence) or (None, 0.0) if no match.
    """
    if not raw_label or not str(raw_label).strip():
        return None, 0.0

    compact = _compact_label(raw_label)
    if not compact:
        return None, 0.0

    # Exact alias match
    if compact in _ALIAS_LOOKUP:
        field_name, confidence = _ALIAS_LOOKUP[compact]
        return field_name, confidence

    # Fuzzy match against all aliases
    best_field: str | None = None
    best_score = 0.0

    for alias_compact, (standard_field, _) in _ALIAS_LOOKUP.items():
        score = _fuzzy_score(compact, alias_compact)
        if score > best_score:
            best_score = score
            best_field = standard_field

    if best_field and best_score >= FUZZY_MATCH_THRESHOLD:
        if best_score >= 0.90:
            confidence = HIGH_CONFIDENCE
        elif best_score >= 0.80:
            confidence = MEDIUM_CONFIDENCE
        else:
            confidence = LOW_CONFIDENCE

        # Slight boost when section context matches
        if section in {"balance_sheet", "profit_and_loss", "asset_quality", "capital_adequacy"}:
            confidence = min(confidence + 0.05, 0.98)

        return best_field, round(confidence, 3)

    return None, 0.0


def classify_section(text: str) -> str:
    """
    Classify a block of text into a financial section.

    Used to improve label mapping confidence.
    """
    from src.config import SECTION_KEYWORDS

    lower = text.lower()
    for section_name, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lower:
                return section_name

    return "unknown"
