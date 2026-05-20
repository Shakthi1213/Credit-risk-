"""
Table detection and parsing for annual report financial statements.

Handles horizontal/vertical tables, year columns, multi-page tables,
and label-value extraction from messy report layouts.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.cleaning import clean_value_for_field
from src.config import YEAR_COLUMN_PATTERNS
from src.mapping import map_label_to_field, normalize_label
from src.schemas import ExtractedField

# Regex to score year columns (higher = more recent)
_YEAR_SCORE_PATTERNS = [
    (re.compile(r"fy\s*'?(\d{2,4})", re.I), 1),
    (re.compile(r"31\s*mar(?:ch)?\s*(\d{4})", re.I), 2),
    (re.compile(r"(\d{4})\s*[-–]\s*(\d{2,4})", re.I), 2),
    (re.compile(r"\b(20\d{2})\b"), 1),
    (re.compile(r"current\s+year", re.I), 3),
]


def table_to_dataframe(table: list[list[Any]]) -> pd.DataFrame | None:
    """Convert a raw pdfplumber table (list of rows) to a DataFrame."""
    if not table or len(table) < 2:
        return None

    # Use first row as header if it looks like headers
    rows = [[str(cell).strip() if cell is not None else "" for cell in row] for row in table]
    max_cols = max(len(row) for row in rows)

    normalized_rows = []
    for row in rows:
        padded = row + [""] * (max_cols - len(row))
        normalized_rows.append(padded)

    df = pd.DataFrame(normalized_rows)
    return df


def detect_year_columns(df: pd.DataFrame) -> list[tuple[int, str, int]]:
    """
    Detect year/period columns in a financial table.

    Returns list of (column_index, label, year_score) sorted by recency.
    """
    if df.empty:
        return []

    header_rows = df.head(3)
    candidates: list[tuple[int, str, int]] = []

    for col_idx in range(df.shape[1]):
        col_text = " ".join(
            str(header_rows.iloc[row_idx, col_idx])
            for row_idx in range(len(header_rows))
        ).strip()

        if not col_text:
            continue

        score = _score_year_label(col_text)
        if score > 0:
            candidates.append((col_idx, col_text, score))

    # If no year headers found, treat rightmost numeric column as latest
    if not candidates and df.shape[1] >= 2:
        candidates.append((df.shape[1] - 1, "latest_column", 1))

    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates


def _score_year_label(label: str) -> int:
    """Score how likely a column header represents a recent year (higher = newer)."""
    score = 0
    for pattern, weight in _YEAR_SCORE_PATTERNS:
        match = pattern.search(label)
        if match:
            groups = match.groups()
            if groups:
                year_str = groups[-1]
                if len(year_str) == 2:
                    year_num = 2000 + int(year_str) if int(year_str) < 50 else 1900 + int(year_str)
                else:
                    year_num = int(year_str)
                score = max(score, year_num * weight)
            else:
                score = max(score, 2025 * weight)
    return int(score)


def detect_table_unit(table_text: str) -> str:
    """Detect reporting unit from table header/footer text."""
    lower = table_text.lower()
    if "in crore" in lower or "₹ crore" in lower or "rs. crore" in lower:
        return "crore"
    if "in lakh" in lower or "₹ lakh" in lower:
        return "lakh"
    if "in million" in lower or "in mn" in lower:
        return "million"
    return ""


def extract_fields_from_table(
    table: list[list[Any]],
    *,
    page_number: int | None = None,
    section: str = "unknown",
    table_index: int = 0,
) -> list[ExtractedField]:
    """
    Extract standardized financial fields from a single table.

  Supports:
        - Label in column 0, values in year columns
        - Multi-row headers
        - Latest year column auto-selected
    """
    df = table_to_dataframe(table)
    if df is None or df.empty:
        return []

    table_text = " ".join(df.astype(str).values.flatten())
    context_unit = detect_table_unit(table_text)
    year_columns = detect_year_columns(df)

    if not year_columns:
        return []

    latest_col_idx, year_label, _ = year_columns[0]
    extracted: list[ExtractedField] = []

    for row_idx in range(len(df)):
        row = df.iloc[row_idx]
        raw_label = str(row.iloc[0]).strip() if len(row) > 0 else ""

        if not raw_label or len(normalize_label(raw_label)) < 2:
            continue

        # Skip header-like rows
        if _score_year_label(raw_label) > 0 and row_idx < 3:
            continue

        raw_value = str(row.iloc[latest_col_idx]).strip() if latest_col_idx < len(row) else ""
        if not raw_value:
            continue

        standard_field, confidence = map_label_to_field(raw_label, section=section)
        if not standard_field:
            continue

        cleaned = clean_value_for_field(raw_value, standard_field, context_unit=context_unit)

        # Table + exact/fuzzy label = higher confidence
        source = "table"
        if confidence < 0.85:
            confidence = min(confidence + 0.1, 0.95)

        extracted.append(
            ExtractedField(
                standard_field=standard_field,
                raw_label=raw_label,
                raw_value=cleaned.raw_value,
                cleaned_value=cleaned.cleaned_value,
                unit=cleaned.unit or context_unit,
                year=year_label,
                page_number=page_number,
                section=section,
                confidence=confidence,
                source=source,
                status="found" if cleaned.cleaned_value is not None else "inferred",
            )
        )

    return extracted


def merge_extracted_fields(
    field_lists: list[list[ExtractedField]],
) -> list[ExtractedField]:
    """
    Merge multiple extraction lists, keeping highest-confidence value per field.
    """
    best: dict[str, ExtractedField] = {}

    for fields in field_lists:
        for item in fields:
            existing = best.get(item.standard_field)
            if existing is None or item.confidence > existing.confidence:
                best[item.standard_field] = item

    return list(best.values())
