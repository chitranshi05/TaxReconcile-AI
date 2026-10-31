from pathlib import Path

import pandas as pd


def inspect_file(file_path: str):
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = path.suffix.lower()

    if extension == ".csv":

        try:
            dataframe = pd.read_csv(path)
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError, OSError) as error:
            raise ValueError(f"Unable to read CSV file: {error}") from error

        return [
            {
                "sheet_name": "csv",
                "rows": len(dataframe),
                "columns": [
                    str(column)
                    for column in dataframe.columns
                ],
                "sample": dataframe.head(5).fillna("").to_dict(
                    orient="records"
                )
            }
        ]

    if extension in [".xlsx", ".xls"]:

        try:
            sheets = pd.read_excel(
                path,
                sheet_name=None,
                engine="openpyxl" if extension == ".xlsx" else None,
            )
        except Exception as error:
            raise ValueError(f"Unable to read Excel workbook: {error}") from error

        result = []

        for sheet_name, dataframe in sheets.items():

            result.append(
                {
                    "sheet_name": str(sheet_name),
                    "rows": len(dataframe),
                    "columns": [
                        str(column)
                        for column in dataframe.columns
                    ],
                    "sample": dataframe.head(5).fillna("").to_dict(
                        orient="records"
                    )
                }
            )

        return result

    raise ValueError(
        f"Unsupported file type: {extension}"
    )