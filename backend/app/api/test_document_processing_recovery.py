import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.documents import process_document


class TestDocumentProcessingRecovery(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.document_id = str(ObjectId())
        self.owner_id = str(ObjectId())
        self.user = {"_id": self.owner_id, "role": "USER"}
        self.other_owner_transaction = {
            "document_id": self.document_id,
            "owner_id": str(ObjectId()),
        }
        self.other_document_transaction = {
            "document_id": str(ObjectId()),
            "owner_id": self.owner_id,
        }
        self.persisted_transactions = [
            self.other_owner_transaction,
            self.other_document_transaction,
        ]

        self.db.documents.find_one.return_value = {
            "_id": ObjectId(self.document_id),
            "owner_id": self.owner_id,
            "file_type": "CSV",
            "filename": "test.csv",
        }
        self.db.transactions.find_one.return_value = None
        self.db.transactions.delete_many.side_effect = self._delete_transactions

    def _save_transactions(self, document_id, owner_id, transactions):
        self.persisted_transactions.extend(
            {
                "document_id": document_id,
                "owner_id": owner_id,
            }
            for _ in transactions
        )
        return len(transactions)

    def _delete_transactions(self, query):
        self.persisted_transactions[:] = [
            transaction
            for transaction in self.persisted_transactions
            if not all(
                transaction.get(key) == value
                for key, value in query.items()
            )
        ]

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_metadata_update_failure_rolls_back_transactions(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_save.side_effect = self._save_transactions
        mock_process.return_value = {
            "transactions": [{"amount": 100}, {"amount": 200}],
            "total_rows": 2,
            "valid_rows": 2,
            "invalid_rows": 0,
            "column_mapping": {},
            "errors": [],
        }
        self.db.documents.update_one.side_effect = RuntimeError(
            "Simulated metadata update failure"
        )

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 500)
        self.db.transactions.delete_many.assert_called_once_with(
            {
                "document_id": self.document_id,
                "owner_id": self.owner_id,
            }
        )
        self.assertEqual(
            self.persisted_transactions,
            [self.other_owner_transaction, self.other_document_transaction],
        )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_rollback_failure_is_reported(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_save.side_effect = self._save_transactions
        mock_process.return_value = {
            "transactions": [{"amount": 100}, {"amount": 200}],
            "total_rows": 2,
            "valid_rows": 2,
            "invalid_rows": 0,
            "column_mapping": {},
            "errors": [],
        }
        self.db.documents.update_one.side_effect = RuntimeError(
            "Simulated metadata update failure"
        )
        self.db.transactions.delete_many.side_effect = RuntimeError(
            "Simulated rollback failure"
        )

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn(
            "Failed to save processed transactions: "
            "Simulated metadata update failure",
            context.exception.detail,
        )
        self.assertIn(
            "Rollback of saved transactions also failed: "
            "Simulated rollback failure",
            context.exception.detail,
        )


if __name__ == "__main__":
    unittest.main()
