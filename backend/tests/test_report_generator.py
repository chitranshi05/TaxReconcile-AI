from io import BytesIO

from openpyxl import load_workbook

from app.services.reconciliation.report_generator import (
    generate_reconciliation_xlsx,
)


def test_xlsx_report_stores_monetary_strings_as_numbers():
    record = {
        "summary": {
            "total_bank_amount": "₹1,234.50",
            "total_ledger_amount": "1,234.50",
            "matched_amount": "1234.5",
            "net_discrepancy": "(0.00)",
        },
        "matches": [
            {
                "bank_transaction": {"amount": "₹1,234.50"},
                "ledger_transaction": {"amount": "1,234.50"},
                "amount_variance": "0.00",
            }
        ],
        "bank_only": [{"amount": "-250.00", "debit": "250.00"}],
        "ledger_only": [{"amount": "(75.25)", "credit": "75.25"}],
    }

    workbook = load_workbook(BytesIO(generate_reconciliation_xlsx(record)))
    summary = workbook["Summary"]
    matches = workbook["Matches"]
    bank_only = workbook["Bank only"]
    ledger_only = workbook["Ledger only"]

    assert summary["B5"].value == 1234.5
    assert summary["B5"].data_type == "n"
    assert matches["E2"].value == 1234.5
    assert matches["H2"].value == 1234.5
    assert matches["I2"].value == 0
    assert bank_only["C2"].value == -250
    assert bank_only["D2"].value == 250
    assert ledger_only["C2"].value == -75.25
    assert ledger_only["E2"].value == 75.25
