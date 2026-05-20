"""
Configuration for the Financial Data Extraction Engine.

Central place for standard field names, label aliases, section keywords,
and extraction thresholds.
"""

# ---------------------------------------------------------------------------
# Standard financial fields (used by ratios, scoring, flags)
# ---------------------------------------------------------------------------
FIELD_REVENUE = "revenue"
FIELD_NET_INCOME = "net_income"
FIELD_PBT = "pbt"
FIELD_EBITDA = "ebitda"
FIELD_EBIT = "ebit"
FIELD_TOTAL_ASSETS = "total_assets"
FIELD_CURRENT_ASSETS = "current_assets"
FIELD_CASH = "cash_and_equivalents"
FIELD_TOTAL_EQUITY = "total_equity"
FIELD_TOTAL_LIABILITIES = "total_liabilities"
FIELD_TOTAL_DEBT = "total_debt"
FIELD_BORROWINGS = "borrowings"
FIELD_INTEREST_EXPENSE = "interest_expense"
FIELD_FINANCE_COST = "finance_cost"
FIELD_OPERATING_EXPENSES = "operating_expenses"
FIELD_GNPA = "gnpa"
FIELD_NPA = "npa"
FIELD_NET_NPA = "net_npa"
FIELD_CAR = "car_crar"
FIELD_TIER1 = "tier1_capital"
FIELD_COLLECTION_EFFICIENCY = "collection_efficiency"
FIELD_WRITE_OFFS = "write_offs"
FIELD_AUM = "aum"
FIELD_LOAN_BOOK = "loan_book"
FIELD_DISBURSEMENTS = "disbursements"
FIELD_CREDIT_RATING = "credit_rating"
FIELD_BORROWER_NAME = "borrower_name"

# Core fields required for credit scorecard
CORE_FIELDS = [
    FIELD_NET_INCOME,
    FIELD_TOTAL_ASSETS,
    FIELD_TOTAL_EQUITY,
    FIELD_TOTAL_DEBT,
    FIELD_EBIT,
    FIELD_INTEREST_EXPENSE,
]

# All fields the engine attempts to extract
ALL_STANDARD_FIELDS = [
    FIELD_BORROWER_NAME,
    FIELD_REVENUE,
    FIELD_NET_INCOME,
    FIELD_PBT,
    FIELD_EBITDA,
    FIELD_EBIT,
    FIELD_TOTAL_ASSETS,
    FIELD_CURRENT_ASSETS,
    FIELD_CASH,
    FIELD_TOTAL_EQUITY,
    FIELD_TOTAL_LIABILITIES,
    FIELD_TOTAL_DEBT,
    FIELD_BORROWINGS,
    FIELD_INTEREST_EXPENSE,
    FIELD_OPERATING_EXPENSES,
    FIELD_GNPA,
    FIELD_NPA,
    FIELD_NET_NPA,
    FIELD_CAR,
    FIELD_TIER1,
    FIELD_COLLECTION_EFFICIENCY,
    FIELD_WRITE_OFFS,
    FIELD_AUM,
    FIELD_LOAN_BOOK,
    FIELD_DISBURSEMENTS,
    FIELD_CREDIT_RATING,
]

PERCENT_FIELDS = {
    FIELD_GNPA,
    FIELD_NPA,
    FIELD_NET_NPA,
    FIELD_CAR,
    FIELD_COLLECTION_EFFICIENCY,
}

# Human-readable names for UI
FIELD_DISPLAY_NAMES: dict[str, str] = {
    FIELD_REVENUE: "Revenue",
    FIELD_NET_INCOME: "Net Income / PAT",
    FIELD_PBT: "Profit Before Tax",
    FIELD_EBITDA: "EBITDA",
    FIELD_EBIT: "EBIT",
    FIELD_TOTAL_ASSETS: "Total Assets",
    FIELD_CURRENT_ASSETS: "Current Assets",
    FIELD_CASH: "Cash & Cash Equivalents",
    FIELD_TOTAL_EQUITY: "Net Worth / Total Equity",
    FIELD_TOTAL_LIABILITIES: "Total Liabilities",
    FIELD_TOTAL_DEBT: "Total Debt",
    FIELD_BORROWINGS: "Borrowings",
    FIELD_INTEREST_EXPENSE: "Interest Expense",
    FIELD_OPERATING_EXPENSES: "Operating Expenses",
    FIELD_GNPA: "Gross NPA (GNPA)",
    FIELD_NPA: "NPA",
    FIELD_NET_NPA: "Net NPA",
    FIELD_CAR: "CAR / CRAR",
    FIELD_TIER1: "Tier 1 Capital",
    FIELD_COLLECTION_EFFICIENCY: "Collection Efficiency",
    FIELD_WRITE_OFFS: "Write-offs",
    FIELD_AUM: "AUM",
    FIELD_LOAN_BOOK: "Loan Book",
    FIELD_DISBURSEMENTS: "Disbursements",
    FIELD_CREDIT_RATING: "Credit Rating",
    FIELD_BORROWER_NAME: "Borrower Name",
}

# ---------------------------------------------------------------------------
# Label aliases for fuzzy mapping (normalized keys built at runtime)
# ---------------------------------------------------------------------------
FIELD_LABEL_ALIASES: dict[str, list[str]] = {
    FIELD_REVENUE: [
        "revenue from operations",
        "total revenue",
        "revenue",
        "sales",
        "turnover",
        "total income",
    ],
    FIELD_NET_INCOME: [
        "profit after tax",
        "pat",
        "profit for the year",
        "net profit",
        "net profit attributable to owners",
        "profit attributable to equity holders",
        "net income",
    ],
    FIELD_PBT: [
        "profit before tax",
        "pbt",
        "profit before taxation",
    ],
    FIELD_EBITDA: [
        "ebitda",
        "earnings before interest tax depreciation amortization",
    ],
    FIELD_EBIT: [
        "ebit",
        "earnings before interest and tax",
        "profit before finance cost",
        "operating profit",
    ],
    FIELD_TOTAL_ASSETS: [
        "total assets",
        "assets",
    ],
    FIELD_CURRENT_ASSETS: [
        "current assets",
        "total current assets",
    ],
    FIELD_CASH: [
        "cash and cash equivalents",
        "cash and bank balances",
        "cash bank balance",
    ],
    FIELD_TOTAL_EQUITY: [
        "net worth",
        "total equity",
        "shareholders funds",
        "shareholders equity",
        "equity attributable to owners",
        "net assets",
    ],
    FIELD_TOTAL_LIABILITIES: [
        "total liabilities",
        "liabilities",
    ],
    FIELD_TOTAL_DEBT: [
        "total debt",
        "borrowings",
        "total borrowings",
        "debt",
        "borrowings other than debt securities",
    ],
    FIELD_INTEREST_EXPENSE: [
        "finance cost",
        "interest expense",
        "interest paid",
        "finance costs",
    ],
    FIELD_GNPA: [
        "gross npa",
        "gnpa",
        "gross non performing assets",
    ],
    FIELD_NET_NPA: [
        "net npa",
        "nnpa",
        "net non performing assets",
    ],
    FIELD_NPA: [
        "npa",
        "non performing assets",
    ],
    FIELD_CAR: [
        "capital adequacy ratio",
        "car",
        "crar",
    ],
    FIELD_COLLECTION_EFFICIENCY: [
        "collection efficiency",
    ],
    FIELD_AUM: [
        "assets under management",
        "aum",
    ],
    FIELD_LOAN_BOOK: [
        "loan book",
        "total loan book",
        "advances",
    ],
    FIELD_DISBURSEMENTS: [
        "disbursements",
        "total disbursements",
    ],
    FIELD_TIER1: [
        "tier 1 capital",
        "tier i capital",
    ],
    FIELD_WRITE_OFFS: [
        "write offs",
        "written off",
    ],
}

# ---------------------------------------------------------------------------
# Section classification keywords
# ---------------------------------------------------------------------------
SECTION_KEYWORDS: dict[str, list[str]] = {
    "balance_sheet": [
        "balance sheet",
        "statement of financial position",
        "assets and liabilities",
    ],
    "profit_and_loss": [
        "statement of profit and loss",
        "profit and loss",
        "income statement",
        "statement of comprehensive income",
    ],
    "cash_flow": [
        "cash flow statement",
        "statement of cash flows",
    ],
    "asset_quality": [
        "asset quality",
        "npa",
        "gnpa",
        "non performing",
        "provision coverage",
    ],
    "capital_adequacy": [
        "capital adequacy",
        "crar",
        "car",
        "regulatory capital",
    ],
    "borrowings": [
        "borrowings",
        "debt securities",
        "lender",
        "funding profile",
    ],
    "notes_to_accounts": [
        "notes to accounts",
        "notes forming part",
        "schedule",
    ],
    "management_discussion": [
        "management discussion",
        "md&a",
        "business review",
    ],
}

# Extraction thresholds
MIN_PDF_TEXT_LENGTH = 80
FUZZY_MATCH_THRESHOLD = 0.72
HIGH_CONFIDENCE = 0.90
MEDIUM_CONFIDENCE = 0.75
LOW_CONFIDENCE = 0.55

# Year column patterns (detect latest period)
YEAR_COLUMN_PATTERNS = [
    r"fy\s*'?(\d{2,4})",
    r"(\d{4})\s*[-–]\s*(\d{2,4})",
    r"31\s*mar(?:ch)?\s*(\d{4})",
    r"(\d{4})",
    r"current\s+year",
    r"previous\s+year",
]
