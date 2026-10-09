COLUMN_ALIASES = {
    "date": [
        "date",
        "transaction date",
        "txn date",
        "transaction_date",
        "txn_date",
        "value date",
        "value_date"
    ],

    "description": [
        "description",
        "narration",
        "particulars",
        "transaction description",
        "transaction_details",
        "details",
        "remarks"
    ],

    "amount": [
        "amount",
        "transaction amount",
        "txn amount",
        "value"
    ],

    "debit": [
        "debit",
        "withdrawal",
        "withdrawals",
        "debit amount",
        "withdrawal amount"
    ],

    "credit": [
        "credit",
        "deposit",
        "deposits",
        "credit amount",
        "deposit amount"
    ],

    "type": [
        "type",
        "transaction type",
        "txn type",
        "transaction_type"
    ],

    "balance": [
        "balance",
        "closing balance",
        "available balance",
        "running balance"
    ],

    "entity": [
        "entity",
        "name",
        "company",
        "employer",
        "merchant",
        "payee",
        "payer"
    ],

    "tds": [
        "tds",
        "tds amount",
        "tax deducted",
        "tax deducted at source"
    ]
}


def normalize_column_name(column_name: str) -> str:
    return (
        str(column_name)
        .strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def detect_columns(columns: list[str]) -> dict:
    mapping = {}

    normalized_aliases = {}

    for standard_name, aliases in COLUMN_ALIASES.items():
        normalized_aliases[standard_name] = {
            normalize_column_name(alias)
            for alias in aliases
        }

    for column in columns:
        normalized_column = normalize_column_name(column)

        for standard_name, aliases in normalized_aliases.items():

            if normalized_column in aliases:
                mapping[standard_name] = column
                break

    return mapping