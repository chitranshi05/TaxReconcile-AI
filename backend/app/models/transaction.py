from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def create_transaction(
    document_id: str,
    owner_id: str,
    transaction_date: datetime,
    description: str = "",
    amount: float | None = None,
    debit: float | None = None,
    credit: float | None = None,
    balance: float | None = None,
    source_row: int | None = None,
) -> dict[str, Any]:
    """Create a normalized transaction document for MongoDB."""

    return {
        "transaction_id": str(uuid4()),
        "document_id": document_id,
        "owner_id": owner_id,
        "transaction_date": transaction_date,
        "description": description,
        "amount": amount,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "source_row": source_row,
        "created_at": datetime.now(timezone.utc),
    }
