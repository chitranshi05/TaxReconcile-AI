"""
backend/app/api/test_explainability_api.py

Unit tests for Explainability API route handlers.
"""

import unittest
from bson import ObjectId

from app.api.explainability import (
    explain_batch,
    explain_match,
    explain_transaction,
)
from app.schemas.explainability import (
    BatchExplainRequest,
    MatchExplainRequest,
    TransactionExplainRequest,
)


class TestExplainabilityAPI(unittest.TestCase):
    def setUp(self):
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_explain_transaction_endpoint(self):
        req = TransactionExplainRequest(
            transaction={
                "transaction_date": "2026-04-01",
                "description": "Salary Deposit",
                "amount": 75000.0,
                "status": "MATCHED",
                "match_type": "EXACT_MATCH",
                "category": "SALARY",
                "tax_head": "INCOME_FROM_SALARY",
            }
        )
        res = explain_transaction(req, current_user=self.current_user)
        self.assertEqual(res["primary_status"], "MATCHED")
        self.assertEqual(res["reconciliation"]["reconciliation_status"], "MATCHED")
        self.assertEqual(len(res["audit_trail"]), 5)

    def test_explain_match_endpoint(self):
        req = MatchExplainRequest(
            match={
                "status": "MATCHED",
                "match_type": "EXACT_MATCH",
                "confidence_score": 1.0,
                "confidence_level": "VERY_HIGH",
                "decision_recommendation": "AUTO_APPROVE",
                "notes": "Exact match on date, normalized description, and amount.",
                "bank_transaction": {
                    "transaction_date": "2026-04-01",
                    "description": "Salary",
                    "amount": 50000.0,
                },
                "ledger_transaction": {
                    "transaction_date": "2026-04-01",
                    "description": "Salary",
                    "amount": 50000.0,
                },
            }
        )
        res = explain_match(req, current_user=self.current_user)
        self.assertEqual(res["status"], "MATCHED")
        self.assertEqual(res["match_type"], "EXACT_MATCH")
        self.assertEqual(res["confidence_score"], 1.0)
        self.assertGreaterEqual(len(res["key_matching_factors"]), 2)

    def test_explain_batch_endpoint(self):
        req = BatchExplainRequest(
            transactions=[
                {
                    "transaction_date": "2026-04-01",
                    "description": "Salary",
                    "amount": 50000.0,
                    "status": "MATCHED",
                },
                {
                    "transaction_date": "2026-04-05",
                    "description": "ATM Cash Withdrawal",
                    "amount": 250000.0,
                    "status": "BANK_ONLY",
                },
            ]
        )
        res = explain_batch(req, current_user=self.current_user)
        self.assertEqual(res["total_explained"], 2)
        self.assertIn("MATCHED", res["summary_by_status"])
        self.assertIn("BANK_ONLY", res["summary_by_status"])
        self.assertEqual(len(res["explanations"]), 2)


if __name__ == "__main__":
    unittest.main()
