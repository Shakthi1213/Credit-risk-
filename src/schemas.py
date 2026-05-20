"""
Data structures for the Financial Data Extraction Engine.

Defines standardized containers for extracted fields, debug records,
and the final extraction result passed to the credit scorecard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ExtractedField:
    """A single extracted and standardized financial data point."""

    standard_field: str
    raw_label: str
    raw_value: str
    cleaned_value: float | None
    unit: str = ""
    year: str | None = None
    page_number: int | None = None
    section: str = "unknown"
    confidence: float = 0.0
    source: str = "unknown"  # table | text | excel | ocr
    status: str = "found"  # found | inferred | missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard_field": self.standard_field,
            "raw_label": self.raw_label,
            "raw_value": self.raw_value,
            "cleaned_value": self.cleaned_value,
            "unit": self.unit,
            "year": self.year,
            "page_number": self.page_number,
            "section": self.section,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "status": self.status,
        }


@dataclass
class ExtractionResult:
    """
    Complete output of the extraction pipeline.

    Ready for ratio calculation, scoring, and red-flag detection.
    """

    dataframe: pd.DataFrame
    fields: list[ExtractedField] = field(default_factory=list)
    unmatched_labels: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    debug_records: list[dict[str, Any]] = field(default_factory=list)

    def to_json_records(self) -> list[dict[str, Any]]:
        """Return all extracted fields as JSON-serializable records."""
        return [field_record.to_dict() for field_record in self.fields]

    def get_best_value(self, standard_field: str) -> float | None:
        """Return the highest-confidence cleaned value for a field."""
        matches = [
            item for item in self.fields
            if item.standard_field == standard_field and item.cleaned_value is not None
        ]
        if not matches:
            return None
        best = max(matches, key=lambda item: item.confidence)
        return best.cleaned_value
