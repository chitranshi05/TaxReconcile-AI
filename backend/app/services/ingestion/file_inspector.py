from pathlib import Path

import pandas as pd


def inspect_file(file_path: str):
    path = Path(file_path)

    extension = path.suffix.lower()

    if extension == ".csv":
        sheets = {
            "csv": pd.read_csv(path)
        }

    elif extension in [".xlsx", ".xls"]:
        sheets = pd.read_excel(path, sheet_name=None)

    else:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    result = []

    for sheet_name, dataframe in sheets.items():

        columns = [
            str(column)
            for column in dataframe.columns
        ]

        result.append(
            {
                "sheet_name": str(sheet_name),
                "rows": len(dataframe),
                "columns": columns,
                "sample": dataframe.head(5).fillna("").to_dict(
                    orient="records"
                )
            }
        )

    return result