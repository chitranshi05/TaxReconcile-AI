import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.reconciliation import (
    get_reconciliation,
    list_reconciliations,
    run_reconciliation,
)
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

        self.mock_db.documents.find_one.side_effect = [
            {"_id": ObjectId(bank_id), "owner_id": self.user_id},
            None,
        ]

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                run_reconciliation(req, self.current_user)
            self.assertEqual(ctx.exception.status_code, 404)
            self.assertIn("Ledger document not found", ctx.exception.detail)
            self.assertEqual(
                self.mock_db.documents.find_one.call_args_list[1].args[0],
                {"_id": ObjectId(ledger_id), "owner_id": self.user_id},
            )

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
            self.assertEqual(
                self.mock_db.reconciliations.insert_one.call_args.args[0]["owner_id"],
                self.user_id,
            )

    def test_admin_cannot_reconcile_documents_with_different_owners(self):
        """ADMIN access does not permit reconciling different owners' documents."""
        bank_id = str(ObjectId())
        ledger_id = str(ObjectId())
        req = ReconciliationRequest(
            bank_document_id=bank_id,
            ledger_document_id=ledger_id,
        )
        admin = {"_id": self.user_id, "role": "ADMIN"}
        self.mock_db.documents.find_one.side_effect = [
            {"_id": ObjectId(bank_id), "owner_id": str(ObjectId())},
            {"_id": ObjectId(ledger_id), "owner_id": str(ObjectId())},
        ]

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                run_reconciliation(req, admin)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.detail,
            "Both documents must belong to the same owner.",
        )
        self.mock_db.transactions.find.assert_not_called()
        self.mock_db.reconciliations.insert_one.assert_not_called()

    def test_admin_can_reconcile_documents_with_same_owner(self):
        """ADMIN can reconcile documents belonging to the same non-admin owner."""
        bank_id = str(ObjectId())
        ledger_id = str(ObjectId())
        owner_id = str(ObjectId())
        req = ReconciliationRequest(
            bank_document_id=bank_id,
            ledger_document_id=ledger_id,
        )
        admin = {"_id": self.user_id, "role": "ADMIN"}
        self.mock_db.documents.find_one.side_effect = [
            {
                "_id": ObjectId(bank_id),
                "owner_id": owner_id,
                "filename": "bank.csv",
            },
            {
                "_id": ObjectId(ledger_id),
                "owner_id": owner_id,
                "filename": "ledger.csv",
            },
        ]
        self.mock_db.transactions.find.return_value.sort.side_effect = [
            [{"transaction_date": "2026-04-01", "amount": 100.0}],
            [{"transaction_date": "2026-04-01", "amount": 100.0}],
        ]
        fake_rec_id = ObjectId()
        self.mock_db.reconciliations.insert_one.return_value.inserted_id = fake_rec_id

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            response = run_reconciliation(req, admin)

        self.assertEqual(response["reconciliation_id"], str(fake_rec_id))
        saved_record = self.mock_db.reconciliations.insert_one.call_args.args[0]
        self.assertEqual(saved_record["owner_id"], owner_id)
        self.mock_db.transactions.find.assert_any_call(
            {"document_id": bank_id, "owner_id": owner_id},
            {"_id": 0},
        )
        self.mock_db.transactions.find.assert_any_call(
            {"document_id": ledger_id, "owner_id": owner_id},
            {"_id": 0},
        )
        self.mock_db.reconciliations.insert_one.assert_called_once()

        saved_record["_id"] = fake_rec_id
        self.mock_db.reconciliations.find_one.return_value = saved_record.copy()
        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            retrieved_record = get_reconciliation(
                str(fake_rec_id),
                {"_id": owner_id, "role": "USER"},
            )

        self.assertEqual(retrieved_record["owner_id"], owner_id)
        self.mock_db.reconciliations.find_one.assert_called_once_with(
            {"_id": fake_rec_id, "owner_id": owner_id}
        )

    def test_user_cannot_retrieve_another_users_reconciliation(self):
        """USER detail and list queries are restricted to their own records."""
        reconciliation_id = ObjectId()
        self.mock_db.reconciliations.find_one.return_value = None

        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_reconciliation(str(reconciliation_id), self.current_user)

            self.assertEqual(ctx.exception.status_code, 404)
            self.assertEqual(
                ctx.exception.detail,
                "Reconciliation record not found.",
            )

            self.mock_db.reconciliations.find.return_value.sort.return_value = []
            listed = list_reconciliations(self.current_user)

        self.assertEqual(listed, {"count": 0, "reconciliations": []})
        self.mock_db.reconciliations.find_one.assert_called_once_with(
            {"_id": reconciliation_id, "owner_id": self.user_id}
        )
        self.mock_db.reconciliations.find.assert_called_once_with(
            {"owner_id": self.user_id}
        )

    def test_reconciliation_id_validation_and_missing_record_responses(self):
        """Invalid and missing reconciliation IDs retain their existing responses."""
        with patch("app.api.reconciliation.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as invalid_ctx:
                get_reconciliation("invalid-id", self.current_user)

            self.assertEqual(invalid_ctx.exception.status_code, 400)
            self.assertEqual(
                invalid_ctx.exception.detail,
                "Invalid reconciliation_id.",
            )

            self.mock_db.reconciliations.find_one.return_value = None
            with self.assertRaises(HTTPException) as missing_ctx:
                get_reconciliation(str(ObjectId()), self.current_user)

        self.assertEqual(missing_ctx.exception.status_code, 404)
        self.assertEqual(
            missing_ctx.exception.detail,
            "Reconciliation record not found.",
        )


if __name__ == "__main__":
    unittest.main()
