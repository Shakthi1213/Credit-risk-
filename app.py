"""
NBFC Credit Risk Scorecard — Streamlit Dashboard

Upload Excel or PDF files with borrower financial data to extract metrics,
calculate ratios, generate credit risk scores, and review red-flag alerts.
"""

import pandas as pd
import streamlit as st

from src.flags import RedFlag, detect_red_flags_from_financial_data
from src.debug import display_full_extraction_debug
from src.ingestion import _get_file_extension, load_uploaded_file_with_details
from src.schemas import ExtractionResult
from src.ratios import calculate_all_ratios
from src.scoring import (
    CRITICAL_RISK,
    HIGH_RISK,
    LOW_RISK,
    MODERATE_RISK,
    get_credit_rating_info,
    score_borrower,
)
from src.utils import (
    COL_BORROWER_NAME,
    COL_CREDIT_RATING,
    COL_CREDIT_RATING_SCORE,
    FIELD_LABELS,
    FINANCIAL_VALUE_COLUMNS,
    PERCENT_COLUMNS,
    build_extraction_preview,
    format_field_preview_value,
    prepare_financial_data,
    validate_financial_data,
)

# Friendly labels for ratio dashboard cards
RATIO_LABELS = {
    "roa": "Return on Assets (ROA)",
    "roe": "Return on Equity (ROE)",
    "debt_equity_ratio": "Debt-to-Equity Ratio",
    "interest_coverage_ratio": "Interest Coverage Ratio",
    "current_ratio": "Current Ratio",
    "debt_to_assets_ratio": "Debt-to-Assets Ratio",
    "revenue": "Revenue",
    "net_worth": "Net Worth",
    "car_crar": "CAR / CRAR",
    "gnpa": "GNPA",
    "npa": "NPA",
    "net_npa": "Net NPA",
    "collection_efficiency": "Collection Efficiency",
}

SUB_SCORE_LABELS = {
    "roa": "ROA Score",
    "roe": "ROE Score",
    "debt_equity_ratio": "Debt-Equity Score",
    "interest_coverage_ratio": "Interest Coverage Score",
}

# Preview columns for cleaned data table
PREVIEW_COLUMNS = [
    COL_BORROWER_NAME,
    "revenue",
    "net_income",
    "total_assets",
    "total_equity",
    "total_debt",
    "ebit",
    "interest_expense",
    "car_crar",
    "gnpa",
    "npa",
    "net_npa",
    "collection_efficiency",
    COL_CREDIT_RATING,
    COL_CREDIT_RATING_SCORE,
    "current_assets",
    "current_liabilities",
]


def configure_page() -> None:
    """Set up the Streamlit page title and layout."""
    st.set_page_config(
        page_title="NBFC Credit Risk Scorecard",
        page_icon="📊",
        layout="wide",
    )


def apply_custom_styles() -> None:
    """Add CSS for a clean, professional dashboard appearance."""
    st.markdown(
        """
        <style>
            .main-header {
                font-size: 2rem;
                font-weight: 700;
                color: #1f3a5f;
                margin-bottom: 0.25rem;
            }
            .sub-header {
                font-size: 1rem;
                color: #5a6778;
                margin-bottom: 1.5rem;
            }
            .risk-low { color: #15803d; font-weight: 700; font-size: 1.1rem; }
            .risk-moderate { color: #b45309; font-weight: 700; font-size: 1.1rem; }
            .risk-high { color: #c2410c; font-weight: 700; font-size: 1.1rem; }
            .risk-critical { color: #b91c1c; font-weight: 700; font-size: 1.1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_ratio_value(ratio_name: str, value: float | None) -> str:
    """Format a ratio or metric for human-readable display."""
    if value is None:
        return "N/A"

    if ratio_name in {"roa", "roe", "debt_to_assets_ratio", "car_crar", "gnpa", "npa", "net_npa", "collection_efficiency"}:
        return f"{value * 100:.2f}%"

    if ratio_name in {"debt_equity_ratio", "interest_coverage_ratio", "current_ratio"}:
        return f"{value:.2f}x"

    if ratio_name in {"revenue", "net_worth"}:
        if abs(value) >= 1_000_000:
            return f"₹{value:,.0f}"
        return f"₹{value:,.2f}"

    return f"{value:.2f}"


def get_risk_category_class(risk_category: str) -> str:
    """Return a CSS class for the risk category colour."""
    return {
        LOW_RISK: "risk-low",
        MODERATE_RISK: "risk-moderate",
        HIGH_RISK: "risk-high",
        CRITICAL_RISK: "risk-critical",
    }.get(risk_category, "risk-moderate")


def display_summary_cards(
    overall_score: float,
    risk_category: str,
    ratios: dict[str, float | None],
    rating_info: dict,
) -> None:
    """Top dashboard row: credit score, risk category, and key metrics."""
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(label="Overall Credit Score", value=f"{overall_score:.1f} / 100")

    with col2:
        css_class = get_risk_category_class(risk_category)
        st.markdown(
            f'<p class="{css_class}">Risk Category<br>{risk_category}</p>',
            unsafe_allow_html=True,
        )

    with col3:
        st.metric(label="ROA", value=format_ratio_value("roa", ratios.get("roa")))

    with col4:
        st.metric(label="ROE", value=format_ratio_value("roe", ratios.get("roe")))

    with col5:
        st.metric(
            label="Interest Coverage",
            value=format_ratio_value(
                "interest_coverage_ratio",
                ratios.get("interest_coverage_ratio"),
            ),
        )

    with col6:
        rating = rating_info.get("credit_rating") or "N/A"
        rating_score = rating_info.get("credit_rating_score")
        if rating_score is not None:
            st.metric(label="Credit Rating", value=f"{rating} ({rating_score}/100)")
        else:
            st.metric(label="Credit Rating", value=rating)


def display_ratio_cards(ratios: dict[str, float | None]) -> None:
    """Display financial ratios and NBFC metrics as dashboard cards."""
    st.subheader("Financial Ratios & NBFC Metrics")

    core_ratios = [
        "roa",
        "roe",
        "debt_equity_ratio",
        "interest_coverage_ratio",
        "car_crar",
        "gnpa",
        "npa",
    ]
    core_present = [name for name in core_ratios if ratios.get(name) is not None]

    if core_present:
        cols = st.columns(min(len(core_present), 4))
        for col, name in zip(cols, core_present[:4]):
            with col:
                st.metric(
                    label=RATIO_LABELS.get(name, name),
                    value=format_ratio_value(name, ratios.get(name)),
                )

        if len(core_present) > 4:
            cols2 = st.columns(len(core_present) - 4)
            for col, name in zip(cols2, core_present[4:]):
                with col:
                    st.metric(
                        label=RATIO_LABELS.get(name, name),
                        value=format_ratio_value(name, ratios.get(name)),
                    )
    else:
        st.info("Core ratios could not be calculated from the available data.")

    optional = ["revenue", "net_worth", "net_npa", "collection_efficiency", "current_ratio", "debt_to_assets_ratio"]
    optional_present = [name for name in optional if ratios.get(name) is not None]

    if optional_present:
        opt_cols = st.columns(min(len(optional_present), 4))
        for col, name in zip(opt_cols, optional_present):
            with col:
                st.metric(
                    label=RATIO_LABELS.get(name, name),
                    value=format_ratio_value(name, ratios.get(name)),
                )


def display_sub_scores(sub_scores: dict[str, int]) -> None:
    """Display individual sub-scores as dashboard cards."""
    st.subheader("Sub-Scores")
    cols = st.columns(len(sub_scores))

    for col, (name, score) in zip(cols, sub_scores.items()):
        with col:
            st.metric(label=SUB_SCORE_LABELS[name], value=f"{score} / 100")


def display_red_flags(flags: list[RedFlag]) -> None:
    """Show red-flag alerts using st.warning() and st.error()."""
    st.subheader("Red Flag Alerts")

    if not flags:
        st.success(
            "No red flags detected. Financial indicators are within acceptable limits."
        )
        return

    for flag in flags:
        if flag["severity"] == "error":
            st.error(f"🚩 {flag['message']}")
        else:
            st.warning(f"⚠️ {flag['message']}")


def display_extraction_preview(financial_data: pd.DataFrame) -> None:
    """Show extracted fields with values and status before analysis."""
    st.subheader("Extracted Data Preview")
    preview_table = build_extraction_preview(financial_data)
    st.dataframe(preview_table, use_container_width=True, hide_index=True)


def display_cleaned_data_preview(df: pd.DataFrame) -> None:
    """Show cleaned financial values for the selected borrower."""
    preview_cols = [col for col in PREVIEW_COLUMNS if col in df.columns]
    display_cols = preview_cols if preview_cols else list(df.columns)

    preview_df = df[display_cols].copy()
    for column in preview_df.columns:
        if column in FINANCIAL_VALUE_COLUMNS or column in PERCENT_COLUMNS or column == COL_CREDIT_RATING_SCORE:
            preview_df[column] = preview_df[column].apply(
                lambda value, col=column: format_field_preview_value(col, value)
            )
        elif column == COL_CREDIT_RATING:
            preview_df[column] = preview_df[column].astype(str)

    st.dataframe(preview_df, use_container_width=True, hide_index=True)


def is_pdf_file(uploaded_file) -> bool:
    """Return True when the uploaded file is a PDF."""
    filename = uploaded_file.name or ""
    return _get_file_extension(filename) == ".pdf"


def is_excel_file(uploaded_file) -> bool:
    """Return True when the uploaded file is Excel."""
    extension = _get_file_extension(uploaded_file.name or "")
    return extension in {".xlsx", ".xls"}


def display_extracted_text_preview(extracted_text: str, metadata: dict) -> None:
    """Show raw text extracted from the PDF."""
    st.subheader("Extracted Text Preview")

    method = metadata.get("extraction_method", "text")
    char_count = len(extracted_text.strip())
    st.caption(f"Extraction method: **{method.upper()}** | Characters: **{char_count}**")

    if metadata.get("ocr_note"):
        st.warning(metadata["ocr_note"])

    if extracted_text.strip():
        # Limit preview length so the UI stays responsive on large PDFs
        preview_limit = 8000
        display_text = extracted_text
        if len(display_text) > preview_limit:
            display_text = display_text[:preview_limit] + "\n\n... (truncated for preview)"
        st.text_area(
            "PDF text content",
            value=display_text,
            height=300,
            disabled=True,
            label_visibility="collapsed",
        )
    else:
        st.warning(
            "No text could be extracted from this PDF. "
            "The file may be image-only; install Tesseract OCR for scanned documents."
        )


def run_extraction_engine(uploaded_file) -> tuple[pd.DataFrame | None, dict, ExtractionResult | None, bool]:
    """
    Run the Financial Data Extraction Engine on any supported file.

    Returns:
        (financial_data, metadata, extraction_result, failed)
    """
    file_label = "PDF" if is_pdf_file(uploaded_file) else "Excel"
    print(f"[APP] {file_label} upload detected — starting extraction engine")
    st.write(f"Debug: **{file_label}** file detected. Starting extraction pipeline...")

    metadata: dict = {}
    extraction_result: ExtractionResult | None = None

    try:
        with st.spinner(f"Processing {file_label}..."):
            financial_data, metadata, extraction_result = load_uploaded_file_with_details(
                uploaded_file
            )
            print(
                f"[APP] Extraction complete — "
                f"{extraction_result.summary.get('fields_extracted', 0)} fields extracted"
            )
            st.write(
                f"Debug: Extraction finished. Method = **{metadata.get('extraction_method', 'unknown')}**."
            )

        st.success(f"{file_label} processed successfully! Review extracted data below.")

    except ImportError as error:
        print(f"[APP] ImportError: {error}")
        st.error(f"**Missing library:** {error}\n\nRun: `pip install -r requirements.txt`")
        with st.expander("Exception details"):
            st.exception(error)
        return None, metadata, extraction_result, True

    except Exception as error:
        print(f"[APP] Extraction error: {error}")
        st.error(f"**{file_label} extraction failed.** Please try another file.")
        with st.expander("Exception details"):
            st.exception(error)

        # Fallback: show raw text if PDF text was partially extracted
        raw_text = metadata.get("final_text") or metadata.get("raw_text") or ""
        if raw_text.strip():
            st.info("Partial text extracted before the error:")
            display_extracted_text_preview(raw_text, metadata)
        return None, metadata, extraction_result, True

    # PDF: show extracted text preview immediately
    if is_pdf_file(uploaded_file):
        display_text = metadata.get("final_text") or metadata.get("raw_text") or ""
        display_extracted_text_preview(display_text, metadata)

    # Show full extraction debug (audit trail, missing fields, warnings)
    if extraction_result is not None:
        display_full_extraction_debug(extraction_result)

    return financial_data, metadata, extraction_result, False


def display_upload_instructions() -> None:
    """Guidance shown before a file is uploaded."""
    st.info(
        "**Upload Excel (.xlsx, .xls) or PDF (.pdf)** with borrower financial data.\n\n"
        "**Automatically extracted fields:**\n"
        "- Revenue, PAT / Net Income, Net Worth, Total Assets, Total Debt\n"
        "- EBIT, Interest Expense, CAR / CRAR, GNPA, NPA, Collection Efficiency\n"
        "- Credit Ratings (AAA through D)\n\n"
        "**Excel:** column names are mapped automatically (PAT, Borrowings, Finance Cost, etc.)\n\n"
        "**PDF / Annual reports:** full extraction pipeline with tables, OCR, and fuzzy label mapping.\n\n"
        "Values like `₹10,004 Cr`, `5.2%`, and `(₹500 Cr)` are cleaned automatically."
    )


def process_borrower(financial_data: pd.DataFrame, row_index: int) -> None:
    """Run the full credit analysis pipeline for one borrower."""
    borrower_df = financial_data.iloc[[row_index]].reset_index(drop=True)

    try:
        ratios = calculate_all_ratios(borrower_df)
        rating_info = get_credit_rating_info(borrower_df)
        scoring_result = score_borrower(ratios, **rating_info)
        flags = detect_red_flags_from_financial_data(borrower_df)
    except KeyError as error:
        st.error(
            f"Could not calculate ratios - a required field is missing: {error}. "
            "Please check your file and the extraction preview above."
        )
        return
    except ValueError as error:
        st.error(f"Could not process borrower data: {error}")
        return
    except Exception as error:
        st.error(
            f"An unexpected error occurred during analysis: {error}. "
            "Please verify your uploaded data."
        )
        return

    overall_score = scoring_result["overall_score"]
    risk_category = scoring_result["risk_category"]
    sub_scores = scoring_result["sub_scores"]

    display_summary_cards(overall_score, risk_category, ratios, rating_info)
    st.divider()

    display_ratio_cards(ratios)
    st.divider()

    left_col, right_col = st.columns(2)
    with left_col:
        display_sub_scores(sub_scores)
    with right_col:
        st.subheader("Score Summary")
        st.write(f"**Overall Credit Score:** {overall_score:.1f} / 100")
        st.write(f"**Risk Category:** {risk_category}")
        if rating_info.get("credit_rating"):
            st.write(
                f"**Credit Rating:** {rating_info['credit_rating']} "
                f"(Internal Score: {rating_info.get('credit_rating_score', 'N/A')}/100)"
            )

    st.divider()
    display_red_flags(flags)


def main() -> None:
    """Main entry point for the Streamlit dashboard."""
    configure_page()
    apply_custom_styles()

    st.markdown(
        '<p class="main-header">NBFC Credit Risk Scorecard</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">Upload Excel or PDF financials to assess credit risk</p>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Data Upload")
        uploaded_file = st.file_uploader(
            "Upload Excel or PDF",
            type=["xlsx", "xls", "pdf"],
            help="Financial statements in Excel or PDF format.",
        )

    # Only process when a file is actually uploaded
    if uploaded_file is None:
        display_upload_instructions()
        return

    extraction_result: ExtractionResult | None = None

    # --- Run extraction engine for PDF or Excel ---
    if is_pdf_file(uploaded_file) or is_excel_file(uploaded_file):
        financial_data, load_metadata, extraction_result, failed = run_extraction_engine(
            uploaded_file
        )
        if failed:
            return
    else:
        st.error("Unsupported file type. Please upload .xlsx, .xls, or .pdf")
        return

    if financial_data is None or financial_data.empty:
        st.warning("No financial data could be loaded from the file.")
        return

    # --- Validate (errors block analysis; warnings are informational) ---
    can_run, validation_errors, validation_warnings = validate_financial_data(financial_data)

    for warning_message in validation_warnings:
        st.warning(warning_message)

    # --- Borrower selection ---
    if COL_BORROWER_NAME in financial_data.columns:
        borrower_options = financial_data[COL_BORROWER_NAME].astype(str).tolist()
    else:
        borrower_options = [
            f"Borrower {index + 1}" for index in range(len(financial_data))
        ]

    with st.sidebar:
        selected_borrower = st.selectbox("Select Borrower", borrower_options)
        row_index = borrower_options.index(selected_borrower)

        st.divider()
        st.caption("Cleaned values (selected borrower)")
        display_cleaned_data_preview(financial_data.iloc[[row_index]])

    st.subheader(f"Credit Analysis: {selected_borrower}")

    # --- Extraction preview (always shown before calculation) ---
    display_extraction_preview(financial_data.iloc[[row_index]])

    if not can_run:
        st.error("**Cannot run credit analysis - please fix the following:**")
        for error_message in validation_errors:
            st.error(error_message)
        with st.expander("Detected columns in uploaded file"):
            st.write(list(financial_data.columns))
        return

    st.divider()
    process_borrower(financial_data, row_index)


if __name__ == "__main__":
    main()
