"""
Financial value cleaning for the extraction engine.

Converts messy strings from annual reports into usable numeric values.
Preserves raw values and detects units (crore, lakh, percent, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from src.config import PERCENT_FIELDS


@dataclass
class CleanedValue:
    """Result of cleaning a single financial value."""

    raw_value: str
    cleaned_value: float | None
    unit: str
    is_negative: bool


def _detect_unit(text: str) -> str:
    """Detect unit from a raw value string."""
    lower = text.lower()
    if "%" in text:
        return "percent"
    if re.search(r"\bcrore\b|\bcr\b", lower):
        return "crore"
    if re.search(r"\blakh\b|\blac\b", lower):
        return "lakh"
    if re.search(r"\bmn\b|\bmillion\b", lower):
        return "million"
    if "₹" in text or re.search(r"\brs\.?\b", lower):
        return "inr"
    return "absolute"


def clean_financial_value(value, *, context_unit: str = "") -> CleanedValue:
    """
    Convert a messy financial cell value into a CleanedValue.

    Handles:
        - ₹, commas, spaces
        - Cr / crore / lakh / mn
        - % suffix
        - Brackets for negatives: (500) -> -500
        - Indian numbering: 1,25,000

    Examples:
        "₹10,004 Cr"  -> 10004.0 (unit: crore)
        "5.2%"        -> 5.2 (unit: percent)
        "(₹500 Cr)"   -> -500.0
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return CleanedValue(raw_value="", cleaned_value=None, unit="", is_negative=False)

    if isinstance(value, (int, float)):
        return CleanedValue(
            raw_value=str(value),
            cleaned_value=float(value),
            unit=context_unit or "absolute",
            is_negative=value < 0,
        )

    raw_text = str(value).strip()
    if not raw_text or raw_text.lower() in {"na", "n/a", "-", "none", "null", ""}:
        return CleanedValue(raw_value=raw_text, cleaned_value=None, unit="", is_negative=False)

    unit = context_unit or _detect_unit(raw_text)
    text = raw_text

    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()
    elif text.startswith("-"):
        is_negative = True

    text = text.replace("₹", "").replace("rs.", "").replace("rs", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", "")
    text = re.sub(r"crore|cr", "", text, flags=re.IGNORECASE)
    text = re.sub(r"lakh|lac", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmn\b|\bmillion\b", "", text, flags=re.IGNORECASE)
    text = text.replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)

    if not text or text in {".", "-", "-."}:
        return CleanedValue(raw_value=raw_text, cleaned_value=None, unit=unit, is_negative=is_negative)

    try:
        number = float(text)
        if is_negative and number > 0:
            number = -number
        return CleanedValue(
            raw_value=raw_text,
            cleaned_value=number,
            unit=unit,
            is_negative=is_negative,
        )
    except ValueError:
        return CleanedValue(raw_value=raw_text, cleaned_value=None, unit=unit, is_negative=is_negative)


def normalize_percent_storage(value: float | None, standard_field: str) -> float | None:
    """
    Store percentage fields as decimals for ratio engine (5.2% -> 0.052).
    """
    if value is None:
        return None
    if standard_field not in PERCENT_FIELDS:
        return value
    if abs(value) > 1:
        return value / 100.0
    return value


def clean_value_for_field(value, standard_field: str, *, context_unit: str = "") -> CleanedValue:
    """Clean a value and apply field-specific normalization."""
    result = clean_financial_value(value, context_unit=context_unit)
    if result.cleaned_value is not None:
        result.cleaned_value = normalize_percent_storage(result.cleaned_value, standard_field)
    return result
