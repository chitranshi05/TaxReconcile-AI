from pydantic import BaseModel, Field


class ReconciliationRequest(BaseModel):
    bank_document_id: str = Field(..., description="ObjectId of the bank statement document")
    ledger_document_id: str = Field(..., description="ObjectId of the company ledger document")
    date_tolerance_days: int = Field(default=1, ge=0, le=30, description="Allowed date difference in days for potential matches")
    amount_tolerance: float = Field(default=0.0, ge=0.0, description="Allowed monetary difference for rounding discrepancies")
