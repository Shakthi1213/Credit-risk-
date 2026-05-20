"""
Data preparation utilities for the NBFC credit scorecard.

Handles:
    - Excel column name normalization and mapping
    - Financial value cleaning (₹, commas, Cr, %, brackets, etc.)
    - Credit rating normalization
    - Validation with user-friendly messages
"""

from __future__ import annotations

import re

import pandas as pd

from src.ratings import normalize_credit_rating, rating_to_score

# ---------------------------------------------------------------------------
# Standard column names
# ---------------------------------------------------------------------------
COL_REVENUE = "revenue"
COL_NET_INCOME = "net_income"
COL_TOTAL_ASSETS = "total_assets"
COL_TOTAL_EQUITY = "total_equity"
COL_TOTAL_DEBT = "total_debt"
COL_EBIT = "ebit"
COL_INTEREST_EXPENSE = "interest_expense"
COL_CAR = "car_crar"
COL_GNPA = "gnpa"
COL_NPA = "npa"
COL_NET_NPA = "net_npa"
COL_COLLECTION_EFFICIENCY = "collection_efficiency"
COL_CREDIT_RATING = "credit_rating"
COL_CREDIT_RATING_SCORE = "credit_rating_score"
COL_CURRENT_ASSETS = "current_assets"
COL_CURRENT_LIABILITIES = "current_liabilities"
COL_PRIOR_NET_INCOME = "prior_net_income"
COL_BORROWER_NAME = "borrower_name"

# Core fields needed for standard ratio + scoring pipeline
REQUIRED_COLUMNS = [
    COL_NET_INCOME,
    COL_TOTAL_ASSETS,
    COL_TOTAL_EQUITY,
    COL_TOTAL_DEBT,
    COL_EBIT,
    COL_INTEREST_EXPENSE,
]

# Optional NBFC / regulatory fields
OPTIONAL_COLUMNS = [
    COL_REVENUE,
    COL_CAR,
    COL_GNPA,
    COL_NPA,
    COL_NET_NPA,
    COL_COLLECTION_EFFICIENCY,
    COL_CREDIT_RATING,
    COL_CURRENT_ASSETS,
    COL_CURRENT_LIABILITIES,
    COL_PRIOR_NET_INCOME,
]

ALL_EXTRACTABLE_FIELDS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS + [COL_BORROWER_NAME]

# Columns cleaned as numeric values
FINANCIAL_VALUE_COLUMNS = [
    COL_REVENUE,
    COL_NET_INCOME,
    COL_TOTAL_ASSETS,
    COL_TOTAL_EQUITY,
    COL_TOTAL_DEBT,
    COL_EBIT,
    COL_INTEREST_EXPENSE,
    COL_CAR,
    COL_GNPA,
    COL_NPA,
    COL_NET_NPA,
    COL_COLLECTION_EFFICIENCY,
    COL_CURRENT_ASSETS,
    COL_CURRENT_LIABILITIES,
    COL_PRIOR_NET_INCOME,
]

# Percentage fields stored as decimals (e.g. 5% -> 0.05)
PERCENT_COLUMNS = [
    COL_CAR,
    COL_GNPA,
    COL_NPA,
    COL_NET_NPA,
    COL_COLLECTION_EFFICIENCY,
]

# User-friendly labels for dashboard messages
FIELD_LABELS: dict[str, str] = {
    COL_REVENUE: "Revenue",
    COL_NET_INCOME: "PAT / Net Income",
    COL_TOTAL_ASSETS: "Total Assets",
    COL_TOTAL_EQUITY: "Net Worth / Total Equity",
    COL_TOTAL_DEBT: "Total Debt / Borrowings",
    COL_EBIT: "EBIT",
    COL_INTEREST_EXPENSE: "Interest Expense / Finance Cost",
    COL_CAR: "CAR / CRAR",
    COL_GNPA: "GNPA",
    COL_NPA: "NPA",
    COL_NET_NPA: "Net NPA",
    COL_COLLECTION_EFFICIENCY: "Collection Efficiency",
    COL_CREDIT_RATING: "Credit Rating",
    COL_CREDIT_RATING_SCORE: "Credit Rating Score",
}

# Map common Excel / PDF labels to standard names
COLUMN_ALIASES: dict[str, list[str]] = {
    COL_REVENUE: [
        "revenue",
        "totalrevenue",
        "sales",
        "turnover",
        "totalincome",
    ],
    COL_NET_INCOME: [
        "pat",
        "netprofit",
        "profitaftertax",
        "netincome",
        "profitloss",
    ],
    COL_TOTAL_ASSETS: [
        "assets",
        "totalassets",
        "totassets",
    ],
    COL_TOTAL_EQUITY: [
        "networth",
        "shareholdersequity",
        "shareholderfund",
        "shareholderfunds",
        "equity",
        "totalequity",
    ],
    COL_TOTAL_DEBT: [
        "borrowings",
        "totaldebt",
        "totalborrowings",
        "debt",
    ],
    COL_EBIT: [
        "ebit",
        "operatingprofit",
        "profitbeforeinterestandtax",
    ],
    COL_INTEREST_EXPENSE: [
        "financecost",
        "interestexpense",
        "interestpaid",
        "financecosts",
    ],
    COL_CAR: [
        "car",
        "crar",
        "capitaladequacyratio",
        "capitaladequacy",
    ],
    COL_GNPA: [
        "gnpa",
        "grossnpa",
        "grossnonperformingassets",
    ],
    COL_NPA: [
        "npa",
        "nonperformingassets",
    ],
    COL_NET_NPA: [
        "netnpa",
        "netnonperformingassets",
    ],
    COL_COLLECTION_EFFICIENCY: [
        "collectionefficiency",
        "collectioneff",
        "efficiency",
    ],
    COL_CREDIT_RATING: [
        "creditrating",
        "rating",
        "externalrating",
        "agencyrating",
    ],
    COL_CURRENT_ASSETS: [
        "currentassets",
        "ca",
    ],
    COL_CURRENT_LIABILITIES: [
        "currentliabilities",
        "cl",
    ],
    COL_PRIOR_NET_INCOME: [
        "priornetincome",
        "previousnetincome",
        "prioryearnetincome",
        "priorpat",
    ],
    COL_BORROWER_NAME: [
        "borrowername",
        "companyname",
        "customername",
        "name",
        "nbfcname",
    ],
}


def normalize_column_name(column_name: str) -> str:
    """
    Normalize a column name for matching.

    - Converts to lowercase
    - Removes spaces, underscores, hyphens, and special characters
    """
    if column_name is None:
        return ""

    text = str(column_name).strip().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _build_column_lookup() -> dict[str, str]:
    """Build a lookup from normalized alias -> standard column name."""
    lookup: dict[str, str] = {}

    for standard_name, aliases in COLUMN_ALIASES.items():
        lookup[normalize_column_name(standard_name)] = standard_name
        for alias in aliases:
            lookup[normalize_column_name(alias)] = standard_name

    return lookup


_COLUMN_LOOKUP = _build_column_lookup()


def map_column_names(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Rename DataFrame columns to standard internal names.

    Returns:
        (renamed_dataframe, mapping_report)
    """
    renamed_df = df.copy()
    rename_map: dict[str, str] = {}
    used_standard_names: set[str] = set()

    for original_name in renamed_df.columns:
        normalized = normalize_column_name(original_name)
        standard_name = _COLUMN_LOOKUP.get(normalized)

        if not standard_name:
            continue

        if original_name == standard_name:
            used_standard_names.add(standard_name)
            continue

        if standard_name in used_standard_names:
            continue

        rename_map[original_name] = standard_name
        used_standard_names.add(standard_name)

    if rename_map:
        renamed_df = renamed_df.rename(columns=rename_map)

    return renamed_df, rename_map


def clean_financial_value(value) -> float | None:
    """
    Convert a messy financial cell value into a clean float.

    Handles: ₹, commas, Cr/crore, %, brackets, spaces.

    Examples:
        "₹10,004 Cr"  -> 10004.0
        "5.2%"        -> 5.2
        "(₹500 Cr)"   -> -500.0
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "-", "none", "null"}:
        return None

    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()

    text = text.replace("₹", "").replace("rs.", "").replace("rs", "")
    text = text.replace(",", "").replace(" ", "")
    text = re.sub(r"crore|cr", "", text, flags=re.IGNORECASE)
    text = text.replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)

    if not text or text in {".", "-", "-."}:
        return None

    try:
        number = float(text)
        return -number if is_negative else number
    except ValueError:
        return None


def normalize_percent_storage(value: float | None) -> float | None:
    """
    Store percentage fields as decimals for ratio display.

    Example: 5.2 (from "5.2%") -> 0.052
    Values already in decimal form (<= 1) are kept as-is.
    """
    if value is None:
        return None

    if value > 1:
        return value / 100.0

    return value


def clean_financial_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean numeric columns and normalize ratings / percentages."""
    cleaned_df = df.copy()

    for column in cleaned_df.columns:
        if column == COL_CREDIT_RATING:
            cleaned_df[column] = cleaned_df[column].apply(
                lambda value: normalize_credit_rating(value) if value is not None else None
            )
            cleaned_df[COL_CREDIT_RATING_SCORE] = cleaned_df[column].apply(rating_to_score)
            continue

        if column in FINANCIAL_VALUE_COLUMNS:
            cleaned_df[column] = cleaned_df[column].apply(clean_financial_value)
            if column in PERCENT_COLUMNS:
                cleaned_df[column] = cleaned_df[column].apply(normalize_percent_storage)

    # Add rating score if rating column exists but score column does not
    if COL_CREDIT_RATING in cleaned_df.columns and COL_CREDIT_RATING_SCORE not in cleaned_df.columns:
        cleaned_df[COL_CREDIT_RATING_SCORE] = cleaned_df[COL_CREDIT_RATING].apply(rating_to_score)

    return cleaned_df


def _column_all_null(df: pd.DataFrame, column: str) -> bool:
    """Check whether every value in a column is None or NaN."""
    if column not in df.columns:
        return True
    return df[column].isna().all()


def get_missing_required_columns(df: pd.DataFrame) -> list[str]:
    """Return required columns that are missing or entirely empty."""
    missing: list[str] = []

    for column in REQUIRED_COLUMNS:
        if column not in df.columns or _column_all_null(df, column):
            missing.append(column)

    return missing


def get_missing_optional_columns(df: pd.DataFrame) -> list[str]:
    """Return optional columns that are missing or empty."""
    missing: list[str] = []

    for column in OPTIONAL_COLUMNS:
        if column not in df.columns or _column_all_null(df, column):
            missing.append(column)

    return missing


def format_financial_display(value: float | None, column: str = "") -> str:
    """Format a cleaned number for display in the dashboard preview."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"

    if column in PERCENT_COLUMNS:
        return f"{value * 100:.2f}%"

    if column == COL_CREDIT_RATING_SCORE:
        return f"{int(value)}" if value == int(value) else f"{value:.0f}"

    if abs(value) >= 1_000_000:
        return f"₹{value:,.0f}"
    if value == int(value):
        return f"₹{int(value):,}"
    return f"₹{value:,.2f}"


def format_field_preview_value(column: str, value) -> str:
    """Format any field value for the extraction preview table."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"

    if column == COL_CREDIT_RATING:
        return str(value)

    if column in FINANCIAL_VALUE_COLUMNS or column == COL_CREDIT_RATING_SCORE:
        if isinstance(value, (int, float)):
            return format_financial_display(float(value), column)
        return format_financial_display(clean_financial_value(value), column)

    return str(value)


def build_extraction_preview(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a preview table showing all extractable fields and their values.

    Columns: Field | Value | Status
    """
    row = df.iloc[0] if not df.empty else pd.Series(dtype=object)
    preview_rows: list[dict[str, str]] = []

    for field in ALL_EXTRACTABLE_FIELDS:
        if field == COL_CREDIT_RATING_SCORE:
            continue

        value = row.get(field) if field in row.index else None
        has_value = value is not None and not (isinstance(value, float) and pd.isna(value))

        if field in REQUIRED_COLUMNS:
            status = "Present" if has_value else "Missing (required)"
        else:
            status = "Present" if has_value else "Missing (optional)"

        preview_rows.append(
            {
                "Field": FIELD_LABELS.get(field, field),
                "Value": format_field_preview_value(field, value),
                "Status": status,
            }
        )

    # Show derived rating score when rating is present
    if COL_CREDIT_RATING_SCORE in row.index and not _column_all_null(df, COL_CREDIT_RATING_SCORE):
        preview_rows.append(
            {
                "Field": FIELD_LABELS[COL_CREDIT_RATING_SCORE],
                "Value": format_field_preview_value(
                    COL_CREDIT_RATING_SCORE, row[COL_CREDIT_RATING_SCORE]
                ),
                "Status": "Derived",
            }
        )

    return pd.DataFrame(preview_rows)


def prepare_financial_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Full data preparation: map columns, clean values, add rating score.

    Returns:
        (prepared_dataframe, column_mapping_report)
    """
    prepared, column_mapping = map_column_names(df)
    prepared = clean_financial_dataframe(prepared)
    return prepared, column_mapping


def validate_financial_data(df: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    """
    Validate financial data for the scorecard pipeline.

    Returns:
        (can_run_analysis, error_messages, warning_messages)

    Analysis can run when core required fields are present.
    Warnings are shown for missing optional NBFC fields.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if df.empty:
        return False, ["The uploaded file contains no data rows."], []

    missing_required = get_missing_required_columns(df)
    for column in missing_required:
        errors.append(
            f"Missing or empty required field: **{FIELD_LABELS.get(column, column)}**. "
            "Upload a file with this metric or check PDF extraction results."
        )

    missing_optional = get_missing_optional_columns(df)
    for column in missing_optional:
        warnings.append(
            f"Optional field not found: **{FIELD_LABELS.get(column, column)}**. "
            "Some NBFC metrics will not be shown."
        )

    can_run = len(missing_required) == 0
    return can_run, errors, warnings
