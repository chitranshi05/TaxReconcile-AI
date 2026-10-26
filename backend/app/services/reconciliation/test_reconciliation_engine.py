import unittest
from app.services.reconciliation.reconciliation_engine import (
    reconcile_transactions,
)


class TestReconciliationEngine(unittest.TestCase):

    def test_exact_match(self):
        """₹50,000, same date and matching description -> MATCHED."""
        bank = [
            {
                "transaction_date": "2026-04-01",
                "description": "Salary Deposit",
                "amount": 50000.0,
                "source_row": 2,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-01",
                "description": "Salary",
                "amount": 50000.0,
                "source_row": 5,
            }
        ]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["potential_match_count"], 0)
        self.assertEqual(summary["amount_mismatch_count"], 0)
        self.assertEqual(summary["bank_only_count"], 0)
        self.assertEqual(summary["ledger_only_count"], 0)

        match = result["matches"][0]
        self.assertEqual(match["status"], "MATCHED")
        self.assertEqual(match["amount_variance"], 0.0)
        self.assertEqual(match["date_difference_days"], 0)

    def test_bank_only_and_ledger_only(self):
        """₹25,000 in bank only -> BANK_ONLY; ₹12,000 in ledger only -> LEDGER_ONLY."""
        bank = [
            {
                "transaction_date": "2026-04-05",
                "description": "Interest Credit",
                "amount": 25000.0,
                "source_row": 2,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-06",
                "description": "Consulting Fee",
                "amount": 12000.0,
                "source_row": 8,
            }
        ]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(summary["bank_only_count"], 1)
        self.assertEqual(summary["ledger_only_count"], 1)

        self.assertEqual(result["bank_only"][0]["status"], "BANK_ONLY")
        self.assertEqual(result["bank_only"][0]["amount"], 25000.0)
        self.assertEqual(result["ledger_only"][0]["status"], "LEDGER_ONLY")
        self.assertEqual(result["ledger_only"][0]["amount"], 12000.0)

    def test_amount_mismatch(self):
        """₹10,000 in bank vs ₹9,500 in ledger with matching date & description -> AMOUNT_MISMATCH."""
        bank = [
            {
                "transaction_date": "2026-04-10",
                "description": "Office Supplies",
                "amount": 10000.0,
                "source_row": 2,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-10",
                "description": "Office Supplies",
                "amount": 9500.0,
                "source_row": 3,
            }
        ]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["amount_mismatch_count"], 1)
        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(summary["bank_only_count"], 0)
        self.assertEqual(summary["ledger_only_count"], 0)

        match = result["matches"][0]
        self.assertEqual(match["status"], "AMOUNT_MISMATCH")
        self.assertEqual(match["amount_variance"], 500.0)

    def test_date_tolerance_potential_match(self):
        """₹20,000 dates differ by 1 day -> POTENTIAL_MATCH when date tolerance >= 1."""
        bank = [
            {
                "transaction_date": "2026-04-15",
                "description": "Client Payment",
                "amount": 20000.0,
                "source_row": 2,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-16",
                "description": "Client Payment",
                "amount": 20000.0,
                "source_row": 4,
            }
        ]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=1)
        summary = result["summary"]

        self.assertEqual(summary["potential_match_count"], 1)
        self.assertEqual(summary["matched_count"], 0)

        match = result["matches"][0]
        self.assertEqual(match["status"], "POTENTIAL_MATCH")
        self.assertEqual(match["date_difference_days"], 1)
        self.assertEqual(match["amount_variance"], 0.0)

    def test_date_exceeding_tolerance(self):
        """Dates differing by more than allowed tolerance remain unmatched."""
        bank = [
            {
                "transaction_date": "2026-04-01",
                "description": "Rent",
                "amount": 30000.0,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-10",
                "description": "Rent",
                "amount": 30000.0,
            }
        ]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=1)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(summary["potential_match_count"], 0)
        self.assertEqual(summary["bank_only_count"], 1)
        self.assertEqual(summary["ledger_only_count"], 1)

    def test_duplicate_candidates(self):
        """One bank entry with ₹1,000 matches exactly one ledger entry; remaining ledger entry stays LEDGER_ONLY."""
        bank = [
            {
                "transaction_date": "2026-04-20",
                "description": "Stationery",
                "amount": 1000.0,
            }
        ]
        ledger = [
            {
                "transaction_date": "2026-04-20",
                "description": "Stationery",
                "amount": 1000.0,
            },
            {
                "transaction_date": "2026-04-20",
                "description": "Stationery",
                "amount": 1000.0,
            },
        ]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["bank_only_count"], 0)
        self.assertEqual(summary["ledger_only_count"], 1)

    def test_empty_inputs(self):
        """Edge case: empty inputs handle safely."""
        result = reconcile_transactions([], [])
        summary = result["summary"]

        self.assertEqual(summary["total_bank_transactions"], 0)
        self.assertEqual(summary["total_ledger_transactions"], 0)
        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(len(result["matches"]), 0)


if __name__ == "__main__":
    unittest.main()
