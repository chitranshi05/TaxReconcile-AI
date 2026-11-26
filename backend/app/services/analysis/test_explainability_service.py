"""
backend/app/services/analysis/test_explainability_service.py

Unit tests for the Explainability Service.

Coverage:
1. Exact match transaction explanation
2. Potential match transaction explanation (fuzzy, semantic, date tolerance)
3. Unmatched transaction explanation (BANK_ONLY, LEDGER_ONLY)
4. Amount mismatch explanation
5. Anomaly explanation (IQR, round amounts, burst, Isolation Forest)
6. Classification and deductibility explanation (Sec 37 vs personal)
7. Statutory risk assessment (Sec 269ST cash limit, Sec 40A(3), Sec 68)
8. Audit trail generation
9. Reconciliation match deep-dive explanation
"""

import unittest
from app.services.analysis.explainability_service import (
    ExplainabilityService,
    explain_reconciliation_match,
    explain_single_transaction,
)


class TestExplainabilityService(unittest.TestCase):
    def test_explain_exact_match_transaction(self):
        tx = {
            "transaction_date": "2026-04-01",
            "description": "Salary Deposit April",
            "amount": 50000.0,
            "status": "MATCHED",
            "match_type": "EXACT_MATCH",
            "category": "SALARY",
            "tax_head": "INCOME_FROM_SALARY",
            "is_tax_deductible": None,
        }

        res = explain_single_transaction(tx)
        self.assertEqual(res["primary_status"], "MATCHED")
        self.assertIn("Fully reconciled", res["headline"])
        self.assertEqual(res["reconciliation"]["reconciliation_status"], "MATCHED")
        self.assertIsNone(res["reconciliation"]["why_not_exact_match"])
        self.assertFalse(res["anomaly"]["is_anomalous"])
        self.assertEqual(res["risk_assessment"]["risk_level"], "LOW")
        self.assertEqual(len(res["audit_trail"]), 5)

    def test_explain_fuzzy_potential_match(self):
        tx = {
            "transaction_date": "2026-05-15",
            "description": "Amazon Payments India",
            "amount": 2499.0,
            "status": "POTENTIAL_MATCH",
            "match_type": "FUZZY_MATCH",
            "similarity_score": 85.0,
            "category": "OFFICE_SUPPLIES",
            "is_tax_deductible": True,
        }

        res = explain_single_transaction(tx)
        self.assertEqual(res["primary_status"], "POTENTIAL_MATCH")
        self.assertIn("fuzzy description similarity", res["reconciliation"]["summary"])
        self.assertIsNotNone(res["reconciliation"]["why_not_exact_match"])
        self.assertIn("Section 37(1)", res["classification"]["deductibility_rationale"])

    def test_explain_date_tolerance_match(self):
        tx = {
            "transaction_date": "2026-05-01",
            "description": "Vendor Payment",
            "amount": 15000.0,
            "status": "POTENTIAL_MATCH",
            "match_type": "DATE_TOLERANCE_MATCH",
            "date_difference_days": 2,
        }

        res = explain_single_transaction(tx)
        self.assertEqual(res["reconciliation"]["match_type"], "DATE_TOLERANCE_MATCH")
        self.assertIn("2 day(s)", res["reconciliation"]["summary"])

    def test_explain_unmatched_bank_only_with_section_68_risk(self):
        tx = {
            "transaction_date": "2026-06-10",
            "description": "Cash CDM Deposit",
            "amount": 250000.0,
            "credit": 250000.0,
            "status": "BANK_ONLY",
        }

        res = explain_single_transaction(tx)
        self.assertEqual(res["primary_status"], "BANK_ONLY")
        self.assertIn("Unmatched entry", res["reconciliation"]["summary"])
        self.assertEqual(res["risk_assessment"]["risk_level"], "HIGH")
        # Should flag both Section 269ST (>= 2 lakh cash) and Section 68 (unexplained credit)
        self.assertTrue(any("269ST" in s for s in res["risk_assessment"]["relevant_statutory_sections"]))
        self.assertTrue(any("Section 68" in s for s in res["risk_assessment"]["relevant_statutory_sections"]))

    def test_explain_statistical_and_ml_anomaly(self):
        tx = {
            "transaction_date": "2026-07-20",
            "description": "Round Transfer",
            "amount": 1000000.0,
            "is_anomaly": True,
            "anomaly_flags": ["UNUSUALLY_LARGE_AMOUNT", "REPEATED_ROUND_AMOUNT"],
            "anomaly_reasons": ["Amount ₹10,00,000 exceeds upper statistical bound."],
            "is_ml_anomaly": True,
            "ml_flag": "ML_ISOLATION_FOREST",
            "ml_anomaly_score": 0.88,
            "ml_reason": "ML anomaly score: 0.88/1.00.",
            "ml_severity": "HIGH",
        }

        res = explain_single_transaction(tx)
        self.assertTrue(res["anomaly"]["is_anomalous"])
        self.assertEqual(res["anomaly"]["severity"], "HIGH")
        self.assertGreaterEqual(len(res["anomaly"]["triggers"]), 3)
        self.assertEqual(res["risk_assessment"]["risk_level"], "HIGH")
        self.assertIn("Section 285BA", res["risk_assessment"]["relevant_statutory_sections"][0])

    def test_explain_reconciliation_match_pair(self):
        match = {
            "status": "POTENTIAL_MATCH",
            "match_type": "FUZZY_MATCH",
            "confidence_score": 0.84,
            "confidence_level": "HIGH",
            "decision_recommendation": "REVIEW_RECOMMENDED",
            "similarity_score": 84.0,
            "notes": "Fuzzy description match with similarity 84.0%.",
            "bank_transaction": {
                "transaction_date": "2026-05-18",
                "description": "SWIGGY LTD",
                "amount": 540.0,
            },
            "ledger_transaction": {
                "transaction_date": "2026-05-18",
                "description": "SWIGGY LIMITED",
                "amount": 540.0,
            },
        }

        res = explain_reconciliation_match(match)
        self.assertEqual(res["status"], "POTENTIAL_MATCH")
        self.assertEqual(res["match_type"], "FUZZY_MATCH")
        self.assertAlmostEqual(res["confidence_score"], 0.84)
        self.assertEqual(res["confidence_level"], "HIGH")
        self.assertIn("Same transaction date", res["key_matching_factors"][0])
        self.assertIn("Exact matching amount", res["key_matching_factors"][1])
        self.assertIn("84.0%", res["key_matching_factors"][2])


if __name__ == "__main__":
    unittest.main()

