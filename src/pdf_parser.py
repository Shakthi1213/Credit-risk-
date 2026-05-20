"""
PDF financial data extraction (legacy wrapper).

Delegates to the Financial Data Extraction Engine in src.extraction
for production-grade annual report parsing.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from src.ratings import extract_rating_from_text, normalize_credit_rating
from src.utils import (
    ALL_EXTRACTABLE_FIELDS,
    COL_BORROWER_NAME,
    COL_CAR,
    COL_COLLECTION_EFFICIENCY,
    COL_CREDIT_RATING,
    COL_EBIT,
    COL_GNPA,
    COL_INTEREST_EXPENSE,
    COL_NET_INCOME,
    COL_NET_NPA,
    COL_NPA,
    COL_REVENUE,
    COL_TOTAL_ASSETS,
    COL_TOTAL_DEBT,
    COL_TOTAL_EQUITY,
    clean_financial_value,
    normalize_column_name,
)

# Minimum characters to consider text extraction successful
MIN_TEXT_LENGTH_FOR_OCR_SKIP = 80

# Regex patterns: label keywords -> standard field name
# Each pattern captures the value group after the label.
_FIELD_REGEX: list[tuple[str, str]] = [
    (COL_REVENUE, r"(?:total\s+)?revenue\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore|%)?)"),
    (COL_NET_INCOME, r"(?:pat|profit\s+after\s+tax|net\s+profit)\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_TOTAL_EQUITY, r"(?:net\s+worth|shareholders?\s+equity|total\s+equity)\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_TOTAL_ASSETS, r"total\s+assets?\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_TOTAL_DEBT, r"(?:total\s+debt|borrowings?|total\s+borrowings?)\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_EBIT, r"\bebit\b\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_INTEREST_EXPENSE, r"(?:interest\s+expense|finance\s+cost)\s*[:=\-]?\s*([₹Rs\.\(\)\d,\s]+(?:cr|crore)?)"),
    (COL_CAR, r"(?:car|crar|capital\s+adequacy\s+ratio)\s*[:=\-]?\s*([\d\.]+%?)"),
    (COL_GNPA, r"\bgnpa\b\s*[:=\-]?\s*([\d\.]+%?)"),
    (COL_NPA, r"(?:net\s+npa|npa)\s*[:=\-]?\s*([\d\.]+%?)"),
    (COL_NET_NPA, r"net\s+npa\s*[:=\-]?\s*([\d\.]+%?)"),
    (COL_COLLECTION_EFFICIENCY, r"collection\s+efficien(?:cy|t)\s*[:=\-]?\s*([\d\.]+%?)"),
]

# Table row label aliases -> standard field (normalized label lookup)
_TABLE_LABEL_MAP: dict[str, str] = {
    "revenue": COL_REVENUE,
    "totalrevenue": COL_REVENUE,
    "pat": COL_NET_INCOME,
    "profitaftertax": COL_NET_INCOME,
    "netprofit": COL_NET_INCOME,
    "netincome": COL_NET_INCOME,
    "networth": COL_TOTAL_EQUITY,
    "shareholdersequity": COL_TOTAL_EQUITY,
    "totalequity": COL_TOTAL_EQUITY,
    "totalassets": COL_TOTAL_ASSETS,
    "assets": COL_TOTAL_ASSETS,
    "totaldebt": COL_TOTAL_DEBT,
    "borrowings": COL_TOTAL_DEBT,
    "totalborrowings": COL_TOTAL_DEBT,
    "ebit": COL_EBIT,
    "interestexpense": COL_INTEREST_EXPENSE,
    "financecost": COL_INTEREST_EXPENSE,
    "car": COL_CAR,
    "crar": COL_CAR,
    "capitaladequacyratio": COL_CAR,
    "gnpa": COL_GNPA,
    "grossnpa": COL_GNPA,
    "npa": COL_NPA,
    "netnpa": COL_NET_NPA,
    "collectionefficiency": COL_COLLECTION_EFFICIENCY,
}


def _extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    """Extract text from all pages using pdfplumber."""
    import pdfplumber

    text_parts: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)

    return "\n".join(text_parts)


def _extract_tables_pdfplumber(pdf_bytes: bytes) -> list[list[list[str | None]]]:
    """Extract tables from all pages using pdfplumber."""
    import pdfplumber

    all_tables: list[list[list[str | None]]] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if table:
                    all_tables.append(table)

    return all_tables


def _extract_text_ocr(pdf_bytes: bytes) -> str:
    """
    OCR fallback for scanned PDFs using pdf2image + pytesseract.

    Raises ImportError with a helpful message if OCR libraries are missing.
  """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as error:
        raise ImportError(
            "OCR requires pdf2image and pytesseract. "
            "Install them with: pip install pdf2image pytesseract. "
            "You also need Tesseract OCR installed on your system."
        ) from error

    text_parts: list[str] = []
    images = convert_from_bytes(pdf_bytes, dpi=200)

    for image in images:
        page_text = pytesseract.image_to_string(image)
        if page_text.strip():
            text_parts.append(page_text)

    return "\n".join(text_parts)


def _parse_fields_from_text(text: str) -> dict[str, Any]:
    """Extract financial fields from free text using regex patterns."""
    extracted: dict[str, Any] = {}
    text_lower = text.lower()

    for field_name, pattern in _FIELD_REGEX:
        if field_name in extracted:
            continue

        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            raw_value = match.group(1).strip()
            if field_name == COL_CREDIT_RATING:
                extracted[field_name] = raw_value
            else:
                extracted[field_name] = clean_financial_value(raw_value)

    # Net NPA pattern may conflict with NPA - prefer net_npa when label says net
    if COL_NET_NPA not in extracted:
        net_npa_match = re.search(
            r"net\s+npa\s*[:=\-]?\s*([\d\.]+%?)", text_lower, re.IGNORECASE
        )
        if net_npa_match:
            extracted[COL_NET_NPA] = clean_financial_value(net_npa_match.group(1))

    rating = extract_rating_from_text(text)
    if rating:
        extracted[COL_CREDIT_RATING] = rating

    return extracted


def _parse_fields_from_tables(tables: list[list[list[str | None]]]) -> dict[str, Any]:
    """Parse label-value pairs from extracted PDF tables."""
    extracted: dict[str, Any] = {}

    for table in tables:
        for row in table:
            if not row or len(row) < 2:
                continue

            label_cell = row[0]
            value_cell = row[1] if len(row) > 1 else None

            if label_cell is None or value_cell is None:
                continue

            label_key = normalize_column_name(str(label_cell))
            field_name = _TABLE_LABEL_MAP.get(label_key)

            if not field_name or field_name in extracted:
                continue

            if field_name == COL_CREDIT_RATING:
                extracted[field_name] = str(value_cell).strip()
            else:
                extracted[field_name] = clean_financial_value(value_cell)

    return extracted


def extract_raw_text_from_pdf(
    pdf_bytes: bytes,
    *,
    use_ocr: bool = True,
) -> tuple[str, dict]:
    """
    Extract raw text from a PDF (pdfplumber first, OCR fallback if needed).

    Always returns whatever text could be read, even when OCR fails.

    Returns:
        (final_text, text_metadata)
    """
    from src.extraction import extract_text_from_pdf

    final_text, metadata = extract_text_from_pdf(pdf_bytes)
    print(f"[PDF] Extracted {len(final_text)} characters via {metadata.get('extraction_method', 'text')}")
    return final_text, metadata


def extract_financial_data_from_pdf(
    pdf_bytes: bytes,
    *,
    use_ocr: bool = True,
    pre_extracted_text: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Extract financial data from a PDF (delegates to extraction engine).

    Returns:
        (single_row_dataframe, extraction_metadata)
    """
    from src.extraction import extract_from_pdf

    result = extract_from_pdf(pdf_bytes)
    metadata = dict(result.metadata)
    metadata["source"] = "pdf"
    if result.warnings:
        metadata["warning"] = result.warnings[0]
    return result.dataframe, metadata
