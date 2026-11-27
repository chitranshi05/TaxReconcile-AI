from pathlib import Path

import pandas as pd

from app.services.ingestion.csv_processor import process_dataframe


def process_excel_file(file_path: str) -> dict:
    """Process the first worksheet in an .xlsx workbook."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("The uploaded file could not be found.")
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Excel processing currently supports .xlsx files only.")

    try:
        dataframe = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception as error:
        raise ValueError(f"Unable to read Excel workbook: {error}") from error

    return process_dataframe(dataframe)
