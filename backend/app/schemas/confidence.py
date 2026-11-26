"""
backend/app/schemas/confidence.py

Pydantic schemas for Confidence Scoring requests and responses.
"""

from typing import Any
from pydantic import BaseModel, Field


class MatchConfidenceEvaluationRequest(BaseModel):
    bank_transaction: dict[str, Any] = Field(..., description="Bank transaction dictionary")
    ledger_transaction: dict[str, Any] = Field(..., description="Ledger transaction dictionary")
    match_type: str = Field(default="EXACT_MATCH", description="Classification pass / match type")
    similarity_score: float | None = Field(default=None, ge=0.0, le=100.0, description="Description similarity (0-100)")
    date_difference_days: int = Field(default=0, ge=0, description="Difference in days between transaction dates")
    amount_variance: float = Field(default=0.0, description="Monetary difference between bank and ledger amounts")
    candidate_count: int = Field(default=1, ge=1, description="Number of ledger candidates competing for this bank entry")
    second_best_similarity: float | None = Field(default=None, ge=0.0, le=100.0, description="Similarity of alternative match candidate")
    date_tolerance_days: int = Field(default=1, ge=0, description="Configured allowed date difference")
    amount_tolerance: float = Field(default=0.0, ge=0.0, description="Configured allowed amount difference")


class ConfidenceComponentsModel(BaseModel):
    amount_score: float = Field(..., description="Amount agreement score (0.0 to 1.0)")
    date_score: float = Field(..., description="Date proximity score (0.0 to 1.0)")
    description_score: float = Field(..., description="Textual / semantic description score (0.0 to 1.0)")
    uniqueness_score: float = Field(..., description="Uniqueness / ambiguity penalty score (0.0 to 1.0)")


class MatchConfidenceResponse(BaseModel):
    confidence_score: float = Field(..., description="Calibrated confidence score between 0.0 and 1.0")
    confidence_level: str = Field(..., description="Tier: VERY_HIGH, HIGH, MEDIUM, LOW")
    decision_recommendation: str = Field(..., description="Action: AUTO_APPROVE, REVIEW_RECOMMENDED, MANUAL_INVESTIGATION_REQUIRED")
    components: ConfidenceComponentsModel
    positive_factors: list[str] = Field(default_factory=list, description="Positive signals strengthening the match")
    negative_factors: list[str] = Field(default_factory=list, description="Negative signals or risks undermining the match")


class BatchConfidenceEvaluationRequest(BaseModel):
    matches: list[dict[str, Any]] = Field(..., min_length=1, description="List of match objects to evaluate and enrich")
    date_tolerance_days: int = Field(default=1, ge=0)
    amount_tolerance: float = Field(default=0.0, ge=0.0)


class BatchConfidenceResponse(BaseModel):
    total_evaluated: int
    average_confidence: float
    confidence_distribution: dict[str, int]
    recommendations_summary: dict[str, int]
    enriched_matches: list[dict[str, Any]]

