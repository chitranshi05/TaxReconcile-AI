import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.documents import get_document_anomalies
from app.api.anomalies import analyze_transaction_anomalies
from app.schemas.anomaly import AnomalyDetectionRequest


class TestAnomaliesAPI(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_document_anomalies_invalid_id(self):
        """Invalid ObjectId raises 400."""
        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_anomalies(
                    document_id="invalid-id",
                    current_user=self.current_user,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Invalid document ID", ctx.exception.detail)

    def test_document_anomalies_not_found(self):
        """Document not found or unauthorized raises 404."""
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = None

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_anomalies(
                    document_id=doc_id,
                    current_user=self.current_user,
                )
            self.assertEqual(ctx.exception.status_code, 404)

    def test_document_anomalies_success(self):
        """Valid document returns anomaly detection results with formatted dates."""
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = {
            "_id": ObjectId(doc_id),
            "owner_id": self.user_id,
            "filename": "bank_statement.csv",
        }

        mock_transactions = [
            {"transaction_date": "2026-04-01", "description": "Coffee", "amount": 200.0, "source_row": 2},
            {"transaction_date": "2026-04-02", "description": "Lunch", "amount": 500.0, "source_row": 3},
            {"transaction_date": "2026-04-03", "description": "Groceries", "amount": 1200.0, "source_row": 4},
            {"transaction_date": "2026-04-04", "description": "Utilities", "amount": 1500.0, "source_row": 5},
            {"transaction_date": "2026-04-05", "description": "Huge Outlier", "amount": 500000.0, "source_row": 6},
        ]
        self.mock_db.transactions.find.return_value.sort.return_value = mock_transactions

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            res = get_document_anomalies(
                document_id=doc_id,
                current_user=self.current_user,
            )

            self.assertEqual(res["document_id"], doc_id)
            self.assertEqual(res["filename"], "bank_statement.csv")
            self.assertEqual(res["total_transactions"], 5)
            self.assertGreaterEqual(res["anomalous_transactions_count"], 1)
            self.assertIn("UNUSUALLY_LARGE_AMOUNT", res["flag_counts"])

    def test_direct_anomaly_detect_endpoint(self):
        """POST /api/anomalies/detect runs directly on provided transactions."""
        req = AnomalyDetectionRequest(
            transactions=[
                {"transaction_date": "2026-04-01", "description": "Tx 1", "amount": 2000.0},
                {"transaction_date": "2026-04-02", "description": "Tx 2", "amount": 3000.0},
                {"transaction_date": "2026-04-03", "description": "Tx 3", "amount": 4000.0},
                {"transaction_date": "2026-04-04", "description": "Tx 4", "amount": 5000.0},
                {"transaction_date": "2026-04-05", "description": "Outlier", "amount": 500000.0},
            ],
            iqr_multiplier=1.5,
        )

        res = analyze_transaction_anomalies(request=req, current_user=self.current_user)
        self.assertEqual(res["total_transactions"], 5)
        self.assertGreaterEqual(res["anomalous_transactions_count"], 1)
        self.assertEqual(res["anomalies"][0]["amount"], 500000.0)
        self.assertEqual(res["anomalies"][0]["severity"], "HIGH")


if __name__ == "__main__":
    unittest.main()
