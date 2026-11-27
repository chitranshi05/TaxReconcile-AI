import pandas as pd
import pytest

from app.services.ingestion.column_mapper import detect_columns
from app.services.ingestion.csv_processor import process_dataframe
from app.services.ingestion.data_validator import validate_transactions


@pytest.mark.parametrize(
    ("columns", "expected_valid"),
    [
        ({"Date": ["2026-04-01"], "Debit": [100]}, True),
        ({"Date": ["2026-04-01"], "Credit": [100]}, True),
        ({"Date": ["2026-04-01"], "Debit": [None], "Credit": [None]}, False),
        ({"Date": ["2026-04-01"], "Amount": ["invalid"]}, False),
        ({"Date": [None], "Amount": [100]}, False),
        ({"Date": ["not-a-date"], "Amount": [100]}, False),
        (
            {
                "Date": ["2026-04-01"],
                "Debit": [100],
                "Credit": [None],
            },
            True,
        ),
        (
            {
                "Date": ["2026-04-01"],
                "Debit": [0],
                "Credit": [None],
            },
            True,
        ),
        (
            {
                "Date": ["2026-04-01"],
                "Debit": [100],
                "Credit": [50],
            },
            False,
        ),
    ],
)
def test_preview_and_extraction_share_transaction_validation(
    columns, expected_valid
):
    dataframe = pd.DataFrame(columns)
    mapping = detect_columns(list(dataframe.columns))
    preview = validate_transactions(dataframe, mapping)
    processed = process_dataframe(dataframe)

    assert preview["valid"] is expected_valid
    assert (processed["valid_rows"] == 1) is expected_valid
    assert processed["invalid_rows"] == (0 if expected_valid else 1)


def test_processing_rejects_missing_required_columns():
    dataframe = pd.DataFrame({"Description": ["Missing date and amount"]})
    mapping = detect_columns(list(dataframe.columns))

    with pytest.raises(ValueError, match="transaction date column"):
        process_dataframe(dataframe)
