from typing import Any
from pydantic import BaseModel, Field


class TaxValidationRequest(BaseModel):
    financial_year: str = Field(
        default="2025-26",
        description="Indian Financial Year (e.g. '2025-26', '2024-25', '2023-24')",
    )
    is_senior_citizen: bool = Field(
        default=False,
        description="Whether the taxpayer is 60 years or older (qualifies for higher 80D/80TTB limits)",
    )
    declared_income: dict[str, float] | None = Field(
        default=None,
        description="Declared income heads (e.g. {'salary': 1200000.0, 'business_turnover': 2500000.0})",
    )
    claimed_deductions: dict[str, float] | None = Field(
        default=None,
        description="Claimed Chapter VI-A deductions (e.g. {'80c': 150000.0, '80d': 25000.0, '80ccd_1b': 50000.0})",
    )
    tds_entries: list[dict[str, Any]] | None = Field(
        default=None,
        description="TDS entries from Form 26AS/AIS/TIS to reconcile against financial records",
    )
    transactions: list[dict[str, Any]] | None = Field(
        default=None,
        description="Financial transactions / ledger records to audit",
    )
    custom_rules: dict[str, Any] | None = Field(
        default=None,
        description="Optional custom overrides for statutory rule thresholds",
    )


class DocumentTaxValidationRequest(BaseModel):
    financial_year: str = Field(
        default="2025-26",
        description="Indian Financial Year (e.g. '2025-26', '2024-25', '2023-24')",
    )
    is_senior_citizen: bool = Field(
        default=False,
        description="Whether the taxpayer is a senior citizen (60+ years)",
    )
    declared_income: dict[str, float] | None = Field(
        default=None,
        description="Declared income heads to cross-verify against document credits",
    )
    claimed_deductions: dict[str, float] | None = Field(
        default=None,
        description="Claimed deductions to validate against statutory caps and document debits",
    )
    tds_entries: list[dict[str, Any]] | None = Field(
        default=None,
        description="TDS entries from 26AS/AIS to reconcile against document records",
    )
    custom_rules: dict[str, Any] | None = Field(
        default=None,
        description="Optional custom threshold overrides",
    )
