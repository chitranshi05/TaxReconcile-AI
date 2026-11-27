"""
backend/app/services/reconciliation/test_semantic_matcher.py

Unit tests for SemanticMatcher and semantic description similarity computation.
"""

import unittest

from app.services.reconciliation.semantic_matcher import (
    SemanticMatcher,
    compute_semantic_similarity,
    get_shared_concepts,
)


class TestSemanticMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = SemanticMatcher(semantic_threshold=70.0)

    def test_identical_descriptions_score_100(self):
        score = self.matcher.compute_similarity(
            "Amazon Seller Services Private Limited",
            "Amazon Seller Services Private Limited",
        )
        self.assertEqual(score, 100.0)

    def test_empty_and_none_descriptions(self):
        self.assertEqual(self.matcher.compute_similarity("", ""), 100.0)
        self.assertEqual(self.matcher.compute_similarity(None, None), 100.0)
        self.assertEqual(self.matcher.compute_similarity("Some text", ""), 0.0)
        self.assertEqual(self.matcher.compute_similarity(None, "Some text"), 0.0)

    def test_rent_and_lease_equivalence(self):
        desc1 = "Office premises lease rental"
        desc2 = "Rent payment property"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Rent", concepts)

    def test_salary_and_payroll_equivalence(self):
        desc1 = "Staff payroll wages credit"
        desc2 = "Employee salary disbursement May"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Salary", concepts)

    def test_consulting_and_advisory_equivalence(self):
        desc1 = "Legal and professional consulting fees"
        desc2 = "Law advisory retainer charges"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Professional", concepts)

    def test_cloud_and_hosting_equivalence(self):
        desc1 = "Cloud server hosting subscription"
        desc2 = "AWS infrastructure cloud charges"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Software", concepts)

    def test_utilities_equivalence(self):
        desc1 = "Electricity utility bill"
        desc2 = "Power BESCOM payment"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertGreaterEqual(score, 70.0)
        self.assertIn("Utility", concepts)

    def test_unrelated_descriptions_score_low(self):
        desc1 = "Amazon shopping electronics"
        desc2 = "Zomato food delivery"
        score = self.matcher.compute_similarity(desc1, desc2)
        concepts = self.matcher.extract_matched_concepts(desc1, desc2)

        self.assertLess(score, 40.0)
        self.assertEqual(concepts, [])

    def test_stripping_banking_reference_noise(self):
        desc1 = "NEFT-N12345678901234-Rent payment"
        desc2 = "UPI/987654321098/Office premises lease"
        score = self.matcher.compute_similarity(desc1, desc2)
        self.assertGreaterEqual(score, 70.0)

    def test_pairwise_ranking(self):
        ref = "Premises lease rental"
        candidates = [
            "Unrelated tea coffee pantry",
            "Monthly office rent payment",
            "Air conditioner servicing repair",
        ]
        results = self.matcher.compare_pairwise(ref, candidates)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["candidate"], "Monthly office rent payment")
        self.assertTrue(results[0]["is_match"])
        self.assertIn("Rent", results[0]["matched_concepts"])
        self.assertFalse(results[1]["is_match"])
        self.assertFalse(results[2]["is_match"])

    def test_custom_threshold(self):
        strict_matcher = SemanticMatcher(semantic_threshold=95.0)
        desc1 = "Office premises lease rental"
        desc2 = "Rent payment property"
        score = strict_matcher.compute_similarity(desc1, desc2)
        # Score is around 76%, so below strict 95% threshold
        self.assertLess(score, 95.0)

    def test_module_convenience_functions(self):
        score = compute_semantic_similarity(
            "Software license subscription",
            "SaaS cloud hosting",
        )
        self.assertGreaterEqual(score, 70.0)
        concepts = get_shared_concepts(
            "Software license subscription",
            "SaaS cloud hosting",
        )
        self.assertIn("Software", concepts)


if __name__ == "__main__":
    unittest.main()

