"""
backend/app/schemas/explainability.py

Pydantic schemas for Explainability requests and responses.
"""

from typing import Any
from pydantic import BaseModel, Field


class TransactionExplainRequest(BaseModel):
    transaction: dict[str, Any] = Field(..., description="Transaction dictionary to explain")
    match_info: dict[str, Any] | None = Field(default=None, description="Optional associated reconciliation match record")
    context: dict[str, Any] | None = Field(default=None, description="Optional overall document or run context")


class MatchExplainRequest(BaseModel):
    match: dict[str, Any] = Field(..., description="Reconciliation match record containing bank_transaction and ledger_transaction")


class BatchExplainRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(..., min_length=1, description="List of transactions to explain")


class EvidenceItem(BaseModel):
    factor: str
    impact: str
    details: str


class ReconciliationExplanationModel(BaseModel):
    reconciliation_status: str
    match_type: str | None = None
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    why_not_exact_match: str | None = None


class AnomalyTriggerItem(BaseModel):
    detector: str
    flag: str
    explanation: str


class AnomalyExplanationModel(BaseModel):
    is_anomalous: bool
    severity: str
    summary: str
    triggers: list[AnomalyTriggerItem] = Field(default_factory=list)
    detailed_reasons: list[str] = Field(default_factory=list)


class ClassificationExplanationModel(BaseModel):
    category: str
    sub_category: str
    tax_head: str
    confidence: float
    is_tax_deductible: bool | None = None
    classification_reason: str
    deductibility_rationale: str


class RiskAssessmentModel(BaseModel):
    risk_level: str
    risk_factors: list[str] = Field(default_factory=list)
    relevant_statutory_sections: list[str] = Field(default_factory=list)
    audit_scrutiny_likelihood: str


class AuditTrailStep(BaseModel):
    step: str
    status: str
    observation: str


class TransactionExplanationResponse(BaseModel):
    transaction_id: str
    transaction_date: str
    description: str
    amount: float
    primary_status: str
    headline: str
    reconciliation: ReconciliationExplanationModel
    anomaly: AnomalyExplanationModel
    classification: ClassificationExplanationModel
    risk_assessment: RiskAssessmentModel
    audit_trail: list[AuditTrailStep]


class MatchExplanationResponse(BaseModel):
    status: str
    match_type: str
    confidence_score: float
    confidence_level: str
    decision_recommendation: str
    reconciliation_summary: str
    key_matching_factors: list[str]
    bank_summary: dict[str, Any]
    ledger_summary: dict[str, Any]


class BatchExplainResponse(BaseModel):
    total_explained: int
    summary_by_status: dict[str, int]
    summary_by_risk: dict[str, int]
    explanations: list[TransactionExplanationResponse]

