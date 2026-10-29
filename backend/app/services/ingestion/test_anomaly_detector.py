"""
Unit tests for the Transaction Anomaly Detection Engine.

Coverage:
1. Normalization & Statistical Helpers (date, amount parsing, IQR bounds, round numbers)
2. Unusually Large Transactions / Statistical Outlier (IQR on absolute amounts)
3. Unusual Debit or Credit Amounts (independent distributions)
4. Repeated Round Amounts (multiple ₹50,000 or ₹1,00,000 transactions)
5. Unusual Transaction Frequency (burst activity on a single date)
6. Combined Anomaly Flags & Severity Ratings
7. Summary Statistics & Rate Calculations
8. Edge Cases (empty input, small dataset, identical amounts, missing fields, DataFrame input)
"""

from datetime import date, datetime
import unittest
import pandas as pd

from app.services.ingestion.anomaly_detector import (
    AnomalyDetector,
    compute_iqr_bounds,
    detect_anomalies,
    extract_amount_details,
    is_round_number,
    normalize_date_str,
)


def tx(
    date_val: str | date | datetime,
    desc: str,
    amount: float | None = None,
    debit: float | None = None,
    credit: float | None = None,
    source_row: int = 1,
) -> dict:
    """Convenience helper to build transaction dictionary."""
    d = {
        "transaction_date": date_val,
        "description": desc,
        "source_row": source_row,
    }
    if amount is not None:
        d["amount"] = amount
    if debit is not None:
        d["debit"] = debit
    if credit is not None:
        d["credit"] = credit
    return d


# ===========================================================================
# 1. Helper Function Tests
# ===========================================================================
class TestAnomalyHelpers(unittest.TestCase):

    def test_normalize_date_str(self):
        self.assertEqual(normalize_date_str("2026-04-01"), "2026-04-01")
        self.assertEqual(normalize_date_str("01/04/2026"), "2026-04-01")
        self.assertEqual(normalize_date_str(date(2026, 4, 1)), "2026-04-01")
        self.assertEqual(normalize_date_str(datetime(2026, 4, 1, 10, 30)), "2026-04-01")
        self.assertIsNone(normalize_date_str(None))
        self.assertIsNone(normalize_date_str("invalid-date"))

    def test_extract_amount_details_explicit_amount(self):
        res = extract_amount_details({"amount": 5000.0})
        self.assertEqual(res["net_amount"], 5000.0)
        self.assertEqual(res["abs_amount"], 5000.0)
        self.assertEqual(res["type"], "CREDIT")

        res_neg = extract_amount_details({"amount": -2500.0})
        self.assertEqual(res_neg["net_amount"], -2500.0)
        self.assertEqual(res_neg["abs_amount"], 2500.0)
        self.assertEqual(res_neg["type"], "DEBIT")

    def test_extract_amount_details_currency_symbols(self):
        res = extract_amount_details({"amount": "₹ 50,000.00"})
        self.assertEqual(res["net_amount"], 50000.0)
        self.assertEqual(res["abs_amount"], 50000.0)

    def test_extract_amount_details_debit_credit(self):
        res_deb = extract_amount_details({"debit": 1500.0, "credit": 0.0})
        self.assertEqual(res_deb["debit"], 1500.0)
        self.assertEqual(res_deb["abs_amount"], 1500.0)
        self.assertEqual(res_deb["type"], "DEBIT")

        res_crd = extract_amount_details({"credit": 8000.0})
        self.assertEqual(res_crd["credit"], 8000.0)
        self.assertEqual(res_crd["abs_amount"], 8000.0)
        self.assertEqual(res_crd["type"], "CREDIT")

    def test_compute_iqr_bounds_insufficient_samples(self):
        res = compute_iqr_bounds([100.0, 200.0], min_samples=4)
        self.assertEqual(res["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(res["upper_bound"])
        self.assertIsNone(res["iqr"])

    def test_compute_iqr_bounds_valid(self):
        # Sample with values 2000, 3000, 5000, 8000, 10000, 500000
        values = [2000.0, 3000.0, 5000.0, 8000.0, 10000.0, 500000.0]
        res = compute_iqr_bounds(values, multiplier=1.5, min_samples=4)
        self.assertEqual(res["status"], "VALID")
        self.assertIsNotNone(res["q1"])
        self.assertIsNotNone(res["q3"])
        self.assertGreater(res["upper_bound"], res["q3"])
        self.assertLess(res["upper_bound"], 500000.0)

    def test_is_round_number(self):
        self.assertTrue(is_round_number(50000.0, min_value=1000.0))
        self.assertTrue(is_round_number(100000.0, min_value=1000.0))
        self.assertTrue(is_round_number(5000.0, min_value=1000.0))
        self.assertFalse(is_round_number(1234.56, min_value=1000.0))
        self.assertFalse(is_round_number(500.0, min_value=1000.0))
        self.assertFalse(is_round_number(None))


# ===========================================================================
# 2. Feature 1: Unusually Large Transactions / Statistical Outlier
# ===========================================================================
class TestUnusuallyLargeTransactions(unittest.TestCase):

    def test_large_transaction_flagged(self):
        """
        Example from requirement:
        Most transactions are ₹2,000–₹10,000, but one is ₹5,00,000 -> Flag for review.
        """
        transactions = [
            tx("2026-04-01", "Office Supplies", amount=2000.0),
            tx("2026-04-02", "Travel", amount=3500.0),
            tx("2026-04-03", "Software License", amount=5000.0),
            tx("2026-04-04", "Utilities", amount=7500.0),
            tx("2026-04-05", "Equipment Maintenance", amount=9000.0),
            tx("2026-04-06", "Consulting", amount=10000.0),
            tx("2026-04-07", "Heavy Machinery", amount=500000.0),  # Outlier
        ]

        result = detect_anomalies(transactions)

        self.assertEqual(result["total_transactions"], 7)
        self.assertGreaterEqual(result["anomalous_transactions_count"], 1)

        outlier = [t for t in result["flagged_transactions"] if t["amount"] == 500000.0][0]
        self.assertTrue(outlier["is_anomaly"])
        self.assertIn("UNUSUALLY_LARGE_AMOUNT", outlier["anomaly_flags"])
        self.assertEqual(outlier["severity"], "HIGH")
        self.assertTrue(outlier["requires_review"])
        self.assertIn("statistical outlier", outlier["anomaly_reasons"][0])

        # Normal small transactions should not be flagged as unusually large
        small = [t for t in result["flagged_transactions"] if t["amount"] == 2000.0][0]
        self.assertNotIn("UNUSUALLY_LARGE_AMOUNT", small["anomaly_flags"])

    def test_no_outliers_in_uniform_distribution(self):
        """When transactions are in a normal range, no outliers are flagged."""
        transactions = [
            tx("2026-04-01", f"Item {i}", amount=float(5000 + (i * 100)))
            for i in range(10)
        ]
        result = detect_anomalies(transactions)
        self.assertEqual(result["flag_counts"].get("UNUSUALLY_LARGE_AMOUNT", 0), 0)


# ===========================================================================
# 3. Feature 2: Unusual Debit or Credit
# ===========================================================================
class TestUnusualDebitCredit(unittest.TestCase):

    def test_unusual_debit_flagged(self):
        """A debit significantly larger than normal user debits is flagged."""
        transactions = [
            tx("2026-04-01", "Coffee", debit=150.0),
            tx("2026-04-02", "Lunch", debit=350.0),
            tx("2026-04-03", "Taxi", debit=500.0),
            tx("2026-04-04", "Groceries", debit=800.0),
            tx("2026-04-05", "Books", debit=1200.0),
            tx("2026-04-06", "Luxury Purchase", debit=95000.0),  # Abnormal debit
        ]

        result = detect_anomalies(transactions, separate_debit_credit=True)
        anomalies = [t for t in result["anomalies"] if t.get("debit") == 95000.0]

        self.assertEqual(len(anomalies), 1)
        self.assertIn("UNUSUAL_DEBIT", anomalies[0]["anomaly_flags"])
        self.assertTrue(
            any("Debit of ₹95,000.00 is significantly larger" in r for r in anomalies[0]["anomaly_reasons"])
        )

    def test_unusual_credit_flagged(self):
        """A credit significantly larger than normal credits is flagged."""
        transactions = [
            tx("2026-04-01", "Client A", credit=10000.0),
            tx("2026-04-02", "Client B", credit=12000.0),
            tx("2026-04-03", "Client C", credit=15000.0),
            tx("2026-04-04", "Client D", credit=18000.0),
            tx("2026-04-05", "Client E", credit=20000.0),
            tx("2026-04-06", "Surprise Windfall", credit=4500000.0),  # Abnormal credit
        ]

        result = detect_anomalies(transactions, separate_debit_credit=True)
        anomalies = [t for t in result["anomalies"] if t.get("credit") == 4500000.0]

        self.assertEqual(len(anomalies), 1)
        self.assertIn("UNUSUAL_CREDIT", anomalies[0]["anomaly_flags"])


# ===========================================================================
# 4. Feature 3: Repeated Round Amounts
# ===========================================================================
class TestRepeatedRoundAmounts(unittest.TestCase):

    def test_multiple_round_amounts_flagged(self):
        """
        Example from requirement:
        Multiple transactions of ₹50,000 or ₹1,00,000 -> Flag for review.
        """
        transactions = [
            tx("2026-04-01", "Vendor Payment A", amount=50000.0),
            tx("2026-04-05", "Vendor Payment B", amount=50000.0),
            tx("2026-04-10", "Vendor Payment C", amount=50000.0),
            tx("2026-04-12", "Normal Bill", amount=12345.0),
            tx("2026-04-15", "Routine Expense", amount=8420.0),
        ]

        result = detect_anomalies(
            transactions,
            round_amount_min=5000.0,
            round_amount_min_occurrences=2,
        )

        round_flagged = [
            t for t in result["anomalies"]
            if "REPEATED_ROUND_AMOUNT" in t["anomaly_flags"]
        ]

        # All 3 ₹50,000 transactions should receive the repeated round flag
        self.assertEqual(len(round_flagged), 3)
        self.assertIn("Round amount of ₹50,000.00 observed 3 times", round_flagged[0]["anomaly_reasons"][0])

    def test_single_round_amount_not_flagged_as_repeated(self):
        """A single round amount under the occurrence threshold is NOT flagged as repeated."""
        transactions = [
            tx("2026-04-01", "Vendor Payment", amount=50000.0),  # only 1 occurrence
            tx("2026-04-02", "Bill 1", amount=4520.0),
            tx("2026-04-03", "Bill 2", amount=7830.0),
            tx("2026-04-04", "Bill 3", amount=6190.0),
        ]

        result = detect_anomalies(
            transactions,
            round_amount_min=5000.0,
            round_amount_min_occurrences=2,
        )

        repeated_flags = [
            t for t in result["flagged_transactions"]
            if "REPEATED_ROUND_AMOUNT" in t["anomaly_flags"]
        ]
        self.assertEqual(len(repeated_flags), 0)


# ===========================================================================
# 5. Feature 4: Unusual Transaction Frequency
# ===========================================================================
class TestUnusualTransactionFrequency(unittest.TestCase):

    def test_high_frequency_burst_flagged(self):
        """
        Example from requirement:
        15 transactions occur within a short period -> Flag unusual activity.
        """
        # 15 transactions on the exact same date
        burst_txs = [
            tx("2026-04-15", f"Micro-tx {i}", amount=float(100 + (i * 10)))
            for i in range(15)
        ]
        # And 2 transactions on another date
        normal_txs = [
            tx("2026-04-01", "Regular 1", amount=2500.0),
            tx("2026-04-02", "Regular 2", amount=3000.0),
        ]

        result = detect_anomalies(
            burst_txs + normal_txs,
            frequency_threshold=10,  # Alert if >= 10 on a single day
        )

        freq_flagged = [
            t for t in result["anomalies"]
            if "HIGH_TRANSACTION_FREQUENCY" in t["anomaly_flags"]
        ]

        self.assertEqual(len(freq_flagged), 15)
        self.assertIn("2026-04-15", freq_flagged[0]["anomaly_reasons"][0])
        self.assertIn("burst of 15 transactions", freq_flagged[0]["anomaly_reasons"][0])

        # Regular date transactions should NOT be flagged for frequency
        reg1 = [t for t in result["flagged_transactions"] if t["description"] == "Regular 1"][0]
        self.assertNotIn("HIGH_TRANSACTION_FREQUENCY", reg1["anomaly_flags"])


# ===========================================================================
# 6. Combined Flags & Severity
# ===========================================================================
class TestCombinedAnomalies(unittest.TestCase):

    def test_multi_flag_triggers_high_severity(self):
        """A transaction with multiple anomaly triggers is assigned HIGH severity."""
        transactions = [
            tx("2026-04-01", "A", amount=1000.0),
            tx("2026-04-01", "B", amount=1200.0),
            tx("2026-04-01", "C", amount=1400.0),
            tx("2026-04-01", "D", amount=1600.0),
            tx("2026-04-01", "E", amount=1800.0),
            tx("2026-04-01", "F", amount=2000.0),
            tx("2026-04-01", "G", amount=2200.0),
            # Repeat ₹1,00,000 twice on 2026-04-10
            tx("2026-04-10", "Round & Large 1", amount=100000.0),
            tx("2026-04-10", "Round & Large 2", amount=100000.0),
        ]

        result = detect_anomalies(transactions, min_samples_for_iqr=4)
        large_and_round = [t for t in result["anomalies"] if t["amount"] == 100000.0][0]

        self.assertIn("UNUSUALLY_LARGE_AMOUNT", large_and_round["anomaly_flags"])
        self.assertIn("REPEATED_ROUND_AMOUNT", large_and_round["anomaly_flags"])
        self.assertEqual(large_and_round["severity"], "HIGH")


# ===========================================================================
# 7. Summary Statistics & Rate Calculations
# ===========================================================================
class TestSummaryStatistics(unittest.TestCase):

    def test_summary_structure(self):
        transactions = [
            tx("2026-04-01", "Salary", amount=50000.0),
            tx("2026-04-02", "Rent", amount=15000.0),
            tx("2026-04-03", "Groceries", amount=3000.0),
            tx("2026-04-04", "Utilities", amount=2000.0),
        ]

        result = detect_anomalies(transactions)

        self.assertIn("total_transactions", result)
        self.assertIn("anomalous_transactions_count", result)
        self.assertIn("normal_transactions_count", result)
        self.assertIn("anomaly_rate", result)
        self.assertIn("flag_counts", result)
        self.assertIn("statistics", result)
        self.assertIn("anomalies", result)
        self.assertIn("flagged_transactions", result)
        self.assertIn("disclaimer", result)
        self.assertIn("human review", result["disclaimer"])

        self.assertEqual(result["total_transactions"], 4)
        self.assertEqual(
            result["anomalous_transactions_count"] + result["normal_transactions_count"],
            result["total_transactions"],
        )

    def test_frequency_statistics(self):
        transactions = [
            tx("2026-04-01", "A", amount=100.0),
            tx("2026-04-01", "B", amount=200.0),
            tx("2026-04-02", "C", amount=300.0),
        ]
        result = detect_anomalies(transactions)
        freq_stats = result["statistics"]["frequency"]
        self.assertEqual(freq_stats["unique_dates"], 2)
        self.assertEqual(freq_stats["max_daily_transactions"], 2)


# ===========================================================================
# 8. Edge Cases & Robustness
# ===========================================================================
class TestEdgeCases(unittest.TestCase):

    def test_empty_transaction_list(self):
        """Safe zero-handling for empty input."""
        result = detect_anomalies([])
        self.assertEqual(result["total_transactions"], 0)
        self.assertEqual(result["anomalous_transactions_count"], 0)
        self.assertEqual(result["anomaly_rate"], 0.0)
        self.assertEqual(len(result["anomalies"]), 0)
        self.assertEqual(len(result["flagged_transactions"]), 0)

    def test_small_dataset_iqr_fallback(self):
        """Datasets below min_samples_for_iqr do not crash and report a helpful note."""
        transactions = [
            tx("2026-04-01", "One", amount=1000.0),
            tx("2026-04-02", "Two", amount=2000.0),
        ]
        result = detect_anomalies(transactions, min_samples_for_iqr=4)
        self.assertEqual(result["statistics"]["amount"]["status"], "INSUFFICIENT_DATA")
        self.assertTrue(any("at least 4 are required" in note for note in result["notes"]))

    def test_input_mutation_safety(self):
        """Detector does not mutate original input dictionaries."""
        transactions = [
            {"transaction_date": "2026-04-01", "description": "Test", "amount": 1000.0}
        ]
        tx_copy = dict(transactions[0])
        detect_anomalies(transactions)
        self.assertEqual(transactions[0], tx_copy)

    def test_dataframe_input_support(self):
        """Accepts a pandas DataFrame directly."""
        df = pd.DataFrame([
            {"transaction_date": "2026-04-01", "description": "A", "amount": 1000.0},
            {"transaction_date": "2026-04-02", "description": "B", "amount": 2000.0},
            {"transaction_date": "2026-04-03", "description": "C", "amount": 3000.0},
            {"transaction_date": "2026-04-04", "description": "D", "amount": 4000.0},
            {"transaction_date": "2026-04-05", "description": "E", "amount": 500000.0},
        ])
        result = detect_anomalies(df)
        self.assertEqual(result["total_transactions"], 5)
        self.assertGreaterEqual(result["anomalous_transactions_count"], 1)

    def test_identical_amounts_iqr_zero(self):
        """When all amounts are identical, IQR is 0.0 without divide-by-zero errors."""
        transactions = [
            tx("2026-04-01", f"Item {i}", amount=1000.0)
            for i in range(10)
        ]
        result = detect_anomalies(transactions)
        self.assertEqual(result["statistics"]["amount"]["iqr"], 0.0)

    def test_detector_class_direct_instantiation(self):
        """AnomalyDetector class can be configured and run directly."""
        detector = AnomalyDetector(iqr_multiplier=2.0, frequency_threshold=5)
        result = detector.detect([])
        self.assertEqual(result["total_transactions"], 0)


if __name__ == "__main__":
    unittest.main()
