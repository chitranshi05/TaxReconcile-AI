"""
backend/app/schemas/tds_discrepancy.py

Pydantic schemas for the Advanced TDS Discrepancy Detection API.
"""

from typing import Any
from pydantic import BaseModel, Field


class TDSEntry26AS(BaseModel):
    """Represents a single TDS entry from Form 26AS / AIS / TIS."""
    deductor_name: str | None = None
    deductor_tan: str | None = None
    deductee_pan: str | None = None
    section: str | None = Field(default=None, description="TDS section e.g. '194A', '194J'")
    gross_amount: float | None = Field(default=None, description="Gross payment amount")
    tds_amount: float | None = Field(default=None, description="TDS deducted / reported in 26AS")
    transaction_date: str | None = Field(default=None, description="Date of credit/deduction (YYYY-MM-DD)")
    payment_date: str | None = Field(default=None, description="Date of original payment (for late-deduction check)")
    deposit_date: str | None = Field(default=None, description="Challan deposit date (for late-deposit check)")
    is_individual: bool = Field(default=True, description="Deductor is individual/HUF (affects 194C rate)")
    is_technical: bool = Field(default=False, description="Technical service fee (affects 194J rate)")
    source_row: int | None = None


class ExemptionCertificate(BaseModel):
    """Form 15G / 15H / Section 197 lower-deduction certificate."""
    deductee_pan: str = Field(..., description="PAN of deductee holding the certificate")
    section: str = Field(default="ALL", description="Section covered, or 'ALL'")
    certificate_type: str = Field(..., description="'15G', '15H', or '197'")
    approved_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Approved TDS rate (0 for 15G/15H)")
    valid_from: str | None = Field(default=None, description="Certificate validity start (YYYY-MM-DD)")
    valid_to: str | None = Field(default=None, description="Certificate validity end (YYYY-MM-DD)")


class ITRTDSScheduleEntry(BaseModel):
    """Single TDS entry from the ITR TDS schedule."""
    deductor_tan: str = Field(..., description="TAN of deductor as filed in ITR")
    tds_amount_claimed: float = Field(..., description="Amount claimed as TDS credit in ITR")
    transaction_date: str | None = Field(default=None, description="Date to determine quarter (YYYY-MM-DD)")
    quarter: int | None = Field(default=None, ge=1, le=4, description="FY quarter (1-4) if date not provided")


class AdvancedTDSAnalysisRequest(BaseModel):
    tds_entries_26as: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="TDS entries from Form 26AS / AIS. Each entry should include section, gross_amount, tds_amount.",
    )
    tds_entries_books: list[dict[str, Any]] | None = Field(
        default=None,
        description="TDS entries from company books/ledger (for quarter-wise reconciliation pass).",
    )
    exemption_certificates: list[dict[str, Any]] | None = Field(
        default=None,
        description="Form 15G/15H/197 certificates to check for incorrect TDS deduction.",
    )
    itr_tds_schedule: list[dict[str, Any]] | None = Field(
        default=None,
        description="TDS schedule from drafted/filed ITR to identify unclaimed credits.",
    )
    declared_income: dict[str, float] | None = Field(
        default=None,
        description="Declared income heads (e.g. {'salary': 1200000.0}).",
    )
    tax_liability: float | None = Field(
        default=None,
        ge=0.0,
        description="Total computed tax liability (used to identify excess TDS credit).",
    )
    financial_year: str = Field(
        default="2025-26",
        description="Financial year e.g. '2025-26', '2024-25'.",
    )
    tolerance: float = Field(
        default=100.0,
        ge=0.0,
        le=10000.0,
        description="Monetary tolerance for comparisons in ₹ (default ₹100).",
    )


class TDSFindingModel(BaseModel):
    rule_id: str
    category: str
    severity: str
    section: str | None = None
    title: str
    description: str
    details: dict[str, Any]
    remediation: str


class TDSAnalysisSummaryModel(BaseModel):
    financial_year: str
    tds_entries_analysed: int
    total_26as_tds_amount: float
    total_findings: int
    errors_count: int
    warnings_count: int
    info_count: int
    passes_run: list[str]
    findings_by_pass_counts: dict[str, int]


class AdvancedTDSAnalysisResponse(BaseModel):
    summary: TDSAnalysisSummaryModel
    findings: list[TDSFindingModel]
    findings_by_pass: dict[str, list[TDSFindingModel]]
    disclaimer: str

