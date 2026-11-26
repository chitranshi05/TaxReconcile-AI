from typing import Any
from pydantic import BaseModel, Field


class ClassifyTransactionRequest(BaseModel):
    description: str = Field(..., description="Transaction description/narration")
    amount: float | None = Field(default=None, description="Absolute transaction amount")
    debit: float | None = Field(default=None, description="Debit amount if applicable")
    credit: float | None = Field(default=None, description="Credit amount if applicable")


class TransactionClassificationResponse(BaseModel):
    category: str
    sub_category: str
    tax_head: str
    confidence_score: float
    is_tax_deductible: bool | None
    classification_reason: str


class ClassifyBatchRequest(BaseModel):
    transactions: list[ClassifyTransactionRequest] = Field(..., description="List of transactions to classify")


class CategoryMetric(BaseModel):
    count: int
    total_amount: float


class ClassificationSummaryResponse(BaseModel):
    total_transactions: int
    categorized_count: int
    uncategorized_count: int
    category_coverage_rate: float
    total_income: float
    total_deductible_expense: float
    total_non_deductible_expense: float
    category_breakdown: dict[str, CategoryMetric]
    tax_head_breakdown: dict[str, CategoryMetric]


class DocumentClassificationResponse(BaseModel):
    document_id: str
    summary: ClassificationSummaryResponse
    classified_transactions: list[dict[str, Any]]

