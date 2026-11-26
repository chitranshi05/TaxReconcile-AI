"""
backend/app/services/analysis/test_risk_scorer.py

Unit tests for RiskScorer.
"""

import unittest
from app.services.analysis.risk_scorer import RiskScorer


class TestRiskScorer(unittest.TestCase):
    def test_clean_matched_transaction_low_risk(self):
        tx = {
            "amount": 5000.0,
            "transaction_date": "2026-04-01",
            "description": "Office Supplies",
            "status": "MATCHED",
            "is_anomaly": False,
        }
        res = RiskScorer.score_transaction(tx)
        self.assertLess(res["risk_score"], 25.0)
        self.assertEqual(res["risk_tier"], "LOW")
        self.assertEqual(res["audit_scrutiny_priority"], "LOW")

    def test_section_269st_cash_breach_high_risk(self):
        tx = {
            "amount": 250000.0,
            "transaction_date": "2026-04-05",
            "description": "Cash CDM Deposit",
            "status": "MATCHED",
        }
        res = RiskScorer.score_transaction(tx)
        self.assertGreaterEqual(res["risk_score"], 50.0)
        self.assertIn(res["risk_tier"], ("HIGH", "CRITICAL"))
        self.assertTrue(any("269ST" in f for f in res["risk_factors"]))

    def test_unexplained_bank_credit_risk(self):
        tx = {
            "amount": 100000.0,
            "credit": 100000.0,
            "transaction_date": "2026-04-10",
            "description": "Direct Transfer",
            "status": "BANK_ONLY",
        }
        res = RiskScorer.score_transaction(tx)
        self.assertGreaterEqual(res["risk_score"], 50.0)
        self.assertTrue(any("Section 68" in f for f in res["risk_factors"]))

    def test_amount_mismatch_variance_risk(self):
        tx = {
            "amount": 15000.0,
            "transaction_date": "2026-04-12",
            "description": "Vendor Fee",
            "status": "AMOUNT_MISMATCH",
            "amount_variance": 5000.0,
        }
        res = RiskScorer.score_transaction(tx)
        self.assertGreaterEqual(res["components"]["reconciliation_discrepancy"], 20.0)

    def test_anomaly_flags_elevate_score(self):
        tx = {
            "amount": 500000.0,
            "transaction_date": "2026-04-15",
            "description": "Round Transfer",
            "is_anomaly": True,
            "anomaly_flags": ["UNUSUALLY_LARGE_AMOUNT", "REPEATED_ROUND_AMOUNT"],
            "is_ml_anomaly": True,
            "ml_anomaly_score": 0.85,
        }
        res = RiskScorer.score_transaction(tx)
        self.assertGreaterEqual(res["components"]["anomaly_signals"], 20.0)

    def test_score_reconciliation_run(self):
        summary = {
            "total_bank_transactions": 10,
            "total_ledger_transactions": 10,
            "amount_mismatch_count": 2,
            "potential_match_count": 2,
            "total_bank_amount": 100000.0,
            "total_ledger_amount": 90000.0,
            "net_discrepancy": 10000.0,
        }
        bank_only = [{"amount": 5000.0}]
        ledger_only = [{"amount": 2000.0}]
        matches = []

        res = RiskScorer.score_reconciliation_run(
            summary=summary,
            matches=matches,
            bank_only=bank_only,
            ledger_only=ledger_only,
        )
        self.assertIn(res["health_grade"], ("B", "C", "D"))
        self.assertEqual(res["unreconciled_transactions_count"], 4)
        self.assertEqual(res["net_financial_discrepancy"], 10000.0)


if __name__ == "__main__":
    unittest.main()

