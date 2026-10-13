
from datetime import datetime
import math

import pandas as pd


def validate_transactions(
    dataframe: pd.DataFrame,
    column_mapping: dict
) -> dict:
    """
    Validate extracted transaction data without modifying
    the original dataframe.
    """

    errors = []
    warnings = []

    if dataframe.empty:
        return {
            "valid": False,
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "errors": [
                {
                    "row": None,
                    "field": None,
                    "message": "The file contains no transaction rows."
                }
            ],
            "warnings": []
        }

    date_column = column_mapping.get("date")
    description_column = column_mapping.get("description")
    amount_column = column_mapping.get("amount")
    debit_column = column_mapping.get("debit")
    credit_column = column_mapping.get("credit")

    has_amount = bool(amount_column)
    has_debit_credit = bool(debit_column and credit_column)

    if not date_column:
        errors.append({
            "row": None,
            "field": "date",
            "message": "Could not identify a transaction date column."
        })

    if not has_amount and not has_debit_credit:
        errors.append({
            "row": None,
            "field": "amount",
            "message": (
                "Could not identify an amount column or both "
                "debit and credit columns."
            )
        })

    if not description_column:
        warnings.append({
            "row": None,
            "field": "description",
            "message": "No description column was identified."
        })

    invalid_row_numbers = set()

    for index, row in dataframe.iterrows():
        row_number = int(index) + 2

        # Validate transaction date.
        if date_column:
            value = row.get(date_column)

            if pd.isna(value) or str(value).strip() == "":
                errors.append({
                    "row": row_number,
                    "field": "date",
                    "message": "Transaction date is missing."
                })
                invalid_row_numbers.add(index)
            else:
                parsed_date = pd.to_datetime(
                    value,
                    errors="coerce",
                    dayfirst=True
                )

                if pd.isna(parsed_date):
                    errors.append({
                        "row": row_number,
                        "field": "date",
                        "message": "Transaction date is invalid."
                    })
                    invalid_row_numbers.add(index)

        # Validate description when available.
        if description_column:
            value = row.get(description_column)

            if pd.isna(value) or str(value).strip() == "":
                warnings.append({
                    "row": row_number,
                    "field": "description",
                    "message": "Transaction description is missing."
                })

        # Validate a single amount column.
        if has_amount:
            value = row.get(amount_column)

            if pd.isna(value) or str(value).strip() == "":
                errors.append({
                    "row": row_number,
                    "field": "amount",
                    "message": "Transaction amount is missing."
                })
                invalid_row_numbers.add(index)
            else:
                try:
                    amount = float(
                        str(value).replace(",", "").replace("₹", "").strip()
                    )

                    if not math.isfinite(amount):
                        raise ValueError("Amount must be finite.")

                    if amount < 0:
                        warnings.append({
                            "row": row_number,
                            "field": "amount",
                            "message": (
                                "Negative amount found; verify the "
                                "source's debit/credit convention."
                            )
                        })

                except (ValueError, TypeError):
                    errors.append({
                        "row": row_number,
                        "field": "amount",
                        "message": "Transaction amount is not numeric."
                    })
                    invalid_row_numbers.add(index)

        # Validate debit and credit columns when present.
        elif has_debit_credit:
            for field, column in (
                ("debit", debit_column),
                ("credit", credit_column)
            ):
                value = row.get(column)

                if pd.isna(value) or str(value).strip() == "":
                    continue

                try:
                    amount = float(
                        str(value).replace(",", "").replace("₹", "").strip()
                    )

                    if not math.isfinite(amount):
                        raise ValueError("Amount must be finite.")

                    if amount < 0:
                        warnings.append({
                            "row": row_number,
                            "field": field,
                            "message": (
                                "Negative value found; verify the "
                                "source's debit/credit convention."
                            )
                        })

                except (ValueError, TypeError):
                    errors.append({
                        "row": row_number,
                        "field": field,
                        "message": f"{field.title()} amount is not numeric."
                    })
                    invalid_row_numbers.add(index)

    invalid_rows = len(invalid_row_numbers)

    return {
        "valid": len(errors) == 0,
        "total_rows": len(dataframe),
        "valid_rows": len(dataframe) - invalid_rows,
        "invalid_rows": invalid_rows,
        "errors": errors,
        "warnings": warnings
    }
