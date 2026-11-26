"""
backend/app/api/test_semantic_matching_api.py

Unit tests for semantic matching API endpoints in app.api.documents.
"""

import unittest
from bson import ObjectId

from app.api.documents import (
    compute_semantic_similarity_endpoint,
    compare_semantic_batch_endpoint,
)
from app.schemas.semantic_matching import (
    SemanticSimilarityRequest,
    SemanticBatchCompareRequest,
)


class TestSemanticMatchingAPI(unittest.TestCase):
    """Test suite for semantic similarity and compare route handlers."""

    def setUp(self):
        self.user_id = str(ObjectId())
        self.current_user = {"_id": self.user_id, "role": "USER"}

    def test_semantic_similarity_endpoint_equivalent_texts(self):
        """Equivalent descriptions yield is_match=True and shared concepts."""
        req = SemanticSimilarityRequest(
            text1="Office premises lease rental",
            text2="Rent payment property",
            semantic_threshold=70.0,
        )
        res = compute_semantic_similarity_endpoint(req, current_user=self.current_user)
        self.assertGreaterEqual(res.similarity_score, 70.0)
        self.assertTrue(res.is_match)
        self.assertIn("Rent", res.matched_concepts)
        self.assertEqual(res.method, "TF-IDF + Domain Synonyms")

    def test_semantic_similarity_endpoint_unrelated_texts(self):
        """Unrelated descriptions yield is_match=False and 0 shared concepts."""
        req = SemanticSimilarityRequest(
            text1="Amazon shopping electronics",
            text2="Zomato food delivery",
            semantic_threshold=70.0,
        )
        res = compute_semantic_similarity_endpoint(req, current_user=self.current_user)
        self.assertLess(res.similarity_score, 40.0)
        self.assertFalse(res.is_match)
        self.assertEqual(res.matched_concepts, [])

    def test_semantic_batch_compare_endpoint(self):
        """Batch compare endpoint ranks candidate descriptions and flags matches."""
        req = SemanticBatchCompareRequest(
            reference_text="Premises lease rental",
            candidates=[
                "Pantry tea coffee grocery",
                "Monthly office rent payment",
                "Air conditioner servicing repair",
            ],
            semantic_threshold=70.0,
        )
        res = compare_semantic_batch_endpoint(req, current_user=self.current_user)
        self.assertEqual(res.reference_text, "Premises lease rental")
        self.assertEqual(res.candidates_count, 3)
        self.assertEqual(res.matches_count, 1)
        self.assertEqual(len(res.results), 3)

        top_match = res.results[0]
        self.assertEqual(top_match.candidate, "Monthly office rent payment")
        self.assertTrue(top_match.is_match)
        self.assertIn("Rent", top_match.matched_concepts)

    def test_batch_compare_with_strict_threshold(self):
        """High threshold filters out candidates whose similarity is lower."""
        req = SemanticBatchCompareRequest(
            reference_text="Premises lease rental",
            candidates=["Monthly office rent payment"],
            semantic_threshold=99.0,
        )
        res = compare_semantic_batch_endpoint(req, current_user=self.current_user)
        self.assertEqual(res.matches_count, 0)
        self.assertFalse(res.results[0].is_match)


if __name__ == "__main__":
    unittest.main()
