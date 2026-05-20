"""
Debug and audit display helpers for the extraction engine.

Shows transparent extraction details in Streamlit so users can
understand what was found, how it was mapped, and why fields are missing.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import CORE_FIELDS, FIELD_DISPLAY_NAMES
from src.schemas import ExtractionResult


def display_extraction_summary(result: ExtractionResult) -> None:
    """Show high-level extraction summary metrics."""
    summary = result.summary

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Fields Extracted", summary.get("fields_extracted", 0))
    with col2:
        st.metric("Fields Missing", summary.get("fields_missing", 0))
    with col3:
        st.metric(
            "Core Fields",
            f"{summary.get('core_fields_found', 0)} / {summary.get('core_fields_required', 0)}",
        )
    with col4:
        method = result.metadata.get("extraction_method", "unknown")
        st.metric("Method", method.upper())


def display_extraction_debug_table(result: ExtractionResult) -> None:
    """
    Show detailed debug table:
    page | original label | mapped field | raw value | cleaned | confidence | status
    """
    st.subheader("Extraction Audit Trail")

    if not result.debug_records:
        st.info("No fields were extracted. Check the document format or OCR quality.")
        return

    debug_df = pd.DataFrame(result.debug_records)

    display_columns = [
        "page_number",
        "raw_label",
        "standard_field",
        "raw_value",
        "cleaned_value",
        "unit",
        "year",
        "confidence",
        "source",
        "section",
        "status",
    ]
    available = [col for col in display_columns if col in debug_df.columns]

    st.dataframe(
        debug_df[available],
        use_container_width=True,
        hide_index=True,
    )


def display_missing_fields_report(result: ExtractionResult) -> None:
    """Explain which fields are missing and why analysis may be limited."""
    if not result.missing_fields:
        st.success("All target fields were checked. Core fields needed for scoring are present or optional fields were not in the document.")
        return

    rows = []
    for field in result.missing_fields:
        is_core = field in CORE_FIELDS
        rows.append({
            "Field": FIELD_DISPLAY_NAMES.get(field, field),
            "Standard Name": field,
            "Required for Scorecard": "Yes" if is_core else "No",
            "Status": "Missing",
        })

    st.warning(f"**{len(result.missing_fields)}** field(s) could not be extracted from the document.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def display_extraction_warnings(result: ExtractionResult) -> None:
    """Show extraction warnings and OCR/table notes."""
    for warning in result.warnings:
        st.warning(warning)

    if result.metadata.get("ocr_note"):
        st.warning(result.metadata["ocr_note"])

    if result.metadata.get("text_error"):
        st.error(f"Text extraction error: {result.metadata['text_error']}")

    if result.metadata.get("table_error"):
        st.warning(f"Table extraction note: {result.metadata['table_error']}")


def display_full_extraction_debug(result: ExtractionResult) -> None:
    """Display all debug sections for the extraction engine."""
    display_extraction_summary(result)
    display_extraction_warnings(result)

    with st.expander("Extraction audit trail (all mapped fields)", expanded=True):
        display_extraction_debug_table(result)

    with st.expander("Missing fields report"):
        display_missing_fields_report(result)

    if result.unmatched_labels:
        with st.expander("Unmatched labels"):
            st.write(result.unmatched_labels)
