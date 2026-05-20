"""
Credit scorecard module — converts financial ratios into risk scores.

Each ratio is scored from 0 to 100 using simple, rule-based thresholds.
A weighted average produces the overall score, which is mapped to a risk
category (Low, Moderate, High, or Critical).

Higher scores mean stronger financial health and lower credit risk.
"""

from __future__ import annotations

import pandas as pd

from src.ratios import calculate_all_ratios
from src.utils import COL_CREDIT_RATING, COL_CREDIT_RATING_SCORE

# ---------------------------------------------------------------------------
# Risk category labels
# ---------------------------------------------------------------------------
LOW_RISK = "Low Risk"
MODERATE_RISK = "Moderate Risk"
HIGH_RISK = "High Risk"
CRITICAL_RISK = "Critical Risk"

# ---------------------------------------------------------------------------
# Weights for the overall score (must add up to 1.0)
# Leverage and interest coverage get higher weight because they directly
# reflect a borrower's ability to repay debt.
# ---------------------------------------------------------------------------
RATIO_WEIGHTS: dict[str, float] = {
    "roa": 0.20,
    "roe": 0.20,
    "debt_equity_ratio": 0.30,
    "interest_coverage_ratio": 0.30,
}

# ---------------------------------------------------------------------------
# Rule-based thresholds
#
# Each entry is (cutoff_value, score).
# For "higher is better" ratios, we check value >= cutoff.
# For "lower is better" ratios, we check value <= cutoff.
# ---------------------------------------------------------------------------
ROA_THRESHOLDS: list[tuple[float, int]] = [
    (0.10, 100),  # ROA >= 10%  → excellent
    (0.07, 85),   # ROA >= 7%   → very good
    (0.05, 70),   # ROA >= 5%   → good
    (0.03, 50),   # ROA >= 3%   → average
    (0.01, 30),   # ROA >= 1%   → weak
    (0.00, 15),   # ROA >= 0%   → poor (break-even)
]

ROE_THRESHOLDS: list[tuple[float, int]] = [
    (0.20, 100),  # ROE >= 20% → excellent
    (0.15, 85),
    (0.10, 70),
    (0.07, 50),
    (0.03, 30),
    (0.00, 15),
]

# Lower debt-to-equity is safer, so thresholds use "<=" logic.
DEBT_EQUITY_THRESHOLDS: list[tuple[float, int]] = [
    (0.50, 100),  # D/E <= 0.5 → very low leverage
    (1.00, 85),
    (1.50, 70),
    (2.00, 50),
    (3.00, 30),
    (5.00, 15),
]

INTEREST_COVERAGE_THRESHOLDS: list[tuple[float, int]] = [
    (5.0, 100),   # EBIT covers interest 5× → very safe
    (3.0, 85),
    (2.0, 70),
    (1.5, 50),
    (1.0, 30),    # Barely covers interest
    (0.5, 15),
]

# Overall score cutoffs for risk classification
RISK_CATEGORY_THRESHOLDS: list[tuple[float, str]] = [
    (75, LOW_RISK),
    (50, MODERATE_RISK),
    (25, HIGH_RISK),
]


def _score_higher_is_better(
    value: float | None,
    thresholds: list[tuple[float, int]],
) -> int:
    """
    Score a ratio where a larger value is better (e.g. ROA, ROE).

    Walks through thresholds from best to worst and returns the first
    matching score. Returns 0 when the value is missing or negative.
    """
    if value is None or value < 0:
        return 0

    for minimum_value, score in thresholds:
        if value >= minimum_value:
            return score

    return 0


def _score_lower_is_better(
    value: float | None,
    thresholds: list[tuple[float, int]],
) -> int:
    """
    Score a ratio where a smaller value is better (e.g. debt-to-equity).

    Walks through thresholds from best to worst and returns the first
    matching score. Returns 0 when the value is missing or negative.
    """
    if value is None or value < 0:
        return 0

    for maximum_value, score in thresholds:
        if value <= maximum_value:
            return score

    return 0


def score_roa(value: float | None) -> int:
    """Convert Return on Assets (ROA) into a score from 0 to 100."""
    return _score_higher_is_better(value, ROA_THRESHOLDS)


def score_roe(value: float | None) -> int:
    """Convert Return on Equity (ROE) into a score from 0 to 100."""
    return _score_higher_is_better(value, ROE_THRESHOLDS)


def score_debt_equity_ratio(value: float | None) -> int:
    """Convert Debt-to-Equity ratio into a score from 0 to 100."""
    return _score_lower_is_better(value, DEBT_EQUITY_THRESHOLDS)


def score_interest_coverage_ratio(value: float | None) -> int:
    """Convert Interest Coverage ratio into a score from 0 to 100."""
    return _score_higher_is_better(value, INTEREST_COVERAGE_THRESHOLDS)


def calculate_sub_scores(ratios: dict[str, float | None]) -> dict[str, int]:
    """
    Convert each financial ratio into an individual sub-score (0–100).

    Args:
        ratios: Dictionary from calculate_all_ratios(), e.g.
                {"roa": 0.05, "roe": 0.12, ...}

    Returns:
        Dictionary mapping ratio name to its sub-score.
    """
    return {
        "roa": score_roa(ratios.get("roa")),
        "roe": score_roe(ratios.get("roe")),
        "debt_equity_ratio": score_debt_equity_ratio(ratios.get("debt_equity_ratio")),
        "interest_coverage_ratio": score_interest_coverage_ratio(
            ratios.get("interest_coverage_ratio")
        ),
    }


def calculate_overall_score(sub_scores: dict[str, int]) -> float:
    """
    Compute the weighted overall score from individual sub-scores.

    Formula:
        overall = (roa_score × w_roa) + (roe_score × w_roe) + ...

    Returns:
        Weighted average rounded to two decimal places (0–100).
    """
    weighted_total = 0.0

    for ratio_name, weight in RATIO_WEIGHTS.items():
        weighted_total += sub_scores[ratio_name] * weight

    return round(weighted_total, 2)


def classify_risk(overall_score: float) -> str:
    """
    Map an overall score to a risk category.

    Score ranges:
        75–100 → Low Risk
        50–74  → Moderate Risk
        25–49  → High Risk
         0–24  → Critical Risk
    """
    for minimum_score, category in RISK_CATEGORY_THRESHOLDS:
        if overall_score >= minimum_score:
            return category

    return CRITICAL_RISK


def get_credit_rating_info(df: pd.DataFrame) -> dict:
    """Read credit rating and internal score from prepared financial data."""
    rating = None
    rating_score = None

    if COL_CREDIT_RATING in df.columns:
        val = df[COL_CREDIT_RATING].iloc[0]
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            rating = str(val)

    if COL_CREDIT_RATING_SCORE in df.columns:
        val = df[COL_CREDIT_RATING_SCORE].iloc[0]
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            rating_score = int(val) if val == int(val) else int(round(float(val)))

    return {"credit_rating": rating, "credit_rating_score": rating_score}


def score_borrower(
    ratios: dict[str, float | None],
    *,
    credit_rating: str | None = None,
    credit_rating_score: int | None = None,
) -> dict:
    """
    Full scoring pipeline: ratios → sub-scores → overall score → risk category.

    Args:
        ratios: Dictionary of calculated financial ratios.
        credit_rating: Optional agency rating (e.g. 'AA+').
        credit_rating_score: Optional internal rating score (0-100).

    Returns:
        {
            "overall_score": 72.5,
            "risk_category": "Moderate Risk",
            "sub_scores": {...},
            "credit_rating": "AA+",
            "credit_rating_score": 95,
        }
    """
    sub_scores = calculate_sub_scores(ratios)
    overall_score = calculate_overall_score(sub_scores)
    risk_category = classify_risk(overall_score)

    return {
        "overall_score": overall_score,
        "risk_category": risk_category,
        "sub_scores": sub_scores,
        "credit_rating": credit_rating,
        "credit_rating_score": credit_rating_score,
    }


def score_from_financial_data(df: pd.DataFrame) -> dict:
    """
    Convenience function: score a borrower directly from financial data.

    Args:
        df: pandas DataFrame with one row of borrower financial data
            (same columns expected by src.ratios).

    Returns:
        Scoring result dictionary (overall_score, risk_category, sub_scores).
    """
    ratios = calculate_all_ratios(df)
    rating_info = get_credit_rating_info(df)
    return score_borrower(ratios, **rating_info)
