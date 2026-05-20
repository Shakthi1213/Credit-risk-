"""
Financial ratio and metric calculations for borrower credit analysis.

Computes profitability, leverage, coverage, and NBFC regulatory metrics.
Run prepare_financial_data() from src.utils before calling these functions.
"""

import pandas as pd

from src.utils import (
    COL_CAR,
    COL_COLLECTION_EFFICIENCY,
    COL_CURRENT_ASSETS,
    COL_CURRENT_LIABILITIES,
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
)

COL_SHAREHOLDERS_EQUITY = "shareholders_equity"


def _get_numeric_value(df: pd.DataFrame, column: str, required: bool = True) -> float | None:
    """
    Read a single numeric value from the first row.

    Returns None when missing. Raises KeyError only when required=True.
    """
    if df.empty:
        raise ValueError("Financial data DataFrame is empty.")

    if column not in df.columns:
        if required:
            raise KeyError(f"Missing required column: '{column}'")
        return None

    value = df[column].iloc[0]

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    """Divide safely; returns None on missing values or zero denominator."""
    if numerator is None or denominator is None:
        return None
    if pd.isna(numerator) or pd.isna(denominator):
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def _get_equity(df: pd.DataFrame) -> float | None:
    """Get total equity / net worth from the DataFrame."""
    if COL_TOTAL_EQUITY in df.columns:
        return _get_numeric_value(df, COL_TOTAL_EQUITY, required=False)
    if COL_SHAREHOLDERS_EQUITY in df.columns:
        return _get_numeric_value(df, COL_SHAREHOLDERS_EQUITY, required=False)
    raise KeyError(
        f"Missing equity column. Provide '{COL_TOTAL_EQUITY}' or "
        f"'{COL_SHAREHOLDERS_EQUITY}'."
    )


# ---------------------------------------------------------------------------
# Profitability & leverage ratios (calculated)
# ---------------------------------------------------------------------------


def calculate_roa(df: pd.DataFrame) -> float | None:
    """Return on Assets = Net Income / Total Assets"""
    net_income = _get_numeric_value(df, COL_NET_INCOME)
    total_assets = _get_numeric_value(df, COL_TOTAL_ASSETS)
    return _safe_divide(net_income, total_assets)


def calculate_roe(df: pd.DataFrame) -> float | None:
    """Return on Equity = Net Income / Total Equity"""
    net_income = _get_numeric_value(df, COL_NET_INCOME)
    total_equity = _get_equity(df)
    return _safe_divide(net_income, total_equity)


def calculate_debt_equity_ratio(df: pd.DataFrame) -> float | None:
    """Debt-to-Equity = Total Debt / Total Equity"""
    total_debt = _get_numeric_value(df, COL_TOTAL_DEBT)
    total_equity = _get_equity(df)
    return _safe_divide(total_debt, total_equity)


def calculate_interest_coverage_ratio(df: pd.DataFrame) -> float | None:
    """Interest Coverage = EBIT / Interest Expense"""
    ebit = _get_numeric_value(df, COL_EBIT)
    interest_expense = _get_numeric_value(df, COL_INTEREST_EXPENSE)
    return _safe_divide(ebit, interest_expense)


def calculate_current_ratio(df: pd.DataFrame) -> float | None:
    """Current Ratio = Current Assets / Current Liabilities"""
    if COL_CURRENT_ASSETS not in df.columns or COL_CURRENT_LIABILITIES not in df.columns:
        return None

    current_assets = _get_numeric_value(df, COL_CURRENT_ASSETS, required=False)
    current_liabilities = _get_numeric_value(df, COL_CURRENT_LIABILITIES, required=False)
    return _safe_divide(current_assets, current_liabilities)


def calculate_debt_to_assets_ratio(df: pd.DataFrame) -> float | None:
    """Debt-to-Assets = Total Debt / Total Assets"""
    total_debt = _get_numeric_value(df, COL_TOTAL_DEBT)
    total_assets = _get_numeric_value(df, COL_TOTAL_ASSETS)
    return _safe_divide(total_debt, total_assets)


# ---------------------------------------------------------------------------
# NBFC metrics (reported values or passthrough)
# ---------------------------------------------------------------------------


def calculate_revenue(df: pd.DataFrame) -> float | None:
    """Revenue (reported value from financial statements)."""
    return _get_numeric_value(df, COL_REVENUE, required=False)


def calculate_net_worth(df: pd.DataFrame) -> float | None:
    """Net worth = Total equity (reported or derived)."""
    try:
        return _get_equity(df)
    except KeyError:
        return None


def calculate_car_crar(df: pd.DataFrame) -> float | None:
    """Capital Adequacy Ratio / CRAR (stored as decimal, e.g. 0.15 = 15%)."""
    return _get_numeric_value(df, COL_CAR, required=False)


def calculate_gnpa(df: pd.DataFrame) -> float | None:
    """Gross NPA ratio (stored as decimal, e.g. 0.05 = 5%)."""
    return _get_numeric_value(df, COL_GNPA, required=False)


def calculate_npa(df: pd.DataFrame) -> float | None:
    """NPA ratio (stored as decimal). Uses net_npa if npa is not available."""
    npa = _get_numeric_value(df, COL_NPA, required=False)
    if npa is not None:
        return npa
    return _get_numeric_value(df, COL_NET_NPA, required=False)


def calculate_net_npa(df: pd.DataFrame) -> float | None:
    """Net NPA ratio (stored as decimal)."""
    return _get_numeric_value(df, COL_NET_NPA, required=False)


def calculate_collection_efficiency(df: pd.DataFrame) -> float | None:
    """Collection efficiency (stored as decimal, e.g. 0.95 = 95%)."""
    return _get_numeric_value(df, COL_COLLECTION_EFFICIENCY, required=False)


def calculate_all_ratios(df: pd.DataFrame) -> dict[str, float | None]:
    """
    Calculate all financial ratios and NBFC metrics for a borrower.

    Returns None for any metric that cannot be computed due to missing data.
    """
    return {
        # Calculated ratios
        "roa": calculate_roa(df),
        "roe": calculate_roe(df),
        "debt_equity_ratio": calculate_debt_equity_ratio(df),
        "interest_coverage_ratio": calculate_interest_coverage_ratio(df),
        "current_ratio": calculate_current_ratio(df),
        "debt_to_assets_ratio": calculate_debt_to_assets_ratio(df),
        # Reported / passthrough metrics
        "revenue": calculate_revenue(df),
        "net_worth": calculate_net_worth(df),
        "car_crar": calculate_car_crar(df),
        "gnpa": calculate_gnpa(df),
        "npa": calculate_npa(df),
        "net_npa": calculate_net_npa(df),
        "collection_efficiency": calculate_collection_efficiency(df),
    }
