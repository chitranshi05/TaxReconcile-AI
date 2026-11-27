import json

import pandas as pd
import pytest

from app.services.ingestion.excel_processor import process_excel_file
from app.services.ingestion.json_processor import process_json_file


def test_xlsx_processes_first_worksheet(tmp_path):
    workbook = tmp_path / "transactions.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            {"Date": ["2026-04-01"], "Amount": [125.5]}
        ).to_excel(writer, sheet_name="Transactions", index=False)
        pd.DataFrame(
            {"Date": ["2026-04-02"], "Amount": [500]}
        ).to_excel(writer, sheet_name="Ignored", index=False)

    result = process_excel_file(str(workbook))

    assert result["total_rows"] == 1
    assert result["valid_rows"] == 1
    assert result["transactions"][0]["amount"] == 125.5


def test_xlsx_empty_workbook_is_rejected(tmp_path):
    workbook = tmp_path / "empty.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame().to_excel(writer, index=False)

    with pytest.raises(ValueError, match="no transaction rows"):
        process_excel_file(str(workbook))


@pytest.mark.parametrize(
    "columns",
    [{"Description": ["Missing date and amount"]}],
)
def test_xlsx_missing_required_columns_is_rejected(tmp_path, columns):
    workbook = tmp_path / "invalid.xlsx"
    pd.DataFrame(columns).to_excel(workbook, index=False)

    with pytest.raises(ValueError, match="date|amount"):
        process_excel_file(str(workbook))


def test_xlsx_invalid_dates_and_amounts_are_reported(tmp_path):
    workbook = tmp_path / "invalid-values.xlsx"
    pd.DataFrame(
        {"Date": ["not-a-date"], "Amount": ["bad"]}
    ).to_excel(workbook, index=False)

    result = process_excel_file(str(workbook))

    assert result["valid_rows"] == 0
    assert result["invalid_rows"] == 1
    assert {error["field"] for error in result["errors"]} == {"date", "amount"}


def test_json_processes_documented_transaction_array(tmp_path):
    path = tmp_path / "transactions.json"
    path.write_text(
        json.dumps({
            "transactions": [
                {
                    "date": "2026-04-01",
                    "description": "Invoice",
                    "credit": 500,
                }
            ]
        }),
        encoding="utf-8",
    )

    result = process_json_file(str(path))

    assert result["valid_rows"] == 1
    assert result["transactions"][0]["credit"] == 500.0
    assert result["transactions"][0]["description"] == "Invoice"


def test_json_rejects_malformed_json(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to read JSON"):
        process_json_file(str(path))


def test_json_rejects_empty_transaction_array(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text('{"transactions": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="no transaction rows"):
        process_json_file(str(path))


def test_json_reports_missing_fields_and_invalid_values(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps({
            "transactions": [
                {"date": "2026-04-01"},
                {"date": "not-a-date", "amount": "invalid"},
            ]
        }),
        encoding="utf-8",
    )

    result = process_json_file(str(path))

    assert result["valid_rows"] == 0
    assert result["invalid_rows"] == 2
    assert {error["field"] for error in result["errors"]} == {
        "amount",
        "date",
    }


def test_json_rejects_non_scalar_transaction_values(tmp_path):
    path = tmp_path / "nested-value.json"
    path.write_text(
        '{"transactions": [{"date": {"unexpected": "object"}, "amount": 1}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-scalar"):
        process_json_file(str(path))


def test_json_rejects_unrecognized_top_level_shape(tmp_path):
    path = tmp_path / "unexpected.json"
    path.write_text('[{"date": "2026-04-01", "amount": 1}]', encoding="utf-8")

    with pytest.raises(ValueError, match='"transactions" array'):
        process_json_file(str(path))
