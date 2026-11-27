"""
backend/app/schemas/missing_income.py

Pydantic schemas for Missing Income Detection endpoints.
"""

from typing import Any
from pydantic import BaseModel, Field


class MissingIncomeRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of bank transaction dictionaries with transaction_date and credit/amount",
    )
    ledger_transactions: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional list of company ledger transaction dictionaries to check for uncollected income",
    )
    as_of_date: str | None = Field(
        default=None,
        description="Optional reference date (YYYY-MM-DD) to check up to the current period",
    )
    underpayment_ratio_threshold: float = Field(
        default=0.70,
        ge=0.1,
        le=1.0,
        description="Threshold below which an income occurrence is flagged as underpaid (default 70%)",
    )
    uncollected_tolerance_days: int = Field(
        default=30,
        ge=1,
        le=180,
        description="Grace period in days to find matching bank credit for ledger accrued revenue",
    )


class RecurringStreamModel(BaseModel):
    payer: str
    category: str
    periodicity: str
    expected_amount: float
    total_received: float
    occurrences_count: int
    first_date: str
    last_date: str
    active_months: list[str]


class MissingIncomeFindingModel(BaseModel):
    finding_type: str
    payer: str
    expected_period: str
    expected_amount: float
    actual_amount: float
    deficit_amount: float
    severity: str
    confidence_score: float
    description: str
    recommendation: str
    related_transaction: dict[str, Any] | None = None


class MissingIncomeSummaryModel(BaseModel):
    total_credit_transactions: int
    total_actual_income: float
    recurring_streams_count: int
    total_missing_income_amount: float
    findings_count: int
    missing_periodic_gaps_count: int
    underpaid_income_count: int
    uncollected_ledger_income_count: int


class MissingIncomeResponse(BaseModel):
    summary: MissingIncomeSummaryModel
    recurring_streams: list[RecurringStreamModel]
    findings: list[MissingIncomeFindingModel]


class DocumentMissingIncomeResponse(BaseModel):
    document_id: str
    summary: MissingIncomeSummaryModel
    recurring_streams: list[RecurringStreamModel]
    findings: list[MissingIncomeFindingModel]

