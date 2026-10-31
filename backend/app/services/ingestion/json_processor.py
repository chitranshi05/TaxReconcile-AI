import json
from pathlib import Path

import pandas as pd

from app.services.ingestion.csv_processor import process_dataframe


SUPPORTED_FIELDS = {
    "date",
    "transaction_date",
    "value_date",
    "description",
    "narration",
    "particulars",
    "amount",
    "debit",
    "credit",
    "balance",
}


def process_json_file(file_path: str) -> dict:
    """Process JSON shaped as {\"transactions\": [{\"date\": ..., ...}]}."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("The uploaded file could not be found.")
    if path.suffix.lower() != ".json":
        raise ValueError("JSON processing supports .json files only.")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError(f"Unable to read JSON file: {error}") from error

    if not isinstance(data, dict) or set(data) != {"transactions"}:
        raise ValueError(
            'JSON must be an object containing only a "transactions" array.'
        )
    transactions = data["transactions"]
    if not isinstance(transactions, list):
        raise ValueError('"transactions" must be an array.')
    if not transactions:
        raise ValueError("The JSON contains no transaction rows.")
    if any(not isinstance(transaction, dict) for transaction in transactions):
        raise ValueError("Each transaction must be a JSON object.")

    for row_number, transaction in enumerate(transactions, start=2):
        unsupported_fields = set(transaction) - SUPPORTED_FIELDS
        if unsupported_fields:
            raise ValueError(
                f"Transaction at row {row_number} contains unsupported fields: "
                f"{', '.join(sorted(unsupported_fields))}."
            )
        if any(
            isinstance(value, (dict, list))
            for value in transaction.values()
        ):
            raise ValueError(
                f"Transaction at row {row_number} contains a non-scalar value."
            )

    return process_dataframe(pd.DataFrame(transactions))
