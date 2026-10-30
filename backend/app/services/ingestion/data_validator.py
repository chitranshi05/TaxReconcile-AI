import math

import pandas as pd


def _parse_number(value):
    if pd.isna(value) or str(value).strip() == "":
        return None, None

    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()

    for symbol in ("₹", "$", "€", "£", ","):
        text = text.replace(symbol, "")
    text = text.replace(" ", "")

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None, "Value is not numeric."

    if not math.isfinite(number):
        return None, "Value must be finite."

    return (-abs(number) if negative else number), None


def _parse_date(value):
    if not isinstance(value, (str, int, float)) and not hasattr(value, "to_pydatetime"):
        return None
    try:
        return pd.to_datetime(value, errors="coerce", dayfirst=True)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_transactions(
    dataframe: pd.DataFrame,
    column_mapping: dict,
    row_number_offset: int = 2,
) -> dict:
    """Validate and normalize transaction rows using the extraction rules."""
    errors = []
    transactions = []
    date_column = column_mapping.get("date")
    money_columns = {
        field: column_mapping.get(field)
        for field in ("amount", "debit", "credit")
    }

    if dataframe.empty:
        return {
            "transactions": [],
            "errors": [{
                "row": None,
                "field": None,
                "message": "The file contains no transaction rows.",
            }],
        }

    if not date_column:
        errors.append({
            "row": None,
            "field": "date",
            "message": "Could not identify a transaction date column.",
        })

    if not any(money_columns.values()):
        errors.append({
            "row": None,
            "field": "amount",
            "message": "Could not identify an amount, debit, or credit column.",
        })

    if errors:
        return {"transactions": [], "errors": errors}

    description_column = column_mapping.get("description")
    balance_column = column_mapping.get("balance")

    for row_index, (_, row) in enumerate(dataframe.iterrows()):
        row_number = row_index + row_number_offset
        row_errors = []
        raw_date = row.get(date_column)
        parsed_date = _parse_date(raw_date)

        if pd.isna(raw_date) or str(raw_date).strip() == "":
            row_errors.append({
                "row": row_number,
                "field": "date",
                "message": "Transaction date is missing.",
            })
        elif pd.isna(parsed_date):
            row_errors.append({
                "row": row_number,
                "field": "date",
                "message": "Transaction date is invalid.",
            })

        values = {}
        for field, column in money_columns.items():
            if not column:
                values[field] = None
                continue
            values[field], parse_error = _parse_number(row.get(column))
            if parse_error:
                row_errors.append({
                    "row": row_number,
                    "field": field,
                    "message": parse_error,
                })

        present_values = [
            value for value in values.values() if value is not None
        ]
        if not present_values and not any(
            error["field"] in money_columns for error in row_errors
        ):
            row_errors.append({
                "row": row_number,
                "field": "amount",
                "message": "Missing or invalid transaction amount.",
            })

        debit = values["debit"]
        credit = values["credit"]
        if debit is not None and debit < 0:
            row_errors.append({
                "row": row_number,
                "field": "debit",
                "message": "Debit values must be non-negative.",
            })
        if credit is not None and credit < 0:
            row_errors.append({
                "row": row_number,
                "field": "credit",
                "message": "Credit values must be non-negative.",
            })
        if debit is not None and credit is not None and debit > 0 and credit > 0:
            row_errors.append({
                "row": row_number,
                "field": "debit/credit",
                "message": (
                    "Both debit and credit are positive; the row needs review."
                ),
            })

        if row_errors:
            errors.extend(row_errors)
            continue

        description = row.get(description_column, "") if description_column else ""
        transaction = {
            "transaction_date": parsed_date.to_pydatetime(),
            "description": "" if pd.isna(description) else str(description).strip(),
            "amount": values["amount"],
            "debit": debit,
            "credit": credit,
            "source_row": row_number,
        }
        if balance_column:
            transaction["balance"], balance_error = _parse_number(
                row.get(balance_column)
            )
            if balance_error:
                errors.append({
                    "row": row_number,
                    "field": "balance",
                    "message": balance_error,
                })
                continue
        transactions.append(transaction)

    return {"transactions": transactions, "errors": errors}


def validate_transactions(
    dataframe: pd.DataFrame,
    column_mapping: dict
) -> dict:
    """Validate extracted transaction data without modifying the dataframe."""
    normalized = normalize_transactions(dataframe, column_mapping)
    errors = normalized["errors"]
    invalid_row_numbers = {
        error["row"] for error in errors if error["row"] is not None
    }
    schema_invalid = any(error["row"] is None for error in errors)
    invalid_rows = len(dataframe) if schema_invalid else len(invalid_row_numbers)

    warnings = []
    description_column = column_mapping.get("description")
    if not description_column:
        warnings.append({
            "row": None,
            "field": "description",
            "message": "No description column was identified.",
        })
    else:
        for index, value in enumerate(dataframe[description_column]):
            if pd.isna(value) or str(value).strip() == "":
                warnings.append({
                    "row": index + 2,
                    "field": "description",
                    "message": "Transaction description is missing.",
                })

    return {
        "valid": not errors,
        "total_rows": len(dataframe),
        "valid_rows": len(dataframe) - invalid_rows,
        "invalid_rows": invalid_rows,
        "errors": errors,
        "warnings": warnings,
    }
