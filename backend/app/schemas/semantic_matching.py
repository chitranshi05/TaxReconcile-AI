"""
backend/app/schemas/semantic_matching.py

Pydantic schemas for Semantic Matching endpoints and requests.
"""

from typing import Any
from pydantic import BaseModel, Field


class SemanticSimilarityRequest(BaseModel):
    text1: str = Field(..., min_length=1, description="First transaction description / narration")
    text2: str = Field(..., min_length=1, description="Second transaction description / narration")
    semantic_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum score threshold (0-100) to classify as semantic match",
    )


class SemanticSimilarityResponse(BaseModel):
    text1: str
    text2: str
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 100.0)")
    is_match: bool = Field(..., description="Whether similarity meets or exceeds threshold")
    matched_concepts: list[str] = Field(default_factory=list, description="Shared accounting/banking domain concepts")
    method: str = Field(default="TF-IDF + Domain Synonyms", description="Matching technique used")


class SemanticCompareCandidate(BaseModel):
    candidate: str
    similarity_score: float
    is_match: bool
    matched_concepts: list[str] = Field(default_factory=list)


class SemanticBatchCompareRequest(BaseModel):
    reference_text: str = Field(..., min_length=1, description="Base description to compare against")
    candidates: list[str] = Field(..., min_length=1, description="List of candidate descriptions")
    semantic_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum score threshold (0-100) to classify as semantic match",
    )


class SemanticBatchCompareResponse(BaseModel):
    reference_text: str
    candidates_count: int
    matches_count: int
    results: list[SemanticCompareCandidate]
