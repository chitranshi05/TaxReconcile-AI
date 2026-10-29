from typing import Any
from pydantic import BaseModel, Field


class AnomalyDetectionRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(
        ...,
        description="List of raw or normalized transaction objects to analyze for anomalies",
    )
    iqr_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="IQR multiplier for outlier boundary threshold (default 1.5)",
    )
    min_samples_for_iqr: int = Field(
        default=4,
        ge=3,
        description="Minimum sample size required to compute IQR boundaries",
    )
    frequency_threshold: int = Field(
        default=10,
        ge=2,
        description="Daily transaction count threshold for burst activity detection",
    )
    round_amount_min: float = Field(
        default=5000.0,
        ge=100.0,
        description="Minimum amount considered for repeated round figure pattern detection",
    )
    round_amount_min_occurrences: int = Field(
        default=2,
        ge=2,
        description="Minimum occurrences of a round figure to trigger review flag",
    )
    separate_debit_credit: bool = Field(
        default=True,
        description="Whether to analyze debit and credit distributions separately",
    )
