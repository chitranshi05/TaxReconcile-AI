"""
backend/app/api/test_findings_api.py

Unit tests for Findings and Risk Scoring API route handlers.
"""

import unittest
from bson import ObjectId

from app.api.findings import (
    calculate_reconciliation_run_risk,
    calculate_transaction_risk,
    generate_unified_findings,
)
from app.schemas.findings import (
    GenerateFindingsRequest,
    ReconciliationRiskScoreRequest,
    TransactionRiskScoreRequest,
)


class TestFindingsAPI(unittest.TestCase):
    def setUp(self):
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_score_transaction_endpoint(self):
        req = TransactionRiskScoreRequest(
            transaction={
                "amount": 250000.0,
                "transaction_date": "2026-04-01",
                "description": "Cash CDM Deposit",
                "status": "BANK_ONLY",
            }
        )
        res = calculate_transaction_risk(req, current_user=self.current_user)
        self.assertGreaterEqual(res["risk_score"], 50.0)
        self.assertIn("statutory_compliance", res["components"])
        self.assertIn(res["risk_tier"], ("HIGH", "CRITICAL"))

    def test_score_reconciliation_endpoint(self):
        req = ReconciliationRiskScoreRequest(
            summary={
                "total_bank_transactions": 20,
                "total_ledger_transactions": 20,
                "amount_mismatch_count": 2,
                "potential_match_count": 1,
                "total_bank_amount": 200000.0,
                "total_ledger_amount": 195000.0,
                "net_discrepancy": 5000.0,
            },
            bank_only=[{"amount": 1000.0}],
            ledger_only=[],
        )
        res = calculate_reconciliation_run_risk(req, current_user=self.current_user)
        self.assertIn("health_grade", res)
        self.assertIn("overall_risk_score", res)

    def test_generate_findings_endpoint(self):
        req = GenerateFindingsRequest(
            reconciliation_result={
                "matches": [
                    {
                        "status": "AMOUNT_MISMATCH",
                        "amount_variance": 500.0,
                        "bank_transaction": {"transaction_date": "2026-04-01", "amount": 5000.0},
                        "ledger_transaction": {"transaction_date": "2026-04-01", "amount": 4500.0},
                    }
                ],
                "bank_only": [],
                "ledger_only": [],
            }
        )
        res = generate_unified_findings(req, current_user=self.current_user)
        self.assertEqual(res["summary"]["total_findings"], 1)
        self.assertEqual(res["findings"][0]["category"], "RECONCILIATION_DISCREPANCY")


if __name__ == "__main__":
    unittest.main()
