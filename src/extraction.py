"""
Financial Data Extraction Engine for NBFC annual reports.

Pipeline stages:
    A. Document detection
    B. Text extraction (PDF / OCR)
    C. Table detection
    D. Section identification
    E. Financial label mapping
    F. Value cleaning
    G. Confidence scoring
    H. Standardization

Output: ExtractionResult ready for ratios, scoring, and flags.
"""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from src.cleaning import clean_value_for_field
from src.config import (
    ALL_STANDARD_FIELDS,
    CORE_FIELDS,
    FIELD_BORROWER_NAME,
    FIELD_CREDIT_RATING,
    FIELD_DISPLAY_NAMES,
    MIN_PDF_TEXT_LENGTH,
)
from src.mapping import classify_section, map_label_to_field, normalize_label
from src.ratings import extract_rating_from_text, normalize_credit_rating
from src.schemas import ExtractedField, ExtractionResult
from src.table_parser import extract_fields_from_table, merge_extracted_fields

EXCEL_EXTENSIONS = {".xlsx", ".xls"}
PDF_EXTENSIONS = {".pdf"}


# ---------------------------------------------------------------------------
# Stage A: Document detection
# ---------------------------------------------------------------------------


def detect_document_type(filename: str, file_bytes: bytes | None = None) -> dict[str, Any]:
    """
    Detect file type and recommended extraction route.

    Returns metadata dict with: file_type, route, is_pdf, is_excel
    """
    extension = ""
    if filename and "." in filename:
        extension = "." + filename.rsplit(".", 1)[-1].lower()

    info: dict[str, Any] = {
        "filename": filename,
        "extension": extension,
        "file_type": "unknown",
        "route": "unknown",
    }

    if extension in PDF_EXTENSIONS:
        info["file_type"] = "pdf"
        info["route"] = "pdf_text_then_ocr"
        info["is_pdf"] = True
    elif extension in EXCEL_EXTENSIONS:
        info["file_type"] = "excel"
        info["route"] = "excel_workbook"
        info["is_excel"] = True
    else:
        info["is_pdf"] = False
        info["is_excel"] = False

    return info


# ---------------------------------------------------------------------------
# Stage B: Text extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, dict[str, Any]]:
    """
    Extract text from PDF using pdfplumber, with OCR fallback.

    Returns (final_text, metadata).
    """
    import pdfplumber

    metadata: dict[str, Any] = {
        "extraction_method": "text",
        "raw_text": "",
        "ocr_text": "",
        "pages_processed": 0,
    }
    page_texts: list[tuple[int, str]] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        metadata["pages_processed"] = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append((page_num, text))

    raw_text = "\n\n".join(text for _, text in page_texts)
    metadata["raw_text"] = raw_text
    metadata["page_texts"] = page_texts
    final_text = raw_text

    if len(raw_text.strip()) < MIN_PDF_TEXT_LENGTH:
        ocr_text, ocr_meta = _ocr_fallback(pdf_bytes)
        metadata.update(ocr_meta)
        if len(ocr_text.strip()) > len(raw_text.strip()):
            final_text = ocr_text
            metadata["extraction_method"] = "ocr"

    metadata["final_text"] = final_text
    return final_text, metadata


def _ocr_fallback(pdf_bytes: bytes) -> tuple[str, dict[str, Any]]:
    """OCR fallback for scanned PDFs. Never raises — returns empty string on failure."""
    meta: dict[str, Any] = {"ocr_attempted": True, "ocr_text": ""}
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        parts: list[str] = []
        for image in convert_from_bytes(pdf_bytes, dpi=200):
            text = pytesseract.image_to_string(image)
            if text.strip():
                parts.append(text)
        meta["ocr_text"] = "\n\n".join(parts)
    except ImportError:
        meta["ocr_note"] = "OCR libraries not installed (pdf2image, pytesseract)."
    except Exception as error:
        meta["ocr_note"] = f"OCR failed: {error}"

    return meta.get("ocr_text", ""), meta


# ---------------------------------------------------------------------------
# Stage C: Table detection
# ---------------------------------------------------------------------------


def extract_tables_from_pdf(pdf_bytes: bytes) -> list[dict[str, Any]]:
    """
    Extract all tables from PDF with page numbers and section hints.

    Returns list of {page, table_index, table, section, table_text}.
    """
    import pdfplumber

    results: list[dict[str, Any]] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            section = classify_section(page_text)

            for table_idx, table in enumerate(page.extract_tables() or []):
                if not table:
                    continue
                results.append(
                    {
                        "page": page_num,
                        "table_index": table_idx,
                        "table": table,
                        "section": section,
                        "table_text": page_text[:500],
                    }
                )

    return results


# ---------------------------------------------------------------------------
# Stage E-G: Text-based field extraction
# ---------------------------------------------------------------------------

_TEXT_PATTERNS: list[tuple[str, str]] = [
    ("revenue", r"(?:total\s+)?revenue\s+from\s+operations\s*[:=\-]?\s*([^\n]+)"),
    ("net_income", r"(?:profit\s+after\s+tax|pat)\s*[:=\-]?\s*([^\n]+)"),
    ("pbt", r"profit\s+before\s+tax\s*[:=\-]?\s*([^\n]+)"),
    ("ebitda", r"\bebitda\b\s*[:=\-]?\s*([^\n]+)"),
    ("ebit", r"\bebit\b\s*[:=\-]?\s*([^\n]+)"),
    ("total_assets", r"total\s+assets?\s*[:=\-]?\s*([^\n]+)"),
    ("total_equity", r"(?:net\s+worth|total\s+equity|shareholders?\s+funds)\s*[:=\-]?\s*([^\n]+)"),
    ("total_debt", r"(?:total\s+debt|total\s+borrowings)\s*[:=\-]?\s*([^\n]+)"),
    ("interest_expense", r"(?:finance\s+cost|interest\s+expense)\s*[:=\-]?\s*([^\n]+)"),
    ("gnpa", r"\bgnpa\b\s*[:=\-]?\s*([\d\.]+%?)"),
    ("net_npa", r"net\s+npa\s*[:=\-]?\s*([\d\.]+%?)"),
    ("npa", r"(?<!\w)npa\s*[:=\-]?\s*([\d\.]+%?)"),
    ("car_crar", r"(?:car|crar|capital\s+adequacy)\s*[:=\-]?\s*([\d\.]+%?)"),
    ("collection_efficiency", r"collection\s+efficien\w*\s*[:=\-]?\s*([\d\.]+%?)"),
    ("aum", r"\baum\b\s*[:=\-]?\s*([^\n]+)"),
    ("loan_book", r"(?:loan\s+book|advances)\s*[:=\-]?\s*([^\n]+)"),
]


def extract_fields_from_text(
    text: str,
    *,
    source: str = "text",
    page_number: int | None = None,
) -> list[ExtractedField]:
    """Extract fields from free text using regex and line-by-line fuzzy matching."""
    extracted: list[ExtractedField] = []
    text_lower = text.lower()

    # Regex pass
    for field_name, pattern in _TEXT_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            raw_value = match.group(1).strip()
            cleaned = clean_value_for_field(raw_value, field_name)
            extracted.append(
                ExtractedField(
                    standard_field=field_name,
                    raw_label=field_name.replace("_", " "),
                    raw_value=cleaned.raw_value,
                    cleaned_value=cleaned.cleaned_value,
                    unit=cleaned.unit,
                    page_number=page_number,
                    section=classify_section(text[:2000]),
                    confidence=0.70,
                    source=source,
                    status="found",
                )
            )

    # Line-by-line fuzzy pass
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue

        # Split on multiple spaces or tabs (label .... value)
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) < 2:
            # Try last number in line
            label_part = re.sub(r"[\d,₹\.\(\)\-%]+$", "", line).strip()
            value_part = re.findall(r"[\d,\.\(\)₹%]+", line)
            if not label_part or not value_part:
                continue
            raw_label = label_part
            raw_value = value_part[-1]
        else:
            raw_label = parts[0].strip()
            raw_value = parts[-1].strip()

        section = classify_section(text[:2000])
        standard_field, confidence = map_label_to_field(raw_label, section=section)
        if not standard_field:
            continue

        if any(item.standard_field == standard_field for item in extracted):
            continue

        cleaned = clean_value_for_field(raw_value, standard_field)
        extracted.append(
            ExtractedField(
                standard_field=standard_field,
                raw_label=raw_label,
                raw_value=cleaned.raw_value,
                cleaned_value=cleaned.cleaned_value,
                unit=cleaned.unit,
                page_number=page_number,
                section=section,
                confidence=confidence,
                source=source,
                status="found",
            )
        )

    rating = extract_rating_from_text(text)
    if rating:
        extracted.append(
            ExtractedField(
                standard_field=FIELD_CREDIT_RATING,
                raw_label="Credit Rating",
                raw_value=rating,
                cleaned_value=None,
                unit="",
                page_number=page_number,
                section=classify_section(text[:2000]),
                confidence=0.85,
                source=source,
                status="found",
            )
        )

    return extracted


# ---------------------------------------------------------------------------
# Stage H: Standardization
# ---------------------------------------------------------------------------


def fields_to_dataframe(fields: list[ExtractedField]) -> pd.DataFrame:
    """Convert extracted fields to a single-row DataFrame for the scorecard."""
    row: dict[str, Any] = {}

    for item in fields:
        if item.standard_field == FIELD_CREDIT_RATING:
            normalized = normalize_credit_rating(item.raw_value)
            row[item.standard_field] = normalized or item.raw_value
        elif item.cleaned_value is not None:
            row[item.standard_field] = item.cleaned_value

    if FIELD_BORROWER_NAME not in row:
        row[FIELD_BORROWER_NAME] = "Borrower (Extracted)"

    return pd.DataFrame([row])


def build_extraction_result(
    fields: list[ExtractedField],
    *,
    metadata: dict[str, Any] | None = None,
    unmatched_labels: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ExtractionResult:
    """Build final ExtractionResult with summary and debug records."""
    metadata = metadata or {}
    warnings = warnings or []
    unmatched_labels = unmatched_labels or []

    found_fields = {item.standard_field for item in fields if item.cleaned_value is not None or item.standard_field == FIELD_CREDIT_RATING}
    missing = [field for field in ALL_STANDARD_FIELDS if field not in found_fields and field != FIELD_BORROWER_NAME]

    debug_records = [item.to_dict() for item in fields]

    summary = {
        "total_fields_attempted": len(ALL_STANDARD_FIELDS),
        "fields_extracted": len(found_fields),
        "fields_missing": len(missing),
        "core_fields_found": sum(1 for field in CORE_FIELDS if field in found_fields),
        "core_fields_required": len(CORE_FIELDS),
        "extraction_method": metadata.get("extraction_method", "unknown"),
        "pages_processed": metadata.get("pages_processed", 0),
        "tables_found": metadata.get("tables_found", 0),
        "can_run_scorecard": all(field in found_fields for field in CORE_FIELDS),
    }

    dataframe = fields_to_dataframe(fields)

    return ExtractionResult(
        dataframe=dataframe,
        fields=fields,
        unmatched_labels=unmatched_labels,
        missing_fields=missing,
        warnings=warnings,
        summary=summary,
        metadata=metadata,
        debug_records=debug_records,
    )


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def extract_from_pdf(pdf_bytes: bytes, filename: str = "") -> ExtractionResult:
    """
    Full extraction pipeline for PDF annual reports.
    """
    warnings: list[str] = []
    doc_info = detect_document_type(filename, pdf_bytes)
    metadata: dict[str, Any] = {"source": "pdf", **doc_info}

    print("[EXTRACTION] Stage A: Document detected as PDF")

    # Stage B: Text
    print("[EXTRACTION] Stage B: Extracting text...")
    try:
        final_text, text_meta = extract_text_from_pdf(pdf_bytes)
        metadata.update(text_meta)
    except ImportError as error:
        warnings.append(f"pdfplumber not available: {error}")
        final_text = ""
        metadata["text_error"] = str(error)

    if not final_text.strip():
        warnings.append("No text extracted from PDF. Try OCR-enabled upload or a text-based PDF.")

    # Stage C: Tables
    print("[EXTRACTION] Stage C: Detecting tables...")
    all_field_lists: list[list[ExtractedField]] = []
    try:
        table_records = extract_tables_from_pdf(pdf_bytes)
        metadata["tables_found"] = len(table_records)

        for record in table_records:
            table_fields = extract_fields_from_table(
                record["table"],
                page_number=record["page"],
                section=record["section"],
                table_index=record["table_index"],
            )
            all_field_lists.append(table_fields)
    except Exception as error:
        warnings.append(f"Table extraction partial failure: {error}")
        metadata["table_error"] = str(error)

    # Stage E-G: Text extraction
    print("[EXTRACTION] Stage E-G: Mapping labels from text...")
    if final_text.strip():
        text_fields = extract_fields_from_text(
            final_text,
            source=metadata.get("extraction_method", "text"),
        )
        all_field_lists.append(text_fields)

    merged = merge_extracted_fields(all_field_lists)

    if not merged:
        warnings.append(
            "No financial fields mapped. Review document format or add clearer labels."
        )

    print(f"[EXTRACTION] Stage H: Standardizing {len(merged)} fields")
    return build_extraction_result(merged, metadata=metadata, warnings=warnings)


def extract_from_excel(file_obj) -> ExtractionResult:
    """
    Full extraction pipeline for Excel financial statements.
    """
    warnings: list[str] = []
    metadata: dict[str, Any] = {"source": "excel", "extraction_method": "excel"}

    print("[EXTRACTION] Stage A: Document detected as Excel")

    try:
        sheets = pd.read_excel(file_obj, sheet_name=None)
    except Exception as error:
        warnings.append(f"Excel read failed: {error}")
        return build_extraction_result([], metadata=metadata, warnings=warnings)

    all_field_lists: list[list[ExtractedField]] = []
    metadata["sheets"] = list(sheets.keys())

    for sheet_name, sheet_df in sheets.items():
        if sheet_df.empty:
            continue

        section = classify_section(sheet_name + " " + " ".join(sheet_df.columns.astype(str)))

        # Column-based extraction (standard financial model format)
        for column in sheet_df.columns:
            standard_field, confidence = map_label_to_field(str(column), section=section)
            if not standard_field:
                continue

            for _, row in sheet_df.iterrows():
                raw_value = row[column]
                cleaned = clean_value_for_field(raw_value, standard_field)
                if cleaned.cleaned_value is None:
                    continue

                all_field_lists.append([
                    ExtractedField(
                        standard_field=standard_field,
                        raw_label=str(column),
                        raw_value=cleaned.raw_value,
                        cleaned_value=cleaned.cleaned_value,
                        unit=cleaned.unit,
                        year=str(sheet_name),
                        section=section,
                        confidence=confidence,
                        source="excel",
                        status="found",
                    )
                ])
                break

        # Row-based extraction (label in first column)
        if sheet_df.shape[1] >= 2:
            table_data = [sheet_df.columns.tolist()] + sheet_df.values.tolist()
            row_fields = extract_fields_from_table(
                table_data,
                section=section,
            )
            all_field_lists.append(row_fields)

    merged = merge_extracted_fields(all_field_lists)
    print(f"[EXTRACTION] Excel: extracted {len(merged)} fields")

    return build_extraction_result(merged, metadata=metadata, warnings=warnings)


def extract_from_upload(uploaded_file) -> ExtractionResult:
    """
    Auto-detect file type and run the full extraction pipeline.

    Args:
        uploaded_file: Streamlit UploadedFile or file-like object.

    Returns:
        ExtractionResult
    """
    filename = getattr(uploaded_file, "name", "") or ""
    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    doc_info = detect_document_type(filename, file_bytes)

    if doc_info.get("is_pdf"):
        return extract_from_pdf(file_bytes, filename)

    if doc_info.get("is_excel"):
        return extract_from_excel(uploaded_file)

    raise ValueError(
        f"Unsupported file type '{doc_info.get('extension')}'. "
        "Upload PDF (.pdf) or Excel (.xlsx, .xls)."
    )
