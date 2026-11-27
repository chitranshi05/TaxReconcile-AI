"""
backend/app/services/analysis/test_missing_income_detector.py

Unit tests for MissingIncomeDetector and missing income analysis.
"""

import unittest

from app.services.analysis.missing_income_detector import (
    MissingIncomeDetector,
    detect_missing_income,
)


def tx(tx_date: str, desc: str, credit: float | None = None, amount: float | None = None) -> dict:
    item = {"transaction_date": tx_date, "description": desc}
    if credit is not None:
        item["credit"] = credit
    if amount is not None:
        item["amount"] = amount
    return item


class TestMissingIncomeDetector(unittest.TestCase):
    def setUp(self):
        self.detector = MissingIncomeDetector()

    def test_empty_transactions_returns_clean_summary(self):
        res = self.detector.detect([])
        summary = res["summary"]
        self.assertEqual(summary["total_credit_transactions"], 0)
        self.assertEqual(summary["total_actual_income"], 0.0)
        self.assertEqual(summary["recurring_streams_count"], 0)
        self.assertEqual(summary["findings_count"], 0)

    def test_detects_monthly_salary_stream_without_gaps(self):
        """Monthly salary received every month without gaps."""
        transactions = [
            tx("2026-04-01", "Acme Corp Salary April", credit=85000.0),
            tx("2026-05-01", "Acme Corp Salary May", credit=85000.0),
            tx("2026-06-01", "Acme Corp Salary June", credit=85000.0),
        ]
        res = self.detector.detect(transactions)
        self.assertEqual(res["summary"]["recurring_streams_count"], 1)
        self.assertEqual(res["summary"]["missing_periodic_gaps_count"], 0)

        stream = res["recurring_streams"][0]
        self.assertEqual(stream["payer"], "ACME CORP")
        self.assertEqual(stream["category"], "SALARY")
        self.assertEqual(stream["periodicity"], "MONTHLY")
        self.assertEqual(stream["expected_amount"], 85000.0)
        self.assertEqual(stream["occurrences_count"], 3)

    def test_detects_missing_month_gap(self):
        """Salary received in April, May, July, August — June is missing!"""
        transactions = [
            tx("2026-04-01", "Infosys Technologies Salary April", credit=90000.0),
            tx("2026-05-01", "Infosys Technologies Salary May", credit=90000.0),
            # June is missing
            tx("2026-07-01", "Infosys Technologies Salary July", credit=90000.0),
            tx("2026-08-01", "Infosys Technologies Salary August", credit=90000.0),
        ]
        res = self.detector.detect(transactions)
        self.assertEqual(res["summary"]["missing_periodic_gaps_count"], 1)

        findings = res["findings"]
        missing_finding = [f for f in findings if f["finding_type"] == "MISSING_PERIODIC_INCOME"][0]
        self.assertEqual(missing_finding["expected_period"], "2026-06")
        self.assertEqual(missing_finding["expected_amount"], 90000.0)
        self.assertEqual(missing_finding["deficit_amount"], 90000.0)
        self.assertEqual(missing_finding["severity"], "HIGH")
        self.assertIn("missing for 2026-06", missing_finding["description"])

    def test_detects_underpaid_income_drop(self):
        """Rent received in April (40k), May (40k), June (15k) — June is underpaid."""
        transactions = [
            tx("2026-04-05", "Tenant Mr Sharma Rent", credit=40000.0),
            tx("2026-05-05", "Tenant Mr Sharma Rent", credit=40000.0),
            tx("2026-06-05", "Tenant Mr Sharma Rent", credit=15000.0),
        ]
        res = self.detector.detect(transactions, underpayment_ratio_threshold=0.70)
        self.assertEqual(res["summary"]["underpaid_income_count"], 1)

        finding = [f for f in res["findings"] if f["finding_type"] == "UNDERPAID_INCOME"][0]
        self.assertEqual(finding["expected_period"], "2026-06")
        self.assertEqual(finding["expected_amount"], 40000.0)
        self.assertEqual(finding["actual_amount"], 15000.0)
        self.assertEqual(finding["deficit_amount"], 25000.0)

    def test_detects_uncollected_ledger_income(self):
        """Ledger has accrued consulting revenue of 60,000, but no bank credit exists."""
        bank_txs = [
            tx("2026-04-10", "Client A Payment", credit=20000.0),
        ]
        ledger_txs = [
            tx("2026-04-15", "Consulting Fee Client B Accrued", credit=60000.0),
        ]
        res = self.detector.detect(bank_txs, ledger_transactions=ledger_txs, uncollected_tolerance_days=30)
        self.assertEqual(res["summary"]["uncollected_ledger_income_count"], 1)

        finding = [f for f in res["findings"] if f["finding_type"] == "UNCOLLECTED_ACCRUED_INCOME"][0]
        self.assertEqual(finding["expected_amount"], 60000.0)
        self.assertEqual(finding["actual_amount"], 0.0)
        self.assertIn("60,000", finding["description"])

    def test_as_of_date_extends_detection(self):
        """Statements end in May, but as_of_date is July -> flags missing June and July."""
        transactions = [
            tx("2026-03-01", "Consulting Retainer Client X", credit=50000.0),
            tx("2026-04-01", "Consulting Retainer Client X", credit=50000.0),
            tx("2026-05-01", "Consulting Retainer Client X", credit=50000.0),
        ]
        res = self.detector.detect(transactions, as_of_date="2026-07-15")
        gaps = [f for f in res["findings"] if f["finding_type"] == "MISSING_PERIODIC_INCOME"]
        missing_months = [g["expected_period"] for g in gaps]
        self.assertIn("2026-06", missing_months)
        self.assertIn("2026-07", missing_months)

    def test_single_or_irregular_transactions_not_treated_as_streams(self):
        """One-off payments from random persons are not turned into recurring streams."""
        transactions = [
            tx("2026-04-01", "Gift from Uncle", credit=5000.0),
            tx("2026-04-15", "Refund from Merchant", credit=1200.0),
        ]
        res = self.detector.detect(transactions)
        self.assertEqual(res["summary"]["recurring_streams_count"], 0)
        self.assertEqual(res["summary"]["findings_count"], 0)

    def test_convenience_function(self):
        transactions = [
            tx("2026-04-01", "Salary Employer Ltd", credit=70000.0),
            tx("2026-05-01", "Salary Employer Ltd", credit=70000.0),
            tx("2026-07-01", "Salary Employer Ltd", credit=70000.0),
        ]
        res = detect_missing_income(transactions)
        self.assertEqual(res["summary"]["missing_periodic_gaps_count"], 1)


if __name__ == "__main__":
    unittest.main()

