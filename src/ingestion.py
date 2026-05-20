"""
Unified file ingestion for Excel and PDF uploads.

Routes files to the Financial Data Extraction Engine and returns
a standardized DataFrame for the credit scorecard.
"""

from __future__ import annotations

import pandas as pd

from src.extraction import (
    extract_from_excel,
    extract_from_pdf,
    extract_from_upload,
)
from src.schemas import ExtractionResult
from src.utils import prepare_financial_data

EXCEL_EXTENSIONS = {".xlsx", ".xls"}
PDF_EXTENSIONS = {".pdf"}


def _get_file_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def read_pdf_bytes(uploaded_file) -> bytes:
    uploaded_file.seek(0)
    return uploaded_file.read()


def extract_document(uploaded_file) -> ExtractionResult:
    """
    Run the full Financial Data Extraction Engine on an uploaded file.

    This is the primary entry point for PDF and Excel annual reports.
    """
    return extract_from_upload(uploaded_file)


def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame, dict]:
    """
    Load and prepare financial data from an uploaded Excel or PDF file.

    Returns:
        (prepared_dataframe, metadata)
    """
    result = extract_document(uploaded_file)

    # Additional cleaning pass for backward compatibility with utils
    prepared, column_mapping = prepare_financial_data(result.dataframe)

    metadata = dict(result.metadata)
    metadata["source"] = metadata.get("source", "unknown")
    metadata["column_mapping"] = str(column_mapping)
    metadata["extraction_summary"] = result.summary
    metadata["extraction_warnings"] = result.warnings
    metadata["missing_fields"] = result.missing_fields
    metadata["final_text"] = metadata.get("final_text", "")
    metadata["raw_text"] = metadata.get("raw_text", "")

    return prepared, metadata


def load_uploaded_file_with_details(uploaded_file) -> tuple[pd.DataFrame, dict, ExtractionResult]:
    """Load file and return full ExtractionResult for debug display."""
    result = extract_document(uploaded_file)
    prepared, column_mapping = prepare_financial_data(result.dataframe)

    metadata = dict(result.metadata)
    metadata["column_mapping"] = str(column_mapping)

    return prepared, metadata, result
