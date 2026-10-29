import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.tax_validation import (
    get_tax_rules_for_fy,
    list_tax_rules,
    run_direct_tax_validation,
    validate_document_tax_compliance,
)
from app.schemas.tax_validation import (
    DocumentTaxValidationRequest,
    TaxValidationRequest,
)


class TestTaxValidationAPI(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_list_tax_rules(self):
        res = list_tax_rules()
        self.assertIn("2025-26", res["supported_financial_years"])
        self.assertIn("2024-25", res["supported_financial_years"])
        self.assertIn("rules_by_fy", res)

    def test_get_tax_rules_for_fy_valid(self):
        res = get_tax_rules_for_fy("2025-26")
        self.assertEqual(res["financial_year"], "2025-26")
        self.assertEqual(res["rules"]["section_80c_cap"], 150000.0)

    def test_get_tax_rules_for_fy_invalid(self):
        with self.assertRaises(HTTPException) as ctx:
            get_tax_rules_for_fy("1990-91")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_run_direct_tax_validation_endpoint(self):
        req = TaxValidationRequest(
            financial_year="2025-26",
            claimed_deductions={"80c": 180000.0},  # Exceeds cap
            transactions=[
                {"transaction_date": "2026-04-01", "description": "Consulting", "credit": 50000.0}
            ],
        )
        res = run_direct_tax_validation(request=req, current_user=self.current_user)

        self.assertIn("summary", res)
        self.assertIn("findings", res)
        self.assertEqual(res["summary"]["errors_count"], 1)
        self.assertEqual(res["findings"][0]["rule_id"], "TAX-DED-001")

    def test_document_tax_validation_invalid_id(self):
        req = DocumentTaxValidationRequest(financial_year="2025-26")
        with patch("app.api.tax_validation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                validate_document_tax_compliance("bad-id", req, self.current_user)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_document_tax_validation_not_found(self):
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = None
        req = DocumentTaxValidationRequest(financial_year="2025-26")

        with patch("app.api.tax_validation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                validate_document_tax_compliance(doc_id, req, self.current_user)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_document_tax_validation_success(self):
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = {
            "_id": ObjectId(doc_id),
            "owner_id": self.user_id,
            "filename": "ledger_fy26.csv",
        }
        self.mock_db.transactions.find.return_value.sort.return_value = [
            {"transaction_date": "2026-04-01", "description": "Salary Credited", "credit": 100000.0},
            {"transaction_date": "2026-04-05", "description": "PPF Payment 80C", "debit": 50000.0},
        ]

        req = DocumentTaxValidationRequest(
            financial_year="2025-26",
            claimed_deductions={"80c": 50000.0},
        )

        with patch("app.api.tax_validation.get_database", return_value=self.mock_db):
            res = validate_document_tax_compliance(doc_id, req, self.current_user)
            self.assertEqual(res["document_id"], doc_id)
            self.assertEqual(res["summary"]["errors_count"], 0)
            self.assertTrue(res["summary"]["is_filing_ready"])
            self.assertEqual(res["summary"]["tax_readiness_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
