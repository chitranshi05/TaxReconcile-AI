import unittest
from datetime import datetime
from app.services.ingestion.duplicate_detector import (
    detect_duplicates,
    normalize_description,
    normalize_date,
    build_duplicate_signature,
)


class TestDuplicateDetector(unittest.TestCase):

    def test_exact_duplicates(self):
        """Test exact duplicate transactions with identical date, description, and amount."""
        transactions = [
            {
                "transaction_date": datetime(2026, 4, 1),
                "description": "Salary",
                "amount": 50000.0,
                "source_row": 2,
            },
            {
                "transaction_date": datetime(2026, 4, 1),
                "description": "Salary",
                "amount": 50000.0,
                "source_row": 3,
            },
            {
                "transaction_date": datetime(2026, 4, 3),
                "description": "Shopping",
                "amount": 2000.0,
                "source_row": 4,
            },
        ]

        result = detect_duplicates(transactions)

        self.assertEqual(result["total_transactions"], 3)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["original_count"], 1)
        self.assertEqual(result["unique_count"], 1)
        self.assertEqual(result["duplicate_groups_count"], 1)

        flagged = result["flagged_transactions"]

        # First salary transaction -> ORIGINAL
        self.assertEqual(flagged[0]["duplicate_status"], "ORIGINAL")
        self.assertFalse(flagged[0]["is_duplicate"])
        self.assertEqual(flagged[0]["duplicate_group_id"], "dup_group_1")

        # Second salary transaction -> POTENTIAL_DUPLICATE
        self.assertEqual(flagged[1]["duplicate_status"], "POTENTIAL_DUPLICATE")
        self.assertTrue(flagged[1]["is_duplicate"])
        self.assertEqual(flagged[1]["duplicate_group_id"], "dup_group_1")
        self.assertEqual(flagged[1]["duplicate_of_row"], 2)

        # Shopping transaction -> UNIQUE
        self.assertEqual(flagged[2]["duplicate_status"], "UNIQUE")
        self.assertFalse(flagged[2]["is_duplicate"])
        self.assertIsNone(flagged[2]["duplicate_group_id"])

    def test_similar_transactions_on_different_dates(self):
        """Recurring transactions with same description and amount on different dates are NOT duplicates."""
        transactions = [
            {
                "transaction_date": "2026-04-01",
                "description": "Netflix Subscription",
                "amount": 649.0,
                "source_row": 2,
            },
            {
                "transaction_date": "2026-05-01",
                "description": "Netflix Subscription",
                "amount": 649.0,
                "source_row": 15,
            },
        ]

        result = detect_duplicates(transactions)

        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result["unique_count"], 2)
        self.assertEqual(result["duplicate_groups_count"], 0)
        self.assertFalse(result["flagged_transactions"][0]["is_duplicate"])
        self.assertFalse(result["flagged_transactions"][1]["is_duplicate"])
        self.assertEqual(result["flagged_transactions"][0]["duplicate_status"], "UNIQUE")
        self.assertEqual(result["flagged_transactions"][1]["duplicate_status"], "UNIQUE")

    def test_description_normalization(self):
        """Case insensitivity and whitespace differences should still detect duplicates."""
        transactions = [
            {
                "transaction_date": "2026-04-05",
                "description": "  CAFE COFFEE DAY   ",
                "amount": 350.0,
                "source_row": 2,
            },
            {
                "transaction_date": "2026-04-05",
                "description": "cafe  coffee day",
                "amount": 350.0,
                "source_row": 3,
            },
        ]

        result = detect_duplicates(transactions)

        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["original_count"], 1)
        self.assertEqual(result["flagged_transactions"][0]["duplicate_status"], "ORIGINAL")
        self.assertEqual(result["flagged_transactions"][1]["duplicate_status"], "POTENTIAL_DUPLICATE")

    def test_debit_credit_duplicates(self):
        """Test duplicates using debit/credit columns instead of amount column."""
        transactions = [
            {
                "transaction_date": "2026-04-10",
                "description": "ATM Cash Withdrawal",
                "debit": 5000.0,
                "credit": 0.0,
                "source_row": 2,
            },
            {
                "transaction_date": "2026-04-10",
                "description": "ATM Cash Withdrawal",
                "debit": 5000.0,
                "credit": 0.0,
                "source_row": 3,
            },
            {
                "transaction_date": "2026-04-10",
                "description": "ATM Cash Withdrawal",
                "debit": 2000.0,
                "credit": 0.0,
                "source_row": 4,
            },
        ]

        result = detect_duplicates(transactions)

        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["original_count"], 1)
        self.assertEqual(result["unique_count"], 1)
        self.assertEqual(result["flagged_transactions"][0]["duplicate_status"], "ORIGINAL")
        self.assertEqual(result["flagged_transactions"][1]["duplicate_status"], "POTENTIAL_DUPLICATE")
        self.assertEqual(result["flagged_transactions"][2]["duplicate_status"], "UNIQUE")

    def test_empty_and_single_transaction(self):
        """Edge cases: empty list and single transaction."""
        empty_result = detect_duplicates([])
        self.assertEqual(empty_result["total_transactions"], 0)
        self.assertEqual(empty_result["duplicate_count"], 0)

        single_result = detect_duplicates([
            {
                "transaction_date": "2026-04-01",
                "description": "Grocery",
                "amount": 1200.0,
                "source_row": 2,
            }
        ])
        self.assertEqual(single_result["total_transactions"], 1)
        self.assertEqual(single_result["unique_count"], 1)
        self.assertEqual(single_result["duplicate_count"], 0)
        self.assertEqual(single_result["flagged_transactions"][0]["duplicate_status"], "UNIQUE")


if __name__ == "__main__":
    unittest.main()
