"""
tests/test_ingestion.py

Unit tests for the ingestion pipeline:
  - column_mapper.detect_columns
  - data_validator.validate_transactions
  - inspector.inspect_file (CSV)

These tests do NOT require a database or running server — they test
pure Python functions in isolation.
"""

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from app.services.ingestion.column_mapper import detect_columns, normalize_column_name
from app.services.ingestion.data_validator import validate_transactions
from app.services.ingestion.inspector import inspect_file


# ── normalize_column_name ─────────────────────────────────────────────────────

def test_normalize_strips_and_lowercases():
    assert normalize_column_name("  Transaction Date  ") == "transaction date"


def test_normalize_replaces_underscores():
    assert normalize_column_name("txn_date") == "txn date"


def test_normalize_replaces_hyphens():
    assert normalize_column_name("txn-date") == "txn date"


# ── detect_columns ────────────────────────────────────────────────────────────

def test_detect_standard_bank_statement_columns():
    """Standard bank statement headers should all be detected."""
    columns = ["Transaction Date", "Narration", "Withdrawal", "Deposit", "Closing Balance"]
    mapping = detect_columns(columns)

    assert mapping.get("date") == "Transaction Date"
    assert mapping.get("description") == "Narration"
    assert mapping.get("debit") == "Withdrawal"
    assert mapping.get("credit") == "Deposit"
    assert mapping.get("balance") == "Closing Balance"


def test_detect_amount_column():
    columns = ["Date", "Details", "Amount"]
    mapping = detect_columns(columns)
    assert mapping.get("amount") == "Amount"


def test_detect_tds_column():
    columns = ["Date", "TDS Amount"]
    mapping = detect_columns(columns)
    assert mapping.get("tds") == "TDS Amount"


def test_detect_unknown_columns_ignored():
    """Columns with no matching alias should not appear in the mapping."""
    columns = ["FooBar", "Baz"]
    mapping = detect_columns(columns)
    assert mapping == {}


def test_detect_case_insensitive():
    """Column detection is case-insensitive."""
    columns = ["TRANSACTION DATE", "NARRATION", "AMOUNT"]
    mapping = detect_columns(columns)
    assert mapping.get("date") == "TRANSACTION DATE"
    assert mapping.get("description") == "NARRATION"
    assert mapping.get("amount") == "AMOUNT"


# ── validate_transactions ─────────────────────────────────────────────────────

def make_df(data: dict) -> pd.DataFrame:
    return pd.DataFrame(data)


def test_validate_empty_dataframe():
    """Empty dataframe returns valid=False with an explanatory error."""
    result = validate_transactions(pd.DataFrame(), {})
    assert result["valid"] is False
    assert result["total_rows"] == 0


def test_validate_no_date_column_in_mapping():
    """If column_mapping has no 'date' key, validation reports an error."""
    df = make_df({"Amount": [100, 200]})
    result = validate_transactions(df, {"amount": "Amount"})
    assert result["valid"] is False
    # Should contain a schema-level error about date
    assert any(e["field"] == "date" for e in result["errors"])


def test_validate_valid_rows():
    """All valid rows → valid=True, no errors."""
    df = make_df({
        "Date": ["01-04-2026", "02-04-2026"],
        "Amount": ["1000", "2500"],
    })
    mapping = {"date": "Date", "amount": "Amount"}
    result = validate_transactions(df, mapping)

    assert result["valid"] is True
    assert result["total_rows"] == 2
    assert result["valid_rows"] == 2
    assert result["invalid_rows"] == 0
    assert result["errors"] == []


def test_validate_catches_missing_date():
    df = make_df({
        "Date": ["", "02-04-2026"],
        "Amount": ["1000", "2500"],
    })
    mapping = {"date": "Date", "amount": "Amount"}
    result = validate_transactions(df, mapping)

    assert result["valid"] is False
    date_errors = [e for e in result["errors"] if e["field"] == "date"]
    assert len(date_errors) == 1


def test_validate_catches_invalid_date():
    df = make_df({
        "Date": ["not-a-date", "02-04-2026"],
        "Amount": ["1000", "2500"],
    })
    mapping = {"date": "Date", "amount": "Amount"}
    result = validate_transactions(df, mapping)

    assert result["valid"] is False
    date_errors = [e for e in result["errors"] if e["field"] == "date"]
    assert len(date_errors) >= 1


def test_validate_catches_non_numeric_amount():
    df = make_df({
        "Date": ["01-04-2026", "02-04-2026"],
        "Amount": ["1000", "abc"],
    })
    mapping = {"date": "Date", "amount": "Amount"}
    result = validate_transactions(df, mapping)

    assert result["valid"] is False
    amount_errors = [e for e in result["errors"] if e["field"] == "amount"]
    assert len(amount_errors) == 1


def test_validate_debit_credit_columns():
    """Debit/credit split columns are also validated."""
    df = make_df({
        "Date": ["01-04-2026", "02-04-2026"],
        "Debit": [0, "bad"],
        "Credit": [5000, 0],
    })
    mapping = {"date": "Date", "debit": "Debit", "credit": "Credit"}
    result = validate_transactions(df, mapping)

    assert result["valid"] is False
    assert any(e["field"] == "debit" for e in result["errors"])


def test_validate_rupee_symbol_in_amount():
    """₹ symbol in amount values should be stripped and parsed correctly."""
    df = make_df({
        "Date": ["01-04-2026"],
        "Amount": ["₹1,500.00"],
    })
    mapping = {"date": "Date", "amount": "Amount"}
    result = validate_transactions(df, mapping)
    assert result["valid"] is True


def test_validate_missing_description_is_warning_not_error():
    """Missing description is a warning, not a validation error."""
    df = make_df({
        "Date": ["01-04-2026"],
        "Description": [""],
        "Amount": ["1000"],
    })
    mapping = {"date": "Date", "description": "Description", "amount": "Amount"}
    result = validate_transactions(df, mapping)

    # Valid because only description is missing (a warning, not an error)
    assert result["valid"] is True
    assert any(w["field"] == "description" for w in result["warnings"])


# ── inspect_file ──────────────────────────────────────────────────────────────

def test_inspect_csv_file(tmp_path):
    """inspect_file returns one sheet entry for a CSV."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("Date,Narration,Amount\n01-04-2026,Salary,50000\n")

    result = inspect_file(str(csv_file))

    assert len(result) == 1
    sheet = result[0]
    assert sheet["sheet_name"] == "csv"
    assert "Date" in sheet["columns"]
    assert "Amount" in sheet["columns"]
    assert sheet["rows"] == 1
    assert len(sheet["sample"]) == 1


def test_inspect_unsupported_file_raises(tmp_path):
    """inspect_file raises ValueError for unsupported extensions."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("hello")

    with pytest.raises(ValueError, match="Unsupported"):
        inspect_file(str(txt_file))


def test_inspect_missing_file_raises(tmp_path):
    """inspect_file raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        inspect_file(str(tmp_path / "missing.csv"))
