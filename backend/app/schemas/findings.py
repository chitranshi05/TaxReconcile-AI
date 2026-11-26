"""
backend/app/schemas/findings.py

Pydantic schemas for Unified Findings and Risk Scoring.
"""

from typing import Any
from pydantic import BaseModel, Field


class TransactionRiskScoreRequest(BaseModel):
    transaction: dict[str, Any] = Field(..., description="Transaction dictionary to score for financial and tax risk")


class TransactionRiskScoreResponse(BaseModel):
    risk_score: float = Field(..., description="Risk score from 0.0 to 100.0")
    risk_tier: str = Field(..., description="Risk tier: CRITICAL, HIGH, MEDIUM, LOW")
    components: dict[str, float] = Field(..., description="Breakdown across statutory, reconciliation, anomaly, and monetary dimensions")
    risk_factors: list[str] = Field(default_factory=list, description="Specific triggers elevating the risk score")
    audit_scrutiny_priority: str = Field(..., description="Audit priority: CRITICAL, HIGH, MEDIUM, LOW")


class ReconciliationRiskScoreRequest(BaseModel):
    summary: dict[str, Any] = Field(..., description="Reconciliation summary dictionary")
    matches: list[dict[str, Any]] = Field(default_factory=list)
    bank_only: list[dict[str, Any]] = Field(default_factory=list)
    ledger_only: list[dict[str, Any]] = Field(default_factory=list)


class ReconciliationRiskScoreResponse(BaseModel):
    overall_risk_score: float = Field(..., description="Aggregate reconciliation run risk score (0-100)")
    health_grade: str = Field(..., description="Audit readiness grade: A, B, C, D, F")
    risk_level: str = Field(..., description="Risk tier: CRITICAL, HIGH, MEDIUM, LOW")
    unreconciled_transactions_count: int
    unreconciled_ratio_pct: float
    net_financial_discrepancy: float
    risk_breakdown: dict[str, float]


class GenerateFindingsRequest(BaseModel):
    reconciliation_result: dict[str, Any] | None = None
    anomaly_result: dict[str, Any] | None = None
    tax_validation_findings: list[dict[str, Any]] | None = None


class FindingItemModel(BaseModel):
    finding_id: str
    category: str
    severity: str
    title: str
    description: str
    financial_impact: float
    statutory_reference: str | None = None
    source: str
    affected_records: list[Any] = Field(default_factory=list)
    remediation: str
    risk_score: float


class FindingsPortfolioSummaryModel(BaseModel):
    total_findings: int
    total_financial_impact: float
    critical_findings_count: int
    high_findings_count: int
    medium_findings_count: int
    low_findings_count: int
    average_risk_score: float
    overall_audit_status: str


class GenerateFindingsResponse(BaseModel):
    summary: FindingsPortfolioSummaryModel
    findings: list[FindingItemModel]

