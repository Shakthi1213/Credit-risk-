"""
Financial red-flag detection for credit risk analysis.

Each check uses simple, rule-based thresholds and returns a message with
a severity level:
    - "error"   → critical issues (shown with st.error in the dashboard)
    - "warning" → caution items (shown with st.warning in the dashboard)
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd

from src.ratios import calculate_all_ratios
from src.utils import (
    COL_CAR,
    COL_CURRENT_ASSETS,
    COL_CURRENT_LIABILITIES,
    COL_GNPA,
    COL_NET_INCOME,
)

# ---------------------------------------------------------------------------
# Rule-based thresholds
# ---------------------------------------------------------------------------
DEBT_EQUITY_HIGH_THRESHOLD = 2.0
DEBT_EQUITY_LEVERAGE_WARNING_THRESHOLD = 1.5
ROA_LOW_THRESHOLD = 0.03
INTEREST_COVERAGE_WEAK_THRESHOLD = 1.5
CURRENT_RATIO_WEAK_THRESHOLD = 1.0
DEBT_TO_ASSETS_HIGH_THRESHOLD = 0.60
PROFITABILITY_DECLINE_THRESHOLD = 0.01
GNPA_HIGH_THRESHOLD = 0.05
CAR_LOW_THRESHOLD = 0.12


class RedFlag(TypedDict):
    """A single red-flag alert with message and severity."""

    message: str
    severity: str  # "warning" or "error"


def _make_flag(message: str, severity: str) -> RedFlag:
    return {"message": message, "severity": severity}


def flag_high_debt_equity(debt_equity_ratio: float | None) -> RedFlag | None:
    """Critical flag: Debt-to-Equity ratio above 2.0."""
    if debt_equity_ratio is None:
        return None

    if debt_equity_ratio > DEBT_EQUITY_HIGH_THRESHOLD:
        return _make_flag(
            f"High Debt-to-Equity Ratio ({debt_equity_ratio:.2f}x) - "
            "borrower is heavily leveraged.",
            "error",
        )

    return None


def flag_high_leverage_warning(
    debt_equity_ratio: float | None,
    debt_to_assets_ratio: float | None,
) -> RedFlag | None:
    """
    Warning flag: elevated leverage but below critical D/E threshold.

    Triggered when D/E is between 1.5–2.0 or debt-to-assets exceeds 60%.
    """
    if (
        debt_equity_ratio is not None
        and DEBT_EQUITY_LEVERAGE_WARNING_THRESHOLD
        < debt_equity_ratio
        <= DEBT_EQUITY_HIGH_THRESHOLD
    ):
        return _make_flag(
            f"High Leverage Warning - Debt-to-Equity is {debt_equity_ratio:.2f}x. "
            "Monitor repayment capacity closely.",
            "warning",
        )

    if (
        debt_to_assets_ratio is not None
        and debt_to_assets_ratio > DEBT_TO_ASSETS_HIGH_THRESHOLD
    ):
        return _make_flag(
            f"High Leverage Warning - Debt is "
            f"{debt_to_assets_ratio * 100:.1f}% of total assets.",
            "warning",
        )

    return None


def flag_low_roa(roa: float | None) -> RedFlag | None:
    """Critical flag: ROA below 3%."""
    if roa is None:
        return None

    if roa < ROA_LOW_THRESHOLD:
        return _make_flag(
            f"Low ROA ({roa * 100:.2f}%) - "
            "assets are not generating sufficient returns.",
            "error",
        )

    return None


def flag_weak_interest_coverage(interest_coverage_ratio: float | None) -> RedFlag | None:
    """Critical flag: Interest coverage below 1.5x."""
    if interest_coverage_ratio is None:
        return None

    if interest_coverage_ratio < INTEREST_COVERAGE_WEAK_THRESHOLD:
        return _make_flag(
            f"Weak Interest Coverage ({interest_coverage_ratio:.2f}x) - "
            "operating earnings may not comfortably cover interest payments.",
            "error",
        )

    return None


def flag_weak_liquidity(
    current_ratio: float | None,
    current_assets: float | None = None,
    current_liabilities: float | None = None,
) -> RedFlag | None:
    """
    Warning flag: weak short-term liquidity.

    Requires current_assets and current_liabilities in the uploaded data.
    """
    if current_ratio is not None and current_ratio < CURRENT_RATIO_WEAK_THRESHOLD:
        return _make_flag(
            f"Weak Liquidity Warning - Current Ratio is {current_ratio:.2f}x "
            "(below 1.0 indicates short-term obligations may exceed liquid assets).",
            "warning",
        )

    # Fallback when ratio could not be computed but raw values suggest stress
    if (
        current_assets is not None
        and current_liabilities is not None
        and current_liabilities > 0
        and current_assets < current_liabilities
    ):
        return _make_flag(
            "Weak Liquidity Warning - Current assets are lower than current liabilities.",
            "warning",
        )

    return None


def flag_high_gnpa(gnpa: float | None) -> RedFlag | None:
    """Warning flag: GNPA above 5%."""
    if gnpa is not None and gnpa > GNPA_HIGH_THRESHOLD:
        return _make_flag(
            f"High GNPA ({gnpa * 100:.2f}%) - asset quality under pressure.",
            "warning",
        )
    return None


def flag_low_car(car: float | None) -> RedFlag | None:
    """Warning flag: CAR/CRAR below 12%."""
    if car is not None and car < CAR_LOW_THRESHOLD:
        return _make_flag(
            f"Low CAR/CRAR ({car * 100:.2f}%) - capital adequacy may be insufficient.",
            "warning",
        )
    return None


def flag_declining_profitability(
    current_ratios: dict[str, float | None],
    prior_ratios: dict[str, float | None] | None = None,
    *,
    current_net_income: float | None = None,
    prior_net_income: float | None = None,
) -> RedFlag | None:
    """Warning flag: profitability trending downward."""
    decline_reasons: list[str] = []

    if (
        current_net_income is not None
        and prior_net_income is not None
        and current_net_income < prior_net_income
    ):
        decline_reasons.append(
            f"net income fell from {prior_net_income:,.0f} to {current_net_income:,.0f}"
        )

    if prior_ratios is not None:
        current_roa = current_ratios.get("roa")
        prior_roa = prior_ratios.get("roa")
        if (
            current_roa is not None
            and prior_roa is not None
            and current_roa < prior_roa - PROFITABILITY_DECLINE_THRESHOLD
        ):
            decline_reasons.append(
                f"ROA declined from {prior_roa * 100:.2f}% to {current_roa * 100:.2f}%"
            )

        current_roe = current_ratios.get("roe")
        prior_roe = prior_ratios.get("roe")
        if (
            current_roe is not None
            and prior_roe is not None
            and current_roe < prior_roe - PROFITABILITY_DECLINE_THRESHOLD
        ):
            decline_reasons.append(
                f"ROE declined from {prior_roe * 100:.2f}% to {current_roe * 100:.2f}%"
            )

    if not decline_reasons:
        return None

    return _make_flag(
        "Declining Profitability - " + "; ".join(decline_reasons) + ".",
        "warning",
    )


def detect_red_flags(
    ratios: dict[str, float | None],
    prior_ratios: dict[str, float | None] | None = None,
    *,
    current_net_income: float | None = None,
    prior_net_income: float | None = None,
    current_assets: float | None = None,
    current_liabilities: float | None = None,
) -> list[RedFlag]:
    """
    Run all red-flag checks and return a list of alert dictionaries.

    Each item has:
        - message: plain-English warning text
        - severity: "error" or "warning"
    """
    checks: list[RedFlag | None] = [
        flag_high_debt_equity(ratios.get("debt_equity_ratio")),
        flag_high_leverage_warning(
            ratios.get("debt_equity_ratio"),
            ratios.get("debt_to_assets_ratio"),
        ),
        flag_low_roa(ratios.get("roa")),
        flag_weak_interest_coverage(ratios.get("interest_coverage_ratio")),
        flag_weak_liquidity(
            ratios.get("current_ratio"),
            current_assets=current_assets,
            current_liabilities=current_liabilities,
        ),
        flag_high_gnpa(ratios.get("gnpa")),
        flag_low_car(ratios.get("car_crar")),
        flag_declining_profitability(
            ratios,
            prior_ratios,
            current_net_income=current_net_income,
            prior_net_income=prior_net_income,
        ),
    ]

    return [flag for flag in checks if flag is not None]


def detect_red_flags_from_financial_data(df: pd.DataFrame) -> list[RedFlag]:
    """
    Detect red flags directly from prepared borrower financial data.

    Row 0 = current period. Row 1 (if present) = prior period for trends.
    """
    if df.empty:
        return [
            _make_flag("No financial data available to evaluate red flags.", "error")
        ]

    current_df = df.iloc[[0]].reset_index(drop=True)
    ratios = calculate_all_ratios(current_df)

    prior_ratios = None
    if len(df) >= 2:
        prior_ratios = calculate_all_ratios(df.iloc[[1]].reset_index(drop=True))

    current_net_income = None
    prior_net_income = None
    current_assets = None
    current_liabilities = None

    if COL_NET_INCOME in current_df.columns:
        val = current_df[COL_NET_INCOME].iloc[0]
        current_net_income = float(val) if val is not None and not pd.isna(val) else None

    if "prior_net_income" in current_df.columns:
        val = current_df["prior_net_income"].iloc[0]
        prior_net_income = float(val) if val is not None and not pd.isna(val) else None

    if COL_CURRENT_ASSETS in current_df.columns:
        val = current_df[COL_CURRENT_ASSETS].iloc[0]
        current_assets = float(val) if val is not None and not pd.isna(val) else None

    if COL_CURRENT_LIABILITIES in current_df.columns:
        val = current_df[COL_CURRENT_LIABILITIES].iloc[0]
        current_liabilities = float(val) if val is not None and not pd.isna(val) else None

    return detect_red_flags(
        ratios,
        prior_ratios,
        current_net_income=current_net_income,
        prior_net_income=prior_net_income,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
    )
