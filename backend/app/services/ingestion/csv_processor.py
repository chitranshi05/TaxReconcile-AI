
from pathlib import Path
import pandas as pd

from app.services.ingestion.column_mapper import detect_columns


def process_csv_file(file_path: str) -> dict:
    """
    Read a CSV financial statement, map its columns,
    normalize transaction values, and validate every row.

    This function does not write to MongoDB yet.
    """

    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise ValueError("The uploaded file could not be found.")

    if path.suffix.lower() != ".csv":
        raise ValueError("This processor currently supports CSV files only.")

    try:
        dataframe = pd.read_csv(path)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError) as exc:
        raise ValueError(f"Unable to read CSV file: {exc}") from exc

    if dataframe.empty:
        raise ValueError("The CSV file contains no transaction rows.")

    # Clean header whitespace while preserving the original data.
    dataframe.columns = [
        str(column).strip() for column in dataframe.columns
    ]

    if any(not column for column in dataframe.columns):
        raise ValueError("The CSV contains an empty column name.")

    if dataframe.columns.duplicated().any():
        raise ValueError("The CSV contains duplicate column names.")

    mapping = detect_columns(list(dataframe.columns))

    if not isinstance(mapping, dict):
        raise ValueError("Column mapping returned an invalid result.")

    # Require a date and at least one usable financial value.
    if "date" not in mapping:
        raise ValueError(
            "Could not identify a transaction date column."
        )

    if not any(
        field in mapping for field in ("amount", "debit", "credit")
    ):
        raise ValueError(
            "Could not identify an amount, debit, or credit column."
        )

    def parse_number(value):
        """Parse common financial number formats safely."""
        if pd.isna(value) or str(value).strip() == "":
            return None

        text = str(value).strip()
        negative = text.startswith("(") and text.endswith(")")

        if negative:
            text = text[1:-1].strip()

        # Support common currency symbols and thousands separators.
        for symbol in ("₹", "$", "€", "£", ","):
            text = text.replace(symbol, "")

        text = text.replace(" ", "")

        try:
            number = float(text)
        except (TypeError, ValueError):
            return None

        if not pd.notna(number):
            return None

        return -abs(number) if negative else number

    transactions = []
    errors = []

    for index, (_, source_row) in enumerate(
        dataframe.iterrows(), start=2
    ):
        # CSV row 1 is the header; data starts at row 2.
        raw_date = source_row.get(mapping["date"])
        parsed_date = pd.to_datetime(raw_date, errors="coerce")

        if pd.isna(parsed_date):
            errors.append({
                "row": index,
                "field": "date",
                "message": "Missing or invalid transaction date."
            })
            continue

        description_column = mapping.get("description")
        description = (
            str(source_row.get(description_column, "")).strip()
            if description_column else ""
        )

        amount = None
        debit = None
        credit = None

        if "amount" in mapping:
            amount = parse_number(source_row.get(mapping["amount"]))

        if "debit" in mapping:
            debit = parse_number(source_row.get(mapping["debit"]))

        if "credit" in mapping:
            credit = parse_number(source_row.get(mapping["credit"]))

        # Missing or malformed monetary values are rejected.
        present_values = [
            value for value in (amount, debit, credit)
            if value is not None
        ]

        if not present_values:
            errors.append({
                "row": index,
                "field": "amount",
                "message": "Missing or invalid transaction amount."
            })
            continue

        if any(value < 0 for value in (debit, credit)
               if value is not None):
            errors.append({
                "row": index,
                "field": "debit/credit",
                "message": "Debit and credit values must be non-negative."
            })
            continue

        # Reject rows where both debit and credit are positive.
        if debit is not None and credit is not None:
            if debit > 0 and credit > 0:
                errors.append({
                    "row": index,
                    "field": "debit/credit",
                    "message": (
                        "Both debit and credit are positive; "
                        "the row needs review."
                    )
                })
                continue

        # Preserve separate debit and credit values.
        # When an amount column is present, retain its source value.
        transaction = {
            "transaction_date": parsed_date.to_pydatetime(),
            "description": description,
            "amount": amount,
            "debit": debit,
            "credit": credit,
            "source_row": index,
        }

        if "balance" in mapping:
            transaction["balance"] = parse_number(
                source_row.get(mapping["balance"])
            )

        transactions.append(transaction)

    return {
        "total_rows": len(dataframe),
        "valid_rows": len(transactions),
        "invalid_rows": len(errors),
        "column_mapping": mapping,
        "transactions": transactions,
        "errors": errors,
    }
