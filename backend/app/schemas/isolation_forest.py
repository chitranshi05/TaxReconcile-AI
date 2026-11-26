"""
backend/app/schemas/isolation_forest.py

Pydantic request / response schemas for the Isolation Forest anomaly
detection endpoint.
"""

from typing import Any
from pydantic import BaseModel, Field


class IsolationForestRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "List of raw transaction dicts. Each must contain at least "
            "'transaction_date' and an amount field ('amount', 'debit', or 'credit')."
        ),
    )
    contamination: float = Field(
        default=0.05,
        ge=0.01,
        le=0.50,
        description=(
            "Expected fraction of anomalies in the dataset (0.01 – 0.50). "
            "Default 0.05 means roughly 5 % of transactions are expected to be unusual."
        ),
    )
    n_estimators: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Number of Isolation Forest trees. Higher = more stable but slower.",
    )
    random_state: int = Field(
        default=42,
        description="Random seed for reproducibility.",
    )
    min_samples: int = Field(
        default=10,
        ge=5,
        le=1000,
        description="Minimum number of transactions required to train the model.",
    )


class MLModelParamsModel(BaseModel):
    algorithm: str
    contamination: float
    n_estimators: int
    random_state: int | None = None
    feature_names: list[str] | None = None
    min_samples_required: int | None = None
    actual_samples: int | None = None


class MLScoredTransactionModel(BaseModel):
    is_ml_anomaly: bool
    ml_anomaly_score: float | None = None
    ml_severity: str
    ml_flag: str | None = None
    ml_reason: str | None = None


class IsolationForestResponse(BaseModel):
    ml_available: bool
    status: str = Field(
        description="SUCCESS | INSUFFICIENT_DATA | UNAVAILABLE"
    )
    model_params: MLModelParamsModel | dict[str, Any]
    total_transactions: int
    anomalous_count: int
    normal_count: int
    anomaly_rate: float
    anomalies: list[dict[str, Any]]
    all_scored: list[dict[str, Any]]
    notes: list[str]
    disclaimer: str
