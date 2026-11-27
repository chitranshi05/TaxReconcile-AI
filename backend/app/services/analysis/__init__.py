"""
Analysis package containing financial intelligence modules:
- Missing Income Detection
- Risk Scoring
- Explainability
"""

from app.services.analysis.missing_income_detector import (
    MissingIncomeDetector,
    detect_missing_income,
    RecurringIncomeStream,
    MissingIncomeFinding,
)

__all__ = [
    "MissingIncomeDetector",
    "detect_missing_income",
    "RecurringIncomeStream",
    "MissingIncomeFinding",
]

