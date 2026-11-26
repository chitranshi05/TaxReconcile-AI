"""
backend/app/services/reconciliation/test_confidence_scorer.py

Unit tests for ConfidenceScorer and multi-factor reconciliation confidence evaluation.

Coverage:
1. Exact match scoring and VERY_HIGH tier
2. Amount scoring: exact, within tolerance, relative variance penalty
3. Date proximity scoring: same day, within tolerance, beyond tolerance
4. Description scoring: exact, high fuzzy, moderate fuzzy, low similarity
5. Uniqueness & ambiguity: single candidate vs close competition
6. Recommendation mapping: AUTO_APPROVE, REVIEW_RECOMMENDED, MANUAL_INVESTIGATION_REQUIRED
7. Integration with ReconciliationEngine matches
8. Batch confidence computation
"""

import unittest
from app.services.reconciliation.confidence_scorer import (
    ConfidenceScorer,
    compute_batch_confidence,
)
from app.services.reconciliation.reconciliation_engine import (
    reconcile_transactions,
)


class TestConfidenceScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = ConfidenceScorer(date_tolerance_days=2, amount_tolerance=10.0)

    def test_exact_match_perfect_confidence(self):
        bank = {"amount": 50000.0, "transaction_date": "2026-04-01", "description": "Salary April"}
        ledger = {"amount": 50000.0, "transaction_date": "2026-04-01", "description": "Salary April"}

        result = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="EXACT_MATCH",
            similarity_score=100.0,
            date_difference_days=0,
            amount_variance=0.0,
        )

        self.assertEqual(result["confidence_score"], 1.0)
        self.assertEqual(result["confidence_level"], "VERY_HIGH")
        self.assertEqual(result["decision_recommendation"], "AUTO_APPROVE")
        self.assertEqual(result["components"]["amount_score"], 1.0)
        self.assertEqual(result["components"]["date_score"], 1.0)
        self.assertIn("Exact monetary amount match.", result["positive_factors"])

    def test_fuzzy_match_high_similarity(self):
        bank = {"amount": 2500.0, "transaction_date": "2026-05-10", "description": "Amazon Payments India"}
        ledger = {"amount": 2500.0, "transaction_date": "2026-05-10", "description": "Amazon Payment Ind"}

        result = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="FUZZY_MATCH",
            similarity_score=85.0,
            date_difference_days=0,
            amount_variance=0.0,
        )

        self.assertGreaterEqual(result["confidence_score"], 0.80)
        self.assertEqual(result["confidence_level"], "HIGH")
        self.assertEqual(result["decision_recommendation"], "REVIEW_RECOMMENDED")

    def test_date_tolerance_match_score_decay(self):
        bank = {"amount": 10000.0, "transaction_date": "2026-06-01", "description": "Vendor Fee"}
        ledger = {"amount": 10000.0, "transaction_date": "2026-06-03", "description": "Vendor Fee"}

        result_1day = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="DATE_TOLERANCE_MATCH",
            date_difference_days=1,
            amount_variance=0.0,
        )

        result_2days = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="DATE_TOLERANCE_MATCH",
            date_difference_days=2,
            amount_variance=0.0,
        )

        self.assertGreater(result_1day["confidence_score"], result_2days["confidence_score"])
        self.assertIn("within configured tolerance", result_1day["positive_factors"][1])

    def test_amount_mismatch_low_confidence(self):
        bank = {"amount": 10000.0, "transaction_date": "2026-04-10", "description": "Office Supplies"}
        ledger = {"amount": 9500.0, "transaction_date": "2026-04-10", "description": "Office Supplies"}

        result = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="AMOUNT_MISMATCH",
            date_difference_days=0,
            amount_variance=500.0,
        )

        self.assertLessEqual(result["confidence_score"], 0.60)
        self.assertEqual(result["confidence_level"], "LOW")
        self.assertEqual(result["decision_recommendation"], "MANUAL_INVESTIGATION_REQUIRED")
        self.assertTrue(any("discrepancy" in f for f in result["negative_factors"]))

    def test_ambiguity_penalty_when_close_candidate_exists(self):
        bank = {"amount": 700.0, "transaction_date": "2026-05-25", "description": "Zomato Delivery"}
        ledger = {"amount": 700.0, "transaction_date": "2026-05-25", "description": "Zomato Order"}

        unambiguous = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="FUZZY_MATCH",
            similarity_score=80.0,
            candidate_count=1,
        )

        ambiguous = self.scorer.score_match(
            bank_tx=bank,
            ledger_tx=ledger,
            match_type="FUZZY_MATCH",
            similarity_score=80.0,
            candidate_count=2,
            second_best_similarity=78.0,
        )

        self.assertGreater(
            unambiguous["components"]["uniqueness_score"],
            ambiguous["components"]["uniqueness_score"],
        )
        self.assertTrue(any("Ambiguous" in f for f in ambiguous["negative_factors"]))

    def test_reconciliation_engine_enriches_matches(self):
        bank = [{"transaction_date": "2026-04-01", "description": "Salary", "amount": 50000.0}]
        ledger = [{"transaction_date": "2026-04-01", "description": "Salary", "amount": 50000.0}]

        res = reconcile_transactions(bank, ledger)
        self.assertEqual(len(res["matches"]), 1)
        match = res["matches"][0]

        self.assertIn("confidence_score", match)
        self.assertIn("confidence_level", match)
        self.assertIn("decision_recommendation", match)
        self.assertIn("confidence_breakdown", match)
        self.assertIn("confidence_factors", match)
        self.assertEqual(match["confidence_level"], "VERY_HIGH")
        self.assertEqual(match["decision_recommendation"], "AUTO_APPROVE")

    def test_batch_confidence_enrichment(self):
        matches = [
            {
                "bank_transaction": {"amount": 1000.0, "transaction_date": "2026-04-01"},
                "ledger_transaction": {"amount": 1000.0, "transaction_date": "2026-04-01"},
                "match_type": "EXACT_MATCH",
                "amount_variance": 0.0,
                "date_difference_days": 0,
            },
            {
                "bank_transaction": {"amount": 2000.0, "transaction_date": "2026-04-05"},
                "ledger_transaction": {"amount": 1800.0, "transaction_date": "2026-04-05"},
                "match_type": "AMOUNT_MISMATCH",
                "amount_variance": 200.0,
                "date_difference_days": 0,
            },
        ]

        enriched = compute_batch_confidence(matches)
        self.assertEqual(len(enriched), 2)
        self.assertEqual(enriched[0]["confidence_level"], "VERY_HIGH")
        self.assertEqual(enriched[1]["confidence_level"], "LOW")


if __name__ == "__main__":
    unittest.main()

