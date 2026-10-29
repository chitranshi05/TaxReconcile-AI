import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.reconciliation import run_reconciliation
from app.schemas.reconciliation import ReconciliationRequest


class TestReconciliationAPI(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_reconcile_self_document_rejected(self):
        """Cannot reconcile a document with itself."""
        doc_id = str(ObjectId())
        req = ReconciliationRequest(bank_document_id=doc_id, ledger_document_id=doc_id)

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                run_reconciliation(req, self.current_user)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Cannot reconcile a document with itself", ctx.exception.detail)

    def test_reconcile_unauthorized_document(self):
        """User cannot reconcile documents they don't own."""
        bank_id = str(ObjectId())
        ledger_id = str(ObjectId())
        req = ReconciliationRequest(bank_document_id=bank_id, ledger_document_id=ledger_id)

        self.mock_db.documents.find_one.return_value = None

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                run_reconciliation(req, self.current_user)
            self.assertEqual(ctx.exception.status_code, 404)
            self.assertIn("Bank document not found", ctx.exception.detail)

    def test_successful_reconciliation_run(self):
        """Valid bank & ledger documents produce matches and persist to database."""
        bank_id = str(ObjectId())
        ledger_id = str(ObjectId())
        req = ReconciliationRequest(
            bank_document_id=bank_id,
            ledger_document_id=ledger_id,
            date_tolerance_days=1,
            amount_tolerance=0.0,
        )

        self.mock_db.documents.find_one.side_effect = [
            {"_id": ObjectId(bank_id), "owner_id": self.user_id, "filename": "bank.csv"},
            {"_id": ObjectId(ledger_id), "owner_id": self.user_id, "filename": "ledger.csv"},
        ]

        bank_txs = [
            {"transaction_date": "2026-04-01", "description": "Salary", "amount": 50000.0, "source_row": 2},
            {"transaction_date": "2026-04-05", "description": "Bank Fee", "amount": 250.0, "source_row": 3},
        ]
        ledger_txs = [
            {"transaction_date": "2026-04-01", "description": "Salary", "amount": 50000.0, "source_row": 10},
            {"transaction_date": "2026-04-06", "description": "Software", "amount": 1200.0, "source_row": 11},
        ]

        self.mock_db.transactions.find.return_value.sort.side_effect = [
            bank_txs,
            ledger_txs,
        ]

        fake_rec_id = ObjectId()
        self.mock_db.reconciliations.insert_one.return_value.inserted_id = fake_rec_id

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            response = run_reconciliation(req, self.current_user)

            self.assertEqual(response["reconciliation_id"], str(fake_rec_id))
            self.assertEqual(response["summary"]["matched_count"], 1)
            self.assertEqual(response["summary"]["bank_only_count"], 1)
            self.assertEqual(response["summary"]["ledger_only_count"], 1)
            self.assertEqual(len(response["matches"]), 1)
            self.assertEqual(response["matches"][0]["status"], "MATCHED")

            self.mock_db.reconciliations.insert_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()
