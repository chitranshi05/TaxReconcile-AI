
import pandas as pd

from app.services.ingestion.data_validator import validate_transactions


data = {
    "Transaction Date": [
        "01-04-2026",
        "invalid-date",
        "03-04-2026",
        "04-04-2026"
    ],
    "Narration": [
        "Salary",
        "Shopping",
        "",
        "Interest"
    ],
    "Withdrawal": [
        0,
        1500,
        "invalid-amount",
        0
    ],
    "Deposit": [
        50000,
        0,
        0,
        1200
    ],
    "Closing Balance": [
        50000,
        48500,
        48500,
        49700
    ]
}

dataframe = pd.DataFrame(data)

column_mapping = {
    "date": "Transaction Date",
    "description": "Narration",
    "debit": "Withdrawal",
    "credit": "Deposit",
    "balance": "Closing Balance"
}

result = validate_transactions(dataframe, column_mapping)

print("Validation result:")
print(result)
