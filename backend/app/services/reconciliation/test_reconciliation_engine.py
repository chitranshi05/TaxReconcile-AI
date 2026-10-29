"""
Comprehensive unit tests for the Bank vs Ledger Reconciliation Engine.

Test Coverage:
    1. Exact Match Detection
    2. Date-Tolerance Matching (POTENTIAL_MATCH)
    3. Amount Mismatch Detection
    4. Unmatched Bank Transactions (BANK_ONLY)
    5. Unmatched Ledger Transactions (LEDGER_ONLY)
    6. Reconciliation Summary Statistics
    7. Edge Cases and Robustness
"""
import unittest
from datetime import date

from app.services.reconciliation.reconciliation_engine import (
    ReconciliationEngine,
    reconcile_transactions,
    normalize_date_to_date,
    normalize_description,
    descriptions_match,
    extract_amount,
    extract_absolute_amount,
)


# ---------------------------------------------------------------------------
# Helper builder
# ---------------------------------------------------------------------------
def tx(
    date_str: str,
    description: str,
    amount: float | None = None,
    debit: float | None = None,
    credit: float | None = None,
    source_row: int = 1,
) -> dict:
    """Convenience factory for transaction dicts."""
    d: dict = {"transaction_date": date_str, "description": description, "source_row": source_row}
    if amount is not None:
        d["amount"] = amount
    if debit is not None:
        d["debit"] = debit
    if credit is not None:
        d["credit"] = credit
    return d


# ===========================================================================
# Unit tests for helper functions
# ===========================================================================
class TestNormalizeDateToDate(unittest.TestCase):
    def test_iso_string(self):
        self.assertEqual(normalize_date_to_date("2026-04-01"), date(2026, 4, 1))

    def test_dayfirst_string(self):
        self.assertEqual(normalize_date_to_date("01/04/2026"), date(2026, 4, 1))

    def test_datetime_object(self):
        from datetime import datetime
        self.assertEqual(normalize_date_to_date(datetime(2026, 4, 1, 12, 0)), date(2026, 4, 1))

    def test_date_object(self):
        self.assertEqual(normalize_date_to_date(date(2026, 4, 1)), date(2026, 4, 1))

    def test_none_returns_none(self):
        self.assertIsNone(normalize_date_to_date(None))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(normalize_date_to_date("not-a-date"))


class TestNormalizeDescription(unittest.TestCase):
    def test_lowercases_and_strips(self):
        self.assertEqual(normalize_description("  Salary  "), "salary")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_description("Office   Supplies"), "office supplies")

    def test_none_returns_empty(self):
        self.assertEqual(normalize_description(None), "")

    def test_empty_string(self):
        self.assertEqual(normalize_description(""), "")


class TestDescriptionsMatch(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(descriptions_match("salary", "salary"))

    def test_one_contains_other(self):
        self.assertTrue(descriptions_match("salary deposit", "salary"))

    def test_high_token_overlap(self):
        self.assertTrue(descriptions_match("office supplies payment", "office supplies"))

    def test_completely_different(self):
        self.assertFalse(descriptions_match("rent payment", "insurance premium"))

    def test_empty_desc_passes(self):
        # Missing description should not block matching
        self.assertTrue(descriptions_match("", "salary"))


class TestExtractAmount(unittest.TestCase):
    def test_explicit_amount(self):
        self.assertEqual(extract_amount({"amount": 1000.0}), 1000.0)

    def test_debit_only(self):
        self.assertEqual(extract_amount({"debit": 500.0}), -500.0)

    def test_credit_only(self):
        self.assertEqual(extract_amount({"credit": 750.0}), 750.0)

    def test_debit_and_credit(self):
        self.assertEqual(extract_amount({"debit": 200.0, "credit": 500.0}), 300.0)

    def test_no_amount_returns_none(self):
        self.assertIsNone(extract_amount({}))

    def test_absolute_amount(self):
        self.assertEqual(extract_absolute_amount({"debit": 500.0}), 500.0)
        self.assertEqual(extract_absolute_amount({"amount": -300.0}), 300.0)


# ===========================================================================
# Feature 1: Exact Match Detection
# ===========================================================================
class TestExactMatchDetection(unittest.TestCase):
    """Transactions appearing in both records with matching amounts and dates."""

    def test_simple_exact_match(self):
        """Same date, description, amount → MATCHED / EXACT_MATCH."""
        bank = [tx("2026-04-01", "Salary Deposit", amount=50000.0)]
        ledger = [tx("2026-04-01", "Salary", amount=50000.0)]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["bank_only_count"], 0)
        self.assertEqual(summary["ledger_only_count"], 0)
        self.assertEqual(result["matches"][0]["match_type"], "EXACT_MATCH")
        self.assertEqual(result["matches"][0]["confidence_score"], 1.0)
        self.assertEqual(result["matches"][0]["date_difference_days"], 0)
        self.assertEqual(result["matches"][0]["amount_variance"], 0.0)

    def test_exact_match_debit_credit_fields(self):
        """Debit/credit field format matched against single amount field."""
        bank = [tx("2026-04-05", "Vendor Payment", credit=12000.0)]
        ledger = [tx("2026-04-05", "Vendor Payment", amount=12000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 1)

    def test_multiple_exact_matches(self):
        """Multiple independent exact matches are all captured."""
        bank = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-10", "Rent", amount=30000.0),
            tx("2026-04-15", "Internet", amount=2000.0),
        ]
        ledger = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-10", "Rent", amount=30000.0),
            tx("2026-04-15", "Internet Bill", amount=2000.0),
        ]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 3)
        self.assertEqual(result["summary"]["bank_only_count"], 0)
        self.assertEqual(result["summary"]["ledger_only_count"], 0)

    def test_amount_and_date_match_no_description(self):
        """Same date and amount with different descriptions → AMOUNT_AND_DATE_MATCH."""
        bank = [tx("2026-04-20", "Wire Transfer Incoming", amount=75000.0)]
        ledger = [tx("2026-04-20", "Client Remittance", amount=75000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 1)
        match = result["matches"][0]
        self.assertEqual(match["match_type"], "AMOUNT_AND_DATE_MATCH")
        self.assertAlmostEqual(match["confidence_score"], 0.9)

    def test_amount_tolerance_rounds_match(self):
        """Rounding tolerance of 0.01 still resolves as a match."""
        bank = [tx("2026-04-03", "Service Fee", amount=999.99)]
        ledger = [tx("2026-04-03", "Service Fee", amount=1000.00)]

        result = reconcile_transactions(bank, ledger, amount_tolerance=0.02)
        self.assertEqual(result["summary"]["matched_count"], 1)


# ===========================================================================
# Feature 2: Date-Tolerance Matching
# ===========================================================================
class TestDateToleranceMatching(unittest.TestCase):
    """Potential matches when transaction dates differ slightly."""

    def test_one_day_tolerance_match(self):
        """Dates differ by 1 day → POTENTIAL_MATCH with tolerance=1."""
        bank = [tx("2026-04-15", "Client Payment", amount=20000.0)]
        ledger = [tx("2026-04-16", "Client Payment", amount=20000.0)]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=1)
        summary = result["summary"]

        self.assertEqual(summary["potential_match_count"], 1)
        self.assertEqual(summary["matched_count"], 0)
        match = result["matches"][0]
        self.assertEqual(match["status"], "POTENTIAL_MATCH")
        self.assertEqual(match["match_type"], "DATE_TOLERANCE_MATCH")
        self.assertEqual(match["date_difference_days"], 1)
        self.assertEqual(match["amount_variance"], 0.0)

    def test_three_day_tolerance_match(self):
        """Dates differ by 3 days → POTENTIAL_MATCH with tolerance=3."""
        bank = [tx("2026-04-01", "Advance Payment", amount=15000.0)]
        ledger = [tx("2026-04-04", "Advance Payment", amount=15000.0)]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=3)
        self.assertEqual(result["summary"]["potential_match_count"], 1)
        self.assertEqual(result["matches"][0]["date_difference_days"], 3)

    def test_date_exceeding_tolerance_unmatched(self):
        """Dates differ by more than tolerance → remain BANK_ONLY / LEDGER_ONLY."""
        bank = [tx("2026-04-01", "Rent", amount=30000.0)]
        ledger = [tx("2026-04-10", "Rent", amount=30000.0)]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=1)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(summary["potential_match_count"], 0)
        self.assertEqual(summary["bank_only_count"], 1)
        self.assertEqual(summary["ledger_only_count"], 1)

    def test_zero_tolerance_no_potential_match(self):
        """date_tolerance_days=0 disables fuzzy date matching."""
        bank = [tx("2026-04-01", "Insurance", amount=5000.0)]
        ledger = [tx("2026-04-02", "Insurance", amount=5000.0)]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=0)
        self.assertEqual(result["summary"]["potential_match_count"], 0)
        self.assertEqual(result["summary"]["bank_only_count"], 1)
        self.assertEqual(result["summary"]["ledger_only_count"], 1)

    def test_closest_date_selected_when_multiple_candidates(self):
        """Engine picks the closest-date ledger entry for a POTENTIAL_MATCH."""
        bank = [tx("2026-04-10", "Utilities", amount=3000.0)]
        ledger = [
            tx("2026-04-12", "Utilities", amount=3000.0),  # 2 days away
            tx("2026-04-11", "Utilities", amount=3000.0),  # 1 day away — should be preferred
        ]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=3)
        self.assertEqual(result["summary"]["potential_match_count"], 1)
        self.assertEqual(result["matches"][0]["date_difference_days"], 1)
        # One ledger entry remains unmatched
        self.assertEqual(result["summary"]["ledger_only_count"], 1)

    def test_confidence_decreases_with_date_gap(self):
        """Confidence score is lower for larger date gaps."""
        bank = [tx("2026-04-01", "Fees", amount=1000.0)]
        ledger_1day = [tx("2026-04-02", "Fees", amount=1000.0)]
        ledger_3days = [tx("2026-04-04", "Fees", amount=1000.0)]

        r1 = reconcile_transactions(bank, ledger_1day, date_tolerance_days=5)
        r3 = reconcile_transactions(bank, ledger_3days, date_tolerance_days=5)

        conf1 = r1["matches"][0]["confidence_score"]
        conf3 = r3["matches"][0]["confidence_score"]
        self.assertGreater(conf1, conf3)


# ===========================================================================
# Feature 3: Amount Mismatch Detection
# ===========================================================================
class TestAmountMismatchDetection(unittest.TestCase):
    """Transactions with similar details but different amounts."""

    def test_basic_amount_mismatch(self):
        """Same date and description, but amounts differ → AMOUNT_MISMATCH."""
        bank = [tx("2026-04-10", "Office Supplies", amount=10000.0)]
        ledger = [tx("2026-04-10", "Office Supplies", amount=9500.0)]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["amount_mismatch_count"], 1)
        self.assertEqual(summary["matched_count"], 0)
        match = result["matches"][0]
        self.assertEqual(match["status"], "AMOUNT_MISMATCH")
        self.assertEqual(match["amount_variance"], 500.0)
        self.assertAlmostEqual(match["confidence_score"], 0.5)

    def test_amount_mismatch_variance_is_signed(self):
        """Variance reflects direction: bank amount minus ledger amount."""
        bank = [tx("2026-04-12", "Tax Payment", amount=5000.0)]
        ledger = [tx("2026-04-12", "Tax Payment", amount=6000.0)]

        result = reconcile_transactions(bank, ledger)
        match = result["matches"][0]
        # Bank 5000 < Ledger 6000 → variance = 5000 - 6000 = -1000
        self.assertEqual(match["amount_variance"], -1000.0)

    def test_amount_mismatch_note_contains_amounts(self):
        """Notes field includes bank and ledger amounts."""
        bank = [tx("2026-04-15", "Legal Fee", amount=8000.0)]
        ledger = [tx("2026-04-15", "Legal Fee", amount=7000.0)]

        result = reconcile_transactions(bank, ledger)
        note = result["matches"][0]["notes"]
        self.assertIn("8000", note)
        self.assertIn("7000", note)

    def test_amount_mismatch_not_triggered_when_tolerance_covers_gap(self):
        """When amount tolerance covers the gap, it becomes a MATCHED entry."""
        bank = [tx("2026-04-20", "Maintenance", amount=5010.0)]
        ledger = [tx("2026-04-20", "Maintenance", amount=5000.0)]

        result = reconcile_transactions(bank, ledger, amount_tolerance=15.0)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["amount_mismatch_count"], 0)


# ===========================================================================
# Feature 4: Unmatched Bank Transactions
# ===========================================================================
class TestUnmatchedBankTransactions(unittest.TestCase):
    """Bank transactions missing from the ledger."""

    def test_single_bank_only(self):
        """Bank transaction has no counterpart in ledger → BANK_ONLY."""
        bank = [tx("2026-04-05", "ATM Withdrawal", amount=5000.0)]
        ledger = []

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["bank_only_count"], 1)
        self.assertEqual(summary["matched_count"], 0)
        entry = result["bank_only"][0]
        self.assertEqual(entry["status"], "BANK_ONLY")
        self.assertIn("bank statement", entry["notes"])

    def test_multiple_bank_only(self):
        """Three bank transactions with no ledger counterparts → all BANK_ONLY."""
        bank = [
            tx("2026-04-01", "A", amount=100.0),
            tx("2026-04-02", "B", amount=200.0),
            tx("2026-04-03", "C", amount=300.0),
        ]
        result = reconcile_transactions(bank, [])
        self.assertEqual(result["summary"]["bank_only_count"], 3)

    def test_partial_match_rest_bank_only(self):
        """One bank tx matches, the rest become BANK_ONLY."""
        bank = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-05", "Bank Charges", amount=250.0),
            tx("2026-04-10", "Bonus", amount=10000.0),
        ]
        ledger = [tx("2026-04-01", "Salary", amount=50000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["bank_only_count"], 2)
        self.assertEqual(result["summary"]["ledger_only_count"], 0)


# ===========================================================================
# Feature 5: Unmatched Ledger Transactions
# ===========================================================================
class TestUnmatchedLedgerTransactions(unittest.TestCase):
    """Ledger entries missing from the bank statement."""

    def test_single_ledger_only(self):
        """Ledger entry has no counterpart in bank → LEDGER_ONLY."""
        bank = []
        ledger = [tx("2026-04-10", "Depreciation", amount=4000.0)]

        result = reconcile_transactions(bank, ledger)
        summary = result["summary"]

        self.assertEqual(summary["ledger_only_count"], 1)
        entry = result["ledger_only"][0]
        self.assertEqual(entry["status"], "LEDGER_ONLY")
        self.assertIn("ledger", entry["notes"])

    def test_multiple_ledger_only(self):
        """Multiple ledger entries with no bank counterparts."""
        ledger = [
            tx("2026-04-01", "Accrual", amount=500.0),
            tx("2026-04-15", "Provision", amount=1200.0),
        ]
        result = reconcile_transactions([], ledger)
        self.assertEqual(result["summary"]["ledger_only_count"], 2)

    def test_partial_match_rest_ledger_only(self):
        """One ledger tx matches, the rest become LEDGER_ONLY."""
        bank = [tx("2026-04-01", "Salary", amount=50000.0)]
        ledger = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-07", "Consulting Fee", amount=8000.0),
            tx("2026-04-20", "Software Subscription", amount=1500.0),
        ]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["bank_only_count"], 0)
        self.assertEqual(result["summary"]["ledger_only_count"], 2)


# ===========================================================================
# Feature 6: Reconciliation Summary Statistics
# ===========================================================================
class TestReconciliationSummary(unittest.TestCase):
    """Reconciliation statistics are computed correctly."""

    def test_summary_keys_present(self):
        """All required summary keys are returned."""
        result = reconcile_transactions([], [])
        expected_keys = {
            "total_bank_transactions",
            "total_ledger_transactions",
            "matched_count",
            "potential_match_count",
            "amount_mismatch_count",
            "bank_only_count",
            "ledger_only_count",
            "reconciliation_rate",
            "total_bank_amount",
            "total_ledger_amount",
            "matched_amount",
            "net_discrepancy",
        }
        self.assertEqual(set(result["summary"].keys()), expected_keys)

    def test_total_counts_match_inputs(self):
        """total_bank_transactions and total_ledger_transactions reflect input sizes."""
        bank = [tx("2026-04-01", "A", amount=100.0), tx("2026-04-02", "B", amount=200.0)]
        ledger = [tx("2026-04-01", "A", amount=100.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["total_bank_transactions"], 2)
        self.assertEqual(result["summary"]["total_ledger_transactions"], 1)

    def test_reconciliation_rate_100_percent_when_all_matched(self):
        """100% reconciliation rate when every entry is matched."""
        bank = [tx("2026-04-01", "Salary", amount=50000.0)]
        ledger = [tx("2026-04-01", "Salary", amount=50000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["reconciliation_rate"], 100.0)

    def test_reconciliation_rate_zero_when_nothing_matches(self):
        """0% reconciliation rate when nothing matches."""
        bank = [tx("2026-04-01", "A", amount=100.0)]
        ledger = [tx("2026-04-10", "B", amount=999.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["reconciliation_rate"], 0.0)

    def test_net_discrepancy_positive(self):
        """net_discrepancy = total_bank_amount - total_ledger_amount."""
        bank = [tx("2026-04-01", "X", amount=10000.0)]
        ledger = [tx("2026-04-01", "Y", amount=7000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertAlmostEqual(result["summary"]["net_discrepancy"], 3000.0)

    def test_net_discrepancy_negative(self):
        """Negative discrepancy when ledger total exceeds bank total."""
        bank = [tx("2026-04-01", "X", amount=5000.0)]
        ledger = [tx("2026-04-01", "Y", amount=8000.0)]

        result = reconcile_transactions(bank, ledger)
        self.assertAlmostEqual(result["summary"]["net_discrepancy"], -3000.0)

    def test_total_bank_and_ledger_amounts(self):
        """Total amounts accumulate correctly across multiple transactions."""
        bank = [
            tx("2026-04-01", "A", amount=10000.0),
            tx("2026-04-02", "B", amount=5000.0),
        ]
        ledger = [
            tx("2026-04-01", "A", amount=10000.0),
            tx("2026-04-05", "C", amount=2000.0),
        ]

        result = reconcile_transactions(bank, ledger)
        self.assertAlmostEqual(result["summary"]["total_bank_amount"], 15000.0)
        self.assertAlmostEqual(result["summary"]["total_ledger_amount"], 12000.0)

    def test_result_structure_keys_present(self):
        """Top-level result contains summary, matches, bank_only, ledger_only."""
        result = reconcile_transactions([], [])
        self.assertIn("summary", result)
        self.assertIn("matches", result)
        self.assertIn("bank_only", result)
        self.assertIn("ledger_only", result)


# ===========================================================================
# Feature 7: Edge Cases and Robustness
# ===========================================================================
class TestEdgeCases(unittest.TestCase):

    def test_empty_inputs(self):
        """Empty bank and ledger returns safe zero-value summary."""
        result = reconcile_transactions([], [])
        summary = result["summary"]
        self.assertEqual(summary["total_bank_transactions"], 0)
        self.assertEqual(summary["total_ledger_transactions"], 0)
        self.assertEqual(summary["matched_count"], 0)
        self.assertEqual(len(result["matches"]), 0)
        self.assertEqual(len(result["bank_only"]), 0)
        self.assertEqual(len(result["ledger_only"]), 0)

    def test_empty_bank_all_ledger_only(self):
        """No bank transactions → all ledger entries are LEDGER_ONLY."""
        ledger = [tx("2026-04-01", "Accrual", amount=5000.0)]
        result = reconcile_transactions([], ledger)
        self.assertEqual(result["summary"]["ledger_only_count"], 1)
        self.assertEqual(result["summary"]["bank_only_count"], 0)

    def test_empty_ledger_all_bank_only(self):
        """No ledger transactions → all bank entries are BANK_ONLY."""
        bank = [tx("2026-04-01", "ATM", amount=3000.0)]
        result = reconcile_transactions(bank, [])
        self.assertEqual(result["summary"]["bank_only_count"], 1)
        self.assertEqual(result["summary"]["ledger_only_count"], 0)

    def test_duplicate_candidates_one_to_one(self):
        """One bank entry with ₹1,000 matches exactly one ledger entry; extra stays LEDGER_ONLY."""
        bank = [tx("2026-04-20", "Stationery", amount=1000.0)]
        ledger = [
            tx("2026-04-20", "Stationery", amount=1000.0),
            tx("2026-04-20", "Stationery", amount=1000.0),
        ]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["ledger_only_count"], 1)

    def test_internal_keys_not_exposed_in_result(self):
        """Normalization helper keys (_norm_date, etc.) must not appear in output."""
        bank = [tx("2026-04-01", "Salary", amount=50000.0)]
        ledger = [tx("2026-04-01", "Salary", amount=50000.0)]

        result = reconcile_transactions(bank, ledger)
        match = result["matches"][0]
        for key in ("_norm_date", "_norm_desc", "_norm_amt", "_abs_amt"):
            self.assertNotIn(key, match["bank_transaction"])
            self.assertNotIn(key, match["ledger_transaction"])

    def test_input_dicts_not_mutated(self):
        """Engine must not modify the original input dictionaries."""
        bank = [{"transaction_date": "2026-04-01", "description": "Test", "amount": 100.0}]
        ledger = [{"transaction_date": "2026-04-01", "description": "Test", "amount": 100.0}]
        bank_copy = [dict(b) for b in bank]
        ledger_copy = [dict(l) for l in ledger]

        reconcile_transactions(bank, ledger)

        self.assertEqual(bank[0], bank_copy[0])
        self.assertEqual(ledger[0], ledger_copy[0])

    def test_missing_transaction_date_skipped_in_exact_matching(self):
        """Transactions with missing dates are not matched as exact/tolerance matches."""
        bank = [{"description": "No Date TX", "amount": 1000.0}]
        ledger = [{"description": "No Date TX", "amount": 1000.0}]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 0)

    def test_large_dataset_all_matched(self):
        """Stress test: 50 transactions all matched correctly."""
        bank = [tx(f"2026-04-{str(i).zfill(2)}", f"TX{i}", amount=float(i * 1000)) for i in range(1, 29)]
        ledger = [tx(f"2026-04-{str(i).zfill(2)}", f"TX{i}", amount=float(i * 1000)) for i in range(1, 29)]

        result = reconcile_transactions(bank, ledger)
        self.assertEqual(result["summary"]["matched_count"], 28)
        self.assertEqual(result["summary"]["bank_only_count"], 0)
        self.assertEqual(result["summary"]["ledger_only_count"], 0)

    def test_mixed_scenario_all_categories(self):
        """
        Real-world-style scenario covering all five categories simultaneously:
          - 1 EXACT_MATCH
          - 1 POTENTIAL_MATCH (date tolerance)
          - 1 AMOUNT_MISMATCH
          - 1 BANK_ONLY
          - 1 LEDGER_ONLY
        """
        bank = [
            tx("2026-04-01", "Salary", amount=50000.0),       # → EXACT_MATCH
            tx("2026-04-15", "Client Payment", amount=20000.0), # → POTENTIAL_MATCH (ledger = Apr 16)
            tx("2026-04-10", "Office Supplies", amount=10000.0), # → AMOUNT_MISMATCH (ledger = 9500)
            tx("2026-04-05", "Bank Charges", amount=250.0),    # → BANK_ONLY
        ]
        ledger = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-16", "Client Payment", amount=20000.0),
            tx("2026-04-10", "Office Supplies", amount=9500.0),
            tx("2026-04-20", "Depreciation", amount=4000.0),   # → LEDGER_ONLY
        ]

        result = reconcile_transactions(bank, ledger, date_tolerance_days=2)
        summary = result["summary"]

        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["potential_match_count"], 1)
        self.assertEqual(summary["amount_mismatch_count"], 1)
        self.assertEqual(summary["bank_only_count"], 1)
        self.assertEqual(summary["ledger_only_count"], 1)
        self.assertEqual(summary["total_bank_transactions"], 4)
        self.assertEqual(summary["total_ledger_transactions"], 4)

    def test_engine_direct_instantiation(self):
        """ReconciliationEngine can be instantiated and called directly."""
        engine = ReconciliationEngine(date_tolerance_days=2, amount_tolerance=10.0)
        result = engine.reconcile(
            [tx("2026-04-01", "Salary", amount=50000.0)],
            [tx("2026-04-01", "Salary", amount=50000.0)],
        )
        self.assertEqual(result["summary"]["matched_count"], 1)

    def test_negative_tolerance_clamped_to_zero(self):
        """Negative date_tolerance_days is clamped to 0 safely."""
        engine = ReconciliationEngine(date_tolerance_days=-5)
        self.assertEqual(engine.date_tolerance_days, 0)

    def test_negative_amount_tolerance_clamped_to_zero(self):
        """Negative amount_tolerance is clamped to 0.0 safely."""
        engine = ReconciliationEngine(amount_tolerance=-100.0)
        self.assertEqual(engine.amount_tolerance, 0.0)


if __name__ == "__main__":
    unittest.main()
