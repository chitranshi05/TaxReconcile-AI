"""
app/schemas/document.py

Pydantic response models for the documents API.

These models define the exact shape of JSON returned to the frontend.
Pydantic validates the output automatically when used as response_model.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentMetadataResponse(BaseModel):
    """
    Returned by:
      GET  /api/documents/         (one item in the list)
      GET  /api/documents/{id}     (single document fetch)
      DELETE /api/documents/{id}   (not used — delete returns a simple message)

    id           : MongoDB ObjectId as a string.
    filename     : The original filename the user uploaded (not the UUID-prefixed stored name).
    file_type    : CSV | XLSX | XLS | PDF | JSON
    document_type: Broad category (OTHER, BANK_STATEMENT, INVOICE, …)
    status       : UPLOADED | PENDING | PROCESSED | FAILED
    owner_id     : The owning user's MongoDB _id as a string.
    uploaded_at  : ISO-8601 UTC timestamp (None if missing for old records).
    """

    id: str
    filename: str
    file_type: str
    document_type: str
    status: str
    owner_id: str
    uploaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
