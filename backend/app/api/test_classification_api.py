"""
app/api/test_classification_api.py

Unit tests for transaction classification API endpoints.
"""

import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.documents import (
    classify_single_transaction_endpoint,
    classify_batch_endpoint,
    get_document_classification,
)
from app.schemas.classification import (
    ClassifyTransactionRequest,
    ClassifyBatchRequest,
)


class TestClassificationAPI(unittest.TestCase):
    """Test suite for classification route handlers."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_classify_single_transaction(self):
        """Single transaction endpoint returns category and tax head."""
        req = ClassifyTransactionRequest(
            description="Swiggy Bangalore Food delivery",
            debit=350.0,
        )
        res = classify_single_transaction_endpoint(req, current_user=self.current_user)
        self.assertEqual(res["category"], "FOOD_AND_DINING")
        self.assertEqual(res["tax_head"], "PERSONAL_NON_DEDUCTIBLE")
        self.assertFalse(res["is_tax_deductible"])

    def test_classify_batch_endpoint(self):
        """Batch endpoint returns enriched items and summary stats."""
        req = ClassifyBatchRequest(
            transactions=[
                ClassifyTransactionRequest(description="Infosys Salary April", credit=90000.0),
                ClassifyTransactionRequest(description="Uber Mumbai rides", debit=450.0),
            ]
        )
        res = classify_batch_endpoint(req, current_user=self.current_user)
        self.assertIn("summary", res)
        self.assertEqual(res["summary"]["total_transactions"], 2)
        self.assertEqual(res["summary"]["total_income"], 90000.0)
        self.assertEqual(res["summary"]["total_deductible_expense"], 450.0)

    def test_get_document_classification_invalid_id(self):
        """Invalid ObjectId raises 400."""
        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_classification("bad-id", current_user=self.current_user)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_get_document_classification_success(self):
        """Stored document transactions are classified with summary metrics."""
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = {
            "_id": ObjectId(doc_id),
            "owner_id": self.user_id,
            "filename": "ledger.csv",
        }
        self.mock_db.transactions.find.return_value.sort.return_value = [
            {"description": "WeWork office rent", "debit": 25000.0},
            {"description": "Airtel broadband", "debit": 1500.0},
        ]

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            res = get_document_classification(doc_id, current_user=self.current_user)

        self.assertEqual(res["document_id"], doc_id)
        self.assertEqual(res["summary"]["total_transactions"], 2)
        self.assertEqual(res["summary"]["total_deductible_expense"], 26500.0)


if __name__ == "__main__":
    unittest.main()
