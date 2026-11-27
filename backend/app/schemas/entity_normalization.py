from pydantic import BaseModel, Field


class NormalizeDescriptionRequest(BaseModel):
    description: str = Field(..., description="Raw transaction narration/description to normalize")


class NormalizedEntityResponse(BaseModel):
    raw_description: str
    clean_description: str
    normalized_entity: str
    channel: str
    reference_id: str | None = None
    counterparty_type: str
    vpa: str | None = None


class DocumentEntitiesResponse(BaseModel):
    document_id: str
    transaction_count: int
    entities: list[NormalizedEntityResponse]

