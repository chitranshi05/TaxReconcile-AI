from pydantic import BaseModel, Field


class ReconciliationRequest(BaseModel):
    bank_document_id: str = Field(..., description="ObjectId of the bank statement document")
    ledger_document_id: str = Field(..., description="ObjectId of the company ledger document")
    date_tolerance_days: int = Field(default=1, ge=0, le=30, description="Allowed date difference in days for potential matches")
    amount_tolerance: float = Field(default=0.0, ge=0.0, description="Allowed monetary difference for rounding discrepancies")
    fuzzy_threshold: float = Field(default=75.0, ge=0.0, le=100.0, description="Minimum description similarity score (0-100) for fuzzy matching")
    semantic_threshold: float = Field(default=70.0, ge=0.0, le=100.0, description="Minimum semantic description similarity score (0-100) for domain semantic matching")
