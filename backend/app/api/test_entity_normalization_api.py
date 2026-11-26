"""
app/api/test_entity_normalization_api.py

Unit tests for description normalization and entity extraction route handlers.
"""

import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException

from app.api.documents import (
    normalize_description_endpoint,
    get_document_entities,
)
from app.schemas.entity_normalization import NormalizeDescriptionRequest


class TestEntityNormalizationAPI(unittest.TestCase):
    """Test suite for document entity normalization route functions."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_normalize_description_endpoint(self):
        """Endpoint accurately cleans description and extracts entity."""
        req = NormalizeDescriptionRequest(
            description="UPI/512391203912/Swiggy Bangalore/swiggy@icici/Food order"
        )
        res = normalize_description_endpoint(req, current_user=self.current_user)
        self.assertEqual(res["channel"], "UPI")
        self.assertEqual(res["normalized_entity"], "Swiggy")
        self.assertEqual(res["reference_id"], "512391203912")

    def test_get_document_entities_invalid_id(self):
        """Invalid ObjectId raises 400."""
        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_entities(
                    document_id="invalid-id",
                    current_user=self.current_user,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_get_document_entities_not_found(self):
        """Document not found raises 404."""
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = None

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            with self.assertRaises(HTTPException) as ctx:
                get_document_entities(
                    document_id=doc_id,
                    current_user=self.current_user,
                )
            self.assertEqual(ctx.exception.status_code, 404)

    def test_get_document_entities_success(self):
        """Valid document returns list of normalized entities."""
        doc_id = str(ObjectId())
        self.mock_db.documents.find_one.return_value = {
            "_id": ObjectId(doc_id),
            "owner_id": self.user_id,
            "filename": "bank.csv",
        }
        self.mock_db.transactions.find.return_value.sort.return_value = [
            {"description": "UPI/123456789012/Zomato/zomato@hdfc/Food"},
            {"description": "NEFT-N987654321012-INFOSYS-SALARY"},
        ]

        with patch("app.api.documents.get_database", return_value=self.mock_db):
            res = get_document_entities(
                document_id=doc_id,
                current_user=self.current_user,
            )

        self.assertEqual(res["document_id"], doc_id)
        self.assertEqual(res["transaction_count"], 2)
        self.assertEqual(res["entities"][0]["normalized_entity"], "Zomato")
        self.assertEqual(res["entities"][1]["normalized_entity"], "Infosys")


if __name__ == "__main__":
    unittest.main()
