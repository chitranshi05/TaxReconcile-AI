import unittest
from types import SimpleNamespace
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
            "status": "UPLOADED",
        }
        self.db.transactions.find_one.return_value = None
        self.db.transactions.delete_many.side_effect = self._delete_transactions
        self.db.documents.update_one.side_effect = (
            lambda *args: SimpleNamespace(matched_count=1)
        )

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

    def _process_result(self):
        return {
            "transactions": [
                {"transaction_date": "2026-04-01", "amount": 100},
                {"transaction_date": "2026-04-02", "amount": 200},
            ],
            "total_rows": 2,
            "valid_rows": 2,
            "invalid_rows": 0,
            "column_mapping": {},
            "errors": [],
        }

    def test_xlsx_and_json_processing_use_their_processors_and_audit_success(self):
        cases = (
            ("XLSX", "app.api.documents.process_excel_file", "test.xlsx"),
            ("JSON", "app.api.documents.process_json_file", "test.json"),
        )
        for file_type, processor_path, filename in cases:
            with self.subTest(file_type=file_type):
                self.db.documents.find_one.return_value.update(
                    {"file_type": file_type, "filename": filename, "status": "UPLOADED"}
                )
                self.db.documents.update_one.side_effect = (
                    lambda *args: SimpleNamespace(matched_count=1)
                )
                with (
                    patch("app.api.documents.get_database", return_value=self.db),
                    patch(processor_path, return_value=self._process_result()) as processor,
                    patch(
                        "app.api.documents.save_valid_transactions",
                        return_value=2,
                    ) as save_transactions,
                    patch("app.api.documents.log_audit_event") as audit,
                    patch("app.api.documents.UPLOAD_DIR") as upload_dir,
                ):
                    upload_dir.__truediv__.return_value = filename
                    result = process_document(self.document_id, self.user)

                processor.assert_called_once_with(filename)
                save_transactions.assert_called_once()
                self.assertEqual(result["saved_transactions"], 2)
                audit.assert_called_once_with(
                    action="DOCUMENT_PROCESSED",
                    user_id=self.owner_id,
                    resource_type="document",
                    resource_id=self.document_id,
                    details={"saved_transactions": 2},
                )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_metadata_update_failure_rolls_back_transactions(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_save.side_effect = self._save_transactions
        mock_process.return_value = self._process_result()

        def fail_processed_update(query, update):
            if update["$set"]["status"] == "PROCESSED":
                raise RuntimeError("Simulated metadata update failure")
            return SimpleNamespace(matched_count=1)

        self.db.documents.update_one.side_effect = fail_processed_update

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
        self.assertEqual(
            self.db.documents.update_one.call_args_list[0].args[0],
            {"_id": ObjectId(self.document_id), "status": "UPLOADED"},
        )
        self.assertEqual(
            self.db.documents.update_one.call_args_list[1].args[0],
            {"_id": ObjectId(self.document_id), "status": "PENDING"},
        )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_rollback_failure_is_reported(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_save.side_effect = self._save_transactions
        mock_process.return_value = self._process_result()

        def fail_processed_update(query, update):
            if update["$set"]["status"] == "PROCESSED":
                raise RuntimeError("Simulated metadata update failure")
            return SimpleNamespace(matched_count=1)

        self.db.documents.update_one.side_effect = fail_processed_update
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

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_partial_transaction_save_failure_rolls_back_and_marks_failed(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_process.return_value = self._process_result()

        def partially_save_then_fail(document_id, owner_id, transactions):
            self._save_transactions(document_id, owner_id, transactions[:1])
            raise RuntimeError("Simulated partial insert failure")

        mock_save.side_effect = partially_save_then_fail

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("Simulated partial insert failure", context.exception.detail)
        self.assertEqual(
            self.persisted_transactions,
            [self.other_owner_transaction, self.other_document_transaction],
        )
        self.assertEqual(
            self.db.documents.update_one.call_args_list[-1].args[1]["$set"]["status"],
            "FAILED",
        )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_status_update_without_match_rolls_back_transactions(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        mock_process.return_value = self._process_result()
        mock_save.side_effect = self._save_transactions

        def status_update(query, update):
            if update["$set"]["status"] == "PROCESSED":
                return SimpleNamespace(matched_count=0)
            return SimpleNamespace(matched_count=1)

        self.db.documents.update_one.side_effect = status_update

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn(
            "Document status could not be updated to PROCESSED",
            context.exception.detail,
        )
        self.assertEqual(
            self.persisted_transactions,
            [self.other_owner_transaction, self.other_document_transaction],
        )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_concurrent_processing_claim_conflict_returns_409(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        self.db.documents.update_one.side_effect = [
            SimpleNamespace(matched_count=0)
        ]

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 409)
        mock_process.assert_not_called()
        mock_save.assert_not_called()

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_pending_document_is_not_reclaimed_automatically(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        self.db.documents.find_one.return_value["status"] = "PENDING"

        with self.assertRaises(HTTPException) as context:
            process_document(
                document_id=self.document_id,
                current_user=self.user,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.db.documents.update_one.assert_not_called()
        mock_process.assert_not_called()
        mock_save.assert_not_called()

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_existing_transactions_prevent_duplicate_processing(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        self.db.transactions.find_one.return_value = {"_id": ObjectId()}

        with self.assertRaises(HTTPException) as context:
            process_document(
                document_id=self.document_id,
                current_user=self.user,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.db.transactions.find_one.assert_called_once_with(
            {
                "document_id": self.document_id,
                "owner_id": self.owner_id,
            }
        )
        self.db.documents.update_one.assert_not_called()
        mock_process.assert_not_called()
        mock_save.assert_not_called()

    @patch("app.api.documents.log_audit_event")
    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_csv_validation_failure_marks_document_failed(
        self, mock_get_database, mock_save, mock_process, mock_audit
    ):
        mock_get_database.return_value = self.db
        mock_process.side_effect = ValueError("Invalid CSV contents")

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Invalid CSV contents")
        self.assertEqual(
            self.db.documents.update_one.call_args_list[-1].args[1]["$set"]["status"],
            "FAILED",
        )
        self.db.transactions.delete_many.assert_not_called()
        mock_save.assert_not_called()
        mock_audit.assert_called_once_with(
            action="DOCUMENT_PROCESSING_FAILED",
            user_id=self.owner_id,
            resource_type="document",
            resource_id=self.document_id,
            details={"error": "Invalid CSV contents"},
        )

    @patch("app.api.documents.log_audit_event")
    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_failed_document_can_be_retried(
        self, mock_get_database, mock_save, mock_process, mock_audit
    ):
        mock_get_database.return_value = self.db
        self.db.documents.find_one.return_value["status"] = "FAILED"
        failed_attempt_transaction = {
            "document_id": self.document_id,
            "owner_id": self.owner_id,
        }
        self.persisted_transactions.append(failed_attempt_transaction)
        mock_process.return_value = self._process_result()
        mock_save.side_effect = self._save_transactions

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"
            response = process_document(
                document_id=self.document_id,
                current_user=self.user,
            )

        self.assertEqual(response["saved_transactions"], 2)
        self.assertEqual(
            self.db.documents.update_one.call_args_list[0].args[0],
            {"_id": ObjectId(self.document_id), "status": "FAILED"},
        )
        self.assertEqual(
            self.db.documents.update_one.call_args_list[-1].args[0],
            {"_id": ObjectId(self.document_id), "status": "PENDING"},
        )
        self.db.transactions.delete_many.assert_called_once_with(
            {
                "document_id": self.document_id,
                "owner_id": self.owner_id,
            }
        )
        self.assertEqual(
            self.persisted_transactions,
            [self.other_owner_transaction, self.other_document_transaction]
            + [
                {
                    "document_id": self.document_id,
                    "owner_id": self.owner_id,
                }
                for _ in self._process_result()["transactions"]
            ],
        )
        mock_audit.assert_any_call(
            action="DOCUMENT_PROCESSING_RETRIED",
            user_id=self.owner_id,
            resource_type="document",
            resource_id=self.document_id,
        )
        mock_audit.assert_any_call(
            action="DOCUMENT_PROCESSED",
            user_id=self.owner_id,
            resource_type="document",
            resource_id=self.document_id,
            details={"saved_transactions": 2},
        )

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_failed_retry_cleanup_error_does_not_save_new_transactions(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        self.db.documents.find_one.return_value["status"] = "FAILED"
        self.db.transactions.delete_many.side_effect = RuntimeError(
            "Simulated retry cleanup failure"
        )

        with patch("app.api.documents.UPLOAD_DIR") as mock_upload_dir:
            mock_upload_dir.__truediv__.return_value = "test.csv"

            with self.assertRaises(HTTPException) as context:
                process_document(
                    document_id=self.document_id,
                    current_user=self.user,
                )

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("Simulated retry cleanup failure", context.exception.detail)
        mock_process.assert_not_called()
        mock_save.assert_not_called()

    @patch("app.api.documents.process_csv_file")
    @patch("app.api.documents.save_valid_transactions")
    @patch("app.api.documents.get_database")
    def test_user_cannot_process_another_users_document(
        self, mock_get_database, mock_save, mock_process
    ):
        mock_get_database.return_value = self.db
        self.db.documents.find_one.return_value = None

        with self.assertRaises(HTTPException) as context:
            process_document(
                document_id=self.document_id,
                current_user=self.user,
            )

        self.assertEqual(context.exception.status_code, 404)
        self.db.documents.update_one.assert_not_called()
        mock_process.assert_not_called()
        mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
