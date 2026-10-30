from pathlib import Path

import pandas as pd

from app.services.ingestion.column_mapper import detect_columns
from app.services.ingestion.data_validator import normalize_transactions


def process_dataframe(dataframe: pd.DataFrame) -> dict:
    dataframe = dataframe.copy()
    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    if any(not column for column in dataframe.columns):
        raise ValueError("The file contains an empty column name.")
    if dataframe.columns.duplicated().any():
        raise ValueError("The file contains duplicate column names.")
    if dataframe.empty:
        raise ValueError("The file contains no transaction rows.")

    mapping = detect_columns(list(dataframe.columns))
    normalized = normalize_transactions(dataframe, mapping)
    if any(error["row"] is None for error in normalized["errors"]):
        raise ValueError(normalized["errors"][0]["message"])

    return {
        "total_rows": len(dataframe),
        "valid_rows": len(normalized["transactions"]),
        "invalid_rows": len({
            error["row"]
            for error in normalized["errors"]
            if error["row"] is not None
        }),
        "column_mapping": mapping,
        "transactions": normalized["transactions"],
        "errors": normalized["errors"],
    }


def process_csv_file(file_path: str) -> dict:
    """Read, map, validate, and normalize a CSV transaction file."""
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise ValueError("The uploaded file could not be found.")
    if path.suffix.lower() != ".csv":
        raise ValueError("This processor currently supports CSV files only.")

    try:
        dataframe = pd.read_csv(path)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError) as exc:
        raise ValueError(f"Unable to read CSV file: {exc}") from exc

    return process_dataframe(dataframe)
