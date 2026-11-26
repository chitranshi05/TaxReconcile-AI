"""
backend/app/api/test_missing_income_api.py

Unit tests for Missing Income API endpoints in app.api.documents.
"""

import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.documents import (
    detect_missing_income_endpoint,
    get_document_missing_income_endpoint,
)
from app.schemas.missing_income import MissingIncomeRequest


class TestMissingIncomeAPI(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_detect_missing_income_endpoint(self):
        """Direct detection endpoint returns identified recurring streams and gaps."""
        req = MissingIncomeRequest(
            transactions=[
                {"transaction_date": "2026-04-01", "description": "TCS Salary April", "credit": 80000.0},
                {"transaction_date": "2026-05-01", "description": "TCS Salary May", "credit": 80000.0},
                {"transaction_date": "2026-07-01", "description": "TCS Salary July", "credit": 80000.0},
            ]
        )
        res = detect_missing_income_endpoint(req, current_user=self.current_user)
        self.assertEqual(res["summary"]["recurring_streams_count"], 1)
        self.assertEqual(res["summary"]["missing_periodic_gaps_count"], 1)
        self.assertEqual(len(res["findings"]), 1)
        self.assertEqual(res["findings"][0]["expected_period"], "2026-06")

    def test_get_document_missing_income_invalid_id(self):
        """Invalid document ObjectId raises 400."""
        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_missing_income_endpoint("not-an-id", current_user=self.current_user)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_get_document_missing_income_not_found(self):
        """Missing or unowned document raises 404."""
        valid_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = None

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_missing_income_endpoint(valid_id, current_user=self.current_user)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_get_document_missing_income_success(self):
        """Valid document processes transactions and returns missing income report."""
        doc_id = str(ObjectId())
        doc_record = {
            "_id": ObjectId(doc_id),
            "owner_id": self.user_id,
            "filename": "bank_statement.csv",
            "status": "PROCESSED",
        }
        self.mock_db.documents.find_one.return_value = doc_record

        stored_txs = [
            {"document_id": doc_id, "owner_id": self.user_id, "transaction_date": "2026-04-01", "description": "Infosys Salary", "credit": 95000.0},
            {"document_id": doc_id, "owner_id": self.user_id, "transaction_date": "2026-05-01", "description": "Infosys Salary", "credit": 95000.0},
            {"document_id": doc_id, "owner_id": self.user_id, "transaction_date": "2026-07-01", "description": "Infosys Salary", "credit": 95000.0},
        ]
        self.mock_db.transactions.find.return_value.sort.return_value = stored_txs

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            res = get_document_missing_income_endpoint(doc_id, current_user=self.current_user)

        self.assertEqual(res["document_id"], doc_id)
        self.assertEqual(res["summary"]["missing_periodic_gaps_count"], 1)
        self.assertEqual(res["findings"][0]["expected_period"], "2026-06")


if __name__ == "__main__":
    unittest.main()

