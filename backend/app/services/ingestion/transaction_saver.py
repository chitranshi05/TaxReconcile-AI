
from app.database.mongodb import get_database
from app.models.transaction import create_transaction


def save_valid_transactions(
    document_id: str,
    owner_id: str,
    transactions: list[dict],
) -> int:
    """Save validated transactions for a document to MongoDB."""

    database = get_database()
    collection = database["transactions"]

    documents = [
        create_transaction(
            document_id=document_id,
            owner_id=owner_id,
            transaction_date=transaction["transaction_date"],
            description=transaction.get("description", ""),
            amount=transaction.get("amount"),
            debit=transaction.get("debit"),
            credit=transaction.get("credit"),
            balance=transaction.get("balance"),
            source_row=transaction.get("source_row"),
        )
        for transaction in transactions
    ]

    if not documents:
        return 0

    result = collection.insert_many(documents, ordered=True)
    return len(result.inserted_ids)
