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

        dataframe = pd.read_csv(path)

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

        sheets = pd.read_excel(
            path,
            sheet_name=None
        )

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