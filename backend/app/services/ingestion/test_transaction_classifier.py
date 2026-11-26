"""
app/services/ingestion/test_transaction_classifier.py

Unit tests for Financial Transaction Classification Engine.
"""

import unittest

from app.services.ingestion.transaction_classifier import (
    TransactionClassifier,
    TransactionCategory,
    TaxHead,
    classify_transaction,
    classify_transactions,
    summarize_classification,
)


class TestTransactionClassifier(unittest.TestCase):
    """Test suite for financial categorization and tax head mapping."""

    def setUp(self):
        self.classifier = TransactionClassifier()

    def test_swiggy_food_and_dining(self):
        """Food delivery via Swiggy is categorized as FOOD_AND_DINING (non-deductible personal)."""
        tx = {"description": "UPI/512391203912/Swiggy Bangalore/swiggy@icici/Food", "debit": 480.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.FOOD_AND_DINING.value)
        self.assertEqual(res.sub_category, "Food Delivery")
        self.assertEqual(res.tax_head, TaxHead.PERSONAL_NON_DEDUCTIBLE.value)
        self.assertFalse(res.is_tax_deductible)
        self.assertGreaterEqual(res.confidence_score, 0.90)

    def test_uber_travel_conveyance(self):
        """Cab ride via Uber is categorized as TRAVEL_AND_CONVEYANCE (business deductible)."""
        tx = {"description": "UBER INDIA RIDES MUMBAI", "debit": 350.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.TRAVEL_AND_CONVEYANCE.value)
        self.assertEqual(res.tax_head, TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value)
        self.assertTrue(res.is_tax_deductible)

    def test_salary_credit_inflow(self):
        """Salary credit is mapped to SALARY category and INCOME_FROM_SALARY tax head."""
        tx = {"description": "NEFT-N123456789012-INFOSYS-SALARY APR 2026", "credit": 85000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.SALARY.value)
        self.assertEqual(res.tax_head, TaxHead.INCOME_FROM_SALARY.value)
        self.assertIsNone(res.is_tax_deductible)
        self.assertGreaterEqual(res.confidence_score, 0.90)

    def test_payroll_expense_debit(self):
        """Payroll debit to staff is categorized as deductible salary expense."""
        tx = {"description": "Staff Payroll and monthly salary disbursement", "debit": 150000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.SALARY.value)
        self.assertEqual(res.sub_category, "Payroll Expense")
        self.assertEqual(res.tax_head, TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value)
        self.assertTrue(res.is_tax_deductible)

    def test_professional_legal_consulting_fee(self):
        """Consultancy and legal fee payments are categorized as PROFESSIONAL_FEES."""
        tx = {"description": "Quarterly legal consulting fee retainer", "debit": 25000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.PROFESSIONAL_FEES.value)
        self.assertEqual(res.tax_head, TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value)
        self.assertTrue(res.is_tax_deductible)

    def test_office_rent_expense(self):
        """Office rent and coworking payments are categorized as RENT_EXPENSE."""
        tx = {"description": "WeWork monthly coworking office rent", "debit": 40000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.RENT_EXPENSE.value)
        self.assertEqual(res.tax_head, TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value)
        self.assertTrue(res.is_tax_deductible)

    def test_utilities_telecom(self):
        """Telecom and internet bills via Airtel/Jio map to UTILITIES."""
        tx = {"description": "BHARTI AIRTEL BROADBAND BILL", "debit": 1499.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.UTILITIES.value)
        self.assertEqual(res.tax_head, TaxHead.BUSINESS_EXPENSE_DEDUCTIBLE.value)
        self.assertTrue(res.is_tax_deductible)

    def test_interest_income(self):
        """Bank interest credit maps to INTEREST_INCOME and INCOME_FROM_OTHER_SOURCES."""
        tx = {"description": "INT.PD 01-04-2026 TO 30-06-2026", "credit": 3450.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.INTEREST_INCOME.value)
        self.assertEqual(res.tax_head, TaxHead.INCOME_FROM_OTHER_SOURCES.value)

    def test_statutory_tax_payment(self):
        """Income tax challan maps to TAX_PAYMENT and STATUTORY_TAX_PAYMENT."""
        tx = {"description": "INCOME TAX PAYMENT CHALLAN 280 ITNS", "debit": 15000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.TAX_PAYMENT.value)
        self.assertEqual(res.tax_head, TaxHead.STATUTORY_TAX_PAYMENT.value)

    def test_atm_cash_withdrawal(self):
        """Cash withdrawal at ATM is mapped to TRANSFERS_AND_CONTRA."""
        tx = {"description": "ATM WDL HDFC000123 CASH WITHDRAWAL", "debit": 5000.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.TRANSFERS_AND_CONTRA.value)
        self.assertEqual(res.sub_category, "Cash Withdrawal")

    def test_digital_entertainment(self):
        """Netflix subscription maps to ENTERTAINMENT."""
        tx = {"description": "ACH D- NETFLIX ENTERTAINMENT SERVICES", "debit": 649.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.ENTERTAINMENT.value)
        self.assertEqual(res.tax_head, TaxHead.PERSONAL_NON_DEDUCTIBLE.value)

    def test_uncategorized_ambiguous(self):
        """Unrecognized generic text falls back to UNCATEGORIZED with low confidence."""
        tx = {"description": "MISC RANDOM REMITTANCE REF 999", "debit": 100.0}
        res = self.classifier.classify(tx)

        self.assertEqual(res.category, TransactionCategory.UNCATEGORIZED.value)
        self.assertEqual(res.tax_head, TaxHead.NOT_APPLICABLE.value)
        self.assertLessEqual(res.confidence_score, 0.50)

    def test_batch_classification_and_summary(self):
        """classify_transactions and summarize_classification aggregate financial metrics."""
        transactions = [
            {"description": "NEFT-INFOSYS-SALARY", "credit": 80000.0},
            {"description": "Swiggy Bangalore", "debit": 500.0},
            {"description": "WeWork office rent", "debit": 20000.0},
            {"description": "Uber rides Mumbai", "debit": 1500.0},
            {"description": "ATM CASH WDL", "debit": 2000.0},
        ]

        classified = classify_transactions(transactions)
        self.assertEqual(len(classified), 5)
        self.assertIn("category", classified[0])

        summary = summarize_classification(classified)
        self.assertEqual(summary["total_transactions"], 5)
        self.assertEqual(summary["categorized_count"], 5)
        self.assertEqual(summary["category_coverage_rate"], 100.0)
        self.assertEqual(summary["total_income"], 80000.0)
        self.assertEqual(summary["total_deductible_expense"], 21500.0)  # Rent (20000) + Uber (1500)
        self.assertEqual(summary["total_non_deductible_expense"], 500.0)  # Swiggy (500)


if __name__ == "__main__":
    unittest.main()

