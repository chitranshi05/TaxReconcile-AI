"""
Unit tests for the Indian Tax Rule Validation Engine.

Covers:
1. Data Integrity & Missing Information Checks
2. TDS Cross-Reconciliation (Form 26AS vs Financial Records)
3. Income Discrepancies & Section 269ST Cash Compliance
4. Chapter VI-A Deduction Validation (80C, 80D, 80CCD, 80TTA/TTB, Supporting Proofs)
5. Financial Year Versioning & Configurable Thresholds
6. Comprehensive Validation Pipeline, Readiness Scoring & Edge Cases
"""

from datetime import date
import unittest
import pandas as pd

from app.services.tax_validation.tax_rule_engine import (
    DEFAULT_FY_CONFIGS,
    TaxRuleEngine,
    create_finding,
    parse_date_obj,
    parse_float_amount,
    validate_tax_records,
)


# ===========================================================================
# 1. Helper & Formatting Tests
# ===========================================================================
class TestTaxValidationHelpers(unittest.TestCase):

    def test_parse_float_amount(self):
        self.assertEqual(parse_float_amount(150000.0), 150000.0)
        self.assertEqual(parse_float_amount("₹ 1,50,000.00"), 150000.0)
        self.assertEqual(parse_float_amount("$ 500.50"), 500.50)
        self.assertIsNone(parse_float_amount(None))
        self.assertIsNone(parse_float_amount(""))
        self.assertIsNone(parse_float_amount("invalid"))

    def test_parse_date_obj(self):
        self.assertEqual(parse_date_obj("2026-04-01"), date(2026, 4, 1))
        self.assertEqual(parse_date_obj("01/04/2026"), date(2026, 4, 1))
        self.assertEqual(parse_date_obj(date(2026, 4, 1)), date(2026, 4, 1))
        self.assertIsNone(parse_date_obj(None))
        self.assertIsNone(parse_date_obj("not-a-date"))

    def test_create_finding_format(self):
        f = create_finding(
            rule_id="TAX-TEST-001",
            category="TEST",
            severity="WARNING",
            title="Test Finding",
            description="Testing standard finding shape.",
            section="Section 80C",
            details={"key": "val"},
        )
        self.assertEqual(f["rule_id"], "TAX-TEST-001")
        self.assertEqual(f["severity"], "WARNING")
        self.assertEqual(f["section"], "Section 80C")
        self.assertIn("remediation", f)


# ===========================================================================
# 2. Missing & Incomplete Transaction Data
# ===========================================================================
class TestMissingTransactionData(unittest.TestCase):

    def setUp(self):
        self.engine = TaxRuleEngine(financial_year="2025-26")

    def test_missing_date_detected(self):
        """Missing or malformed transaction date generates ERROR TAX-DATA-001."""
        txs = [
            {"transaction_date": None, "description": "Salary", "amount": 50000.0, "source_row": 2},
            {"transaction_date": "invalid-date", "description": "Rent", "amount": 15000.0, "source_row": 3},
        ]
        findings = self.engine.validate_transaction_integrity(txs)
        date_errors = [f for f in findings if f["rule_id"] == "TAX-DATA-001"]

        self.assertEqual(len(date_errors), 2)
        self.assertEqual(date_errors[0]["severity"], "ERROR")
        self.assertIn("Missing Transaction Date", date_errors[0]["title"])

    def test_missing_amount_detected(self):
        """Missing financial amount generates ERROR TAX-DATA-002."""
        txs = [
            {"transaction_date": "2026-04-01", "description": "Empty Entry", "amount": None, "source_row": 5}
        ]
        findings = self.engine.validate_transaction_integrity(txs)
        amt_errors = [f for f in findings if f["rule_id"] == "TAX-DATA-002"]

        self.assertEqual(len(amt_errors), 1)
        self.assertEqual(amt_errors[0]["severity"], "ERROR")

    def test_blank_description_detected(self):
        """Missing transaction narration generates WARNING TAX-DATA-003."""
        txs = [
            {"transaction_date": "2026-04-01", "description": "   ", "amount": 25000.0, "source_row": 6}
        ]
        findings = self.engine.validate_transaction_integrity(txs)
        desc_warnings = [f for f in findings if f["rule_id"] == "TAX-DATA-003"]

        self.assertEqual(len(desc_warnings), 1)
        self.assertEqual(desc_warnings[0]["severity"], "WARNING")

    def test_negative_debit_or_credit_detected(self):
        """Negative debit/credit generates ERROR TAX-DATA-004."""
        txs = [
            {"transaction_date": "2026-04-01", "description": "Reversal", "debit": -500.0, "source_row": 7}
        ]
        findings = self.engine.validate_transaction_integrity(txs)
        neg_errors = [f for f in findings if f["rule_id"] == "TAX-DATA-004"]

        self.assertEqual(len(neg_errors), 1)
        self.assertEqual(neg_errors[0]["severity"], "ERROR")


# ===========================================================================
# 3. TDS Reconciliation (Form 26AS vs Books)
# ===========================================================================
class TestTDSReconciliation(unittest.TestCase):

    def setUp(self):
        self.engine = TaxRuleEngine(financial_year="2025-26")

    def test_tds_missing_in_books(self):
        """TDS reported in Form 26AS without matching entry in books flags WARNING TAX-TDS-001."""
        tds_entries = [
            {
                "deductor_name": "ABC Tech Corp",
                "deductor_tan": "BLRA12345C",
                "section": "Section 194J",
                "tds_amount": 10000.0,
                "gross_amount": 100000.0,
                "source_row": 2,
            }
        ]
        books = []  # No corresponding TDS in books

        findings = self.engine.reconcile_tds(tds_entries, books)
        missing_tds = [f for f in findings if f["rule_id"] == "TAX-TDS-001"]

        self.assertEqual(len(missing_tds), 1)
        self.assertEqual(missing_tds[0]["severity"], "WARNING")
        self.assertIn("ABC Tech Corp", missing_tds[0]["description"])
        self.assertIn("₹10,000.00", missing_tds[0]["description"])

    def test_tds_amount_mismatch(self):
        """TDS discrepancy between 26AS and books beyond tolerance flags WARNING TAX-TDS-002."""
        tds_entries = [
            {
                "deductor_tan": "BLRA12345C",
                "deductor_name": "ABC Tech Corp",
                "tds_amount": 10000.0,
                "source_row": 2,
            }
        ]
        books = [
            {
                "deductor_tan": "BLRA12345C",
                "tds_amount": 8500.0,  # ₹1,500 mismatch
            }
        ]

        findings = self.engine.reconcile_tds(tds_entries, books)
        mismatch_tds = [f for f in findings if f["rule_id"] == "TAX-TDS-002"]

        self.assertEqual(len(mismatch_tds), 1)
        self.assertEqual(mismatch_tds[0]["details"]["variance"], 1500.0)

    def test_matching_tds_clean(self):
        """Matching TDS produces no findings."""
        tds_entries = [
            {"deductor_tan": "BLRA12345C", "tds_amount": 10000.0}
        ]
        books = [
            {"deductor_tan": "BLRA12345C", "tds_amount": 10000.0}
        ]

        findings = self.engine.reconcile_tds(tds_entries, books)
        self.assertEqual(len(findings), 0)


# ===========================================================================
# 4. Income Discrepancy & Section 269ST Cash Compliance
# ===========================================================================
class TestIncomeDiscrepancyAndCash(unittest.TestCase):

    def setUp(self):
        self.engine = TaxRuleEngine(financial_year="2025-26")

    def test_salary_income_discrepancy(self):
        """Declared salary differing significantly from identifiable bank deposits flags TAX-INC-001."""
        declared = {"salary": 1200000.0}
        bank_txs = [
            {"transaction_date": "2026-04-30", "description": "Monthly Salary", "credit": 80000.0},
            {"transaction_date": "2026-05-31", "description": "Monthly Salary", "credit": 80000.0},
            # Total bank salary is only ₹1,60,000 vs ₹12,00,000 declared
        ]

        findings = self.engine.validate_income(declared, bank_txs)
        inc_findings = [f for f in findings if f["rule_id"] == "TAX-INC-001"]

        self.assertEqual(len(inc_findings), 1)
        self.assertIn("Declared vs Bank Salary Discrepancy", inc_findings[0]["title"])
        self.assertGreater(inc_findings[0]["details"]["discrepancy"], 1000000.0)

    def test_cash_receipt_single_day_breach_section_269st(self):
        """Cash deposit >= ₹2,00,000 in a single day flags Section 269ST ERROR TAX-CASH-001."""
        bank_txs = [
            {"transaction_date": "2026-04-10", "description": "Cash Deposit Counter", "credit": 150000.0},
            {"transaction_date": "2026-04-10", "description": "CDM Cash Deposit", "credit": 75000.0},
            # Total cash on 2026-04-10 = ₹2,25,000 >= ₹2,00,000
        ]

        findings = self.engine.validate_income({}, bank_txs)
        cash_findings = [f for f in findings if f["rule_id"] == "TAX-CASH-001"]

        self.assertEqual(len(cash_findings), 1)
        self.assertEqual(cash_findings[0]["severity"], "ERROR")
        self.assertIn("Section 269ST", cash_findings[0]["section"])
        self.assertEqual(cash_findings[0]["details"]["cash_receipt_total"], 225000.0)


# ===========================================================================
# 5. Deduction Validation (Chapter VI-A)
# ===========================================================================
class TestDeductionValidation(unittest.TestCase):

    def setUp(self):
        self.engine = TaxRuleEngine(financial_year="2025-26")

    def test_section_80c_cap_exceeded(self):
        """Claiming > ₹1,50,000 under Section 80C flags ERROR TAX-DED-001."""
        claimed = {"80c": 180000.0}
        findings = self.engine.validate_deductions(claimed)
        f_80c = [f for f in findings if f["rule_id"] == "TAX-DED-001"]

        self.assertEqual(len(f_80c), 1)
        self.assertEqual(f_80c[0]["severity"], "ERROR")
        self.assertEqual(f_80c[0]["details"]["disallowed_excess"], 30000.0)

    def test_section_80d_individual_cap_exceeded(self):
        """Claiming > ₹25,000 under Section 80D for normal individual flags ERROR TAX-DED-002."""
        claimed = {"80d": 35000.0}
        findings = self.engine.validate_deductions(claimed, is_senior_citizen=False)
        f_80d = [f for f in findings if f["rule_id"] == "TAX-DED-002"]

        self.assertEqual(len(f_80d), 1)
        self.assertEqual(f_80d[0]["details"]["disallowed_excess"], 10000.0)

    def test_section_80d_senior_citizen_cap(self):
        """Senior citizens have higher ₹50,000 cap under Section 80D."""
        claimed = {"80d": 45000.0}
        # 45,000 is permitted for seniors, but exceeds standard individual cap
        findings_senior = self.engine.validate_deductions(claimed, is_senior_citizen=True)
        findings_normal = self.engine.validate_deductions(claimed, is_senior_citizen=False)

        self.assertEqual(len(findings_senior), 0)
        self.assertEqual(len(findings_normal), 1)

    def test_section_80ccd_1b_nps_cap_exceeded(self):
        """Claiming > ₹50,000 under Section 80CCD(1B) flags ERROR TAX-DED-003."""
        claimed = {"80ccd_1b": 70000.0}
        findings = self.engine.validate_deductions(claimed)
        f_nps = [f for f in findings if f["rule_id"] == "TAX-DED-003"]

        self.assertEqual(len(f_nps), 1)
        self.assertEqual(f_nps[0]["details"]["disallowed_excess"], 20000.0)

    def test_section_80tta_interest_cap_exceeded(self):
        """Claiming > ₹10,000 savings interest deduction under Section 80TTA flags ERROR TAX-DED-004."""
        claimed = {"80tta": 18000.0}
        findings = self.engine.validate_deductions(claimed, is_senior_citizen=False)
        f_tta = [f for f in findings if f["rule_id"] == "TAX-DED-004"]

        self.assertEqual(len(f_tta), 1)
        self.assertEqual(f_tta[0]["details"]["disallowed_excess"], 8000.0)

    def test_unsubstantiated_80c_claim_without_proof(self):
        """Large 80C claim with no matching payment transactions flags WARNING TAX-DED-005."""
        claimed = {"80c": 120000.0}
        transactions = [
            {"transaction_date": "2026-04-01", "description": "Restaurant Bill", "debit": 2500.0},
            {"transaction_date": "2026-04-05", "description": "Grocery Store", "debit": 4000.0},
        ]
        findings = self.engine.validate_deductions(claimed, transactions=transactions)
        f_unsupported = [f for f in findings if f["rule_id"] == "TAX-DED-005"]

        self.assertEqual(len(f_unsupported), 1)
        self.assertEqual(f_unsupported[0]["severity"], "WARNING")


# ===========================================================================
# 6. Financial Year Versioning & Configurable Thresholds
# ===========================================================================
class TestFinancialYearConfig(unittest.TestCase):

    def test_fy_versioning_defaults(self):
        self.assertIn("2023-24", DEFAULT_FY_CONFIGS)
        self.assertIn("2024-25", DEFAULT_FY_CONFIGS)
        self.assertIn("2025-26", DEFAULT_FY_CONFIGS)

        engine_2526 = TaxRuleEngine("2025-26")
        self.assertEqual(engine_2526.config["assessment_year"], "2026-27")

        engine_2425 = TaxRuleEngine("2024-25")
        self.assertEqual(engine_2425.config["assessment_year"], "2025-26")

    def test_custom_rule_overrides(self):
        """Custom threshold overrides take precedence over FY defaults."""
        custom_engine = TaxRuleEngine(
            financial_year="2025-26",
            custom_rules={"section_80c_cap": 200000.0},
        )
        self.assertEqual(custom_engine.config["section_80c_cap"], 200000.0)

        # Claiming ₹1,80,000 is now valid under custom limit
        findings = custom_engine.validate_deductions({"80c": 180000.0})
        self.assertEqual(len(findings), 0)


# ===========================================================================
# 7. Comprehensive Pipeline, Scoring & Edge Cases
# ===========================================================================
class TestTaxValidationPipeline(unittest.TestCase):

    def test_perfect_records_score_100(self):
        """Flawless records produce 0 findings, 100 readiness score, and is_filing_ready=True."""
        transactions = [
            {"transaction_date": "2026-04-01", "description": "Salary Credited", "credit": 100000.0},
            {"transaction_date": "2026-04-10", "description": "PPF Deposit 80C", "debit": 50000.0},
        ]
        result = validate_tax_records(
            transactions=transactions,
            claimed_deductions={"80c": 50000.0},
            financial_year="2025-26",
        )
        summary = result["summary"]

        self.assertEqual(summary["total_findings"], 0)
        self.assertEqual(summary["errors_count"], 0)
        self.assertEqual(summary["warnings_count"], 0)
        self.assertEqual(summary["tax_readiness_score"], 100.0)
        self.assertTrue(summary["is_filing_ready"])

    def test_readiness_score_deductions(self):
        """Errors deduct 15 points, warnings deduct 5 points."""
        transactions = [
            # 1 ERROR: missing date
            {"transaction_date": None, "description": "Salary", "amount": 50000.0},
            # 1 WARNING: missing narration
            {"transaction_date": "2026-04-01", "description": "", "amount": 500.0},
        ]
        result = validate_tax_records(transactions=transactions)
        summary = result["summary"]

        self.assertEqual(summary["errors_count"], 1)
        self.assertEqual(summary["warnings_count"], 1)
        self.assertFalse(summary["is_filing_ready"])
        # 100 - 15 - 5 = 80.0
        self.assertEqual(summary["tax_readiness_score"], 80.0)

    def test_dataframe_input_supported(self):
        """Accepts pandas DataFrame inputs safely."""
        df = pd.DataFrame([
            {"transaction_date": "2026-04-01", "description": "Consulting Fee", "amount": 25000.0}
        ])
        result = validate_tax_records(transactions=df)
        self.assertEqual(result["summary"]["errors_count"], 0)

    def test_empty_inputs_handled_cleanly(self):
        """Empty inputs return safe zero-findings result."""
        result = validate_tax_records()
        self.assertEqual(result["summary"]["total_findings"], 0)
        self.assertEqual(result["summary"]["tax_readiness_score"], 100.0)
        self.assertTrue(result["summary"]["is_filing_ready"])


if __name__ == "__main__":
    unittest.main()
