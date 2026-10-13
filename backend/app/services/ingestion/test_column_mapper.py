from app.services.ingestion.column_mapper import detect_columns


columns = [
    "Transaction Date",
    "Narration",
    "Withdrawal",
    "Deposit",
    "Closing Balance"
]


result = detect_columns(columns)

print("Detected column mapping:")
print(result)