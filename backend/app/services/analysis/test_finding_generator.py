"""
backend/app/services/analysis/test_finding_generator.py

Unit tests for FindingGenerator.
"""

import unittest
from app.services.analysis.finding_generator import FindingGenerator


class TestFindingGenerator(unittest.TestCase):
    def test_generate_from_reconciliation(self):
        rec_res = {
            "matches": [
                {
                    "status": "AMOUNT_MISMATCH",
                    "amount_variance": 1200.0,
                    "bank_transaction": {"transaction_date": "2026-04-01", "amount": 10000.0},
                    "ledger_transaction": {"transaction_date": "2026-04-01", "amount": 8800.0},
                },
                {
                    "status": "POTENTIAL_MATCH",
                    "amount_variance": 0.0,
                    "bank_transaction": {"transaction_date": "2026-04-05", "amount": 5000.0},
                    "ledger_transaction": {"transaction_date": "2026-04-06", "amount": 5000.0},
                },
            ],
            "bank_only": [{"transaction_date": "2026-04-10", "amount": 25000.0}],
            "ledger_only": [{"transaction_date": "2026-04-15", "amount": 12000.0}],
        }

        findings = FindingGenerator.generate_findings_from_reconciliation(rec_res)
        self.assertEqual(len(findings), 4)

        categories = [f["category"] for f in findings]
        self.assertTrue(all(c == "RECONCILIATION_DISCREPANCY" for c in categories))

        titles = [f["title"] for f in findings]
        self.assertTrue(any("Amount Mismatch" in t for t in titles))
        self.assertTrue(any("Unrecorded Bank" in t for t in titles))
        self.assertTrue(any("Uncleared Ledger" in t for t in titles))
        self.assertTrue(any("Potential Match" in t for t in titles))

    def test_generate_from_anomalies(self):
        anomaly_res = {
            "anomalies": [
                {
                    "amount": 2000000.0,
                    "anomaly_flags": ["UNUSUALLY_LARGE_AMOUNT"],
                },
                {
                    "amount": 50000.0,
                    "anomaly_flags": ["REPEATED_ROUND_AMOUNT"],
                },
                {
                    "amount": 100000.0,
                    "is_ml_anomaly": True,
                },
            ]
        }

        findings = FindingGenerator.generate_findings_from_anomalies(anomaly_res)
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(f["category"] == "TRANSACTION_ANOMALY" for f in findings))

    def test_generate_unified_portfolio(self):
        rec_res = {
            "matches": [
                {
                    "status": "AMOUNT_MISMATCH",
                    "amount_variance": 500.0,
                    "bank_transaction": {"transaction_date": "2026-04-01", "amount": 5000.0},
                    "ledger_transaction": {"transaction_date": "2026-04-01", "amount": 4500.0},
                }
            ],
            "bank_only": [],
            "ledger_only": [],
        }
        tax_findings = [
            {
                "rule_id": "TAX-DED-001",
                "severity": "ERROR",
                "title": "Section 80C Ceiling Exceeded",
                "description": "Claim exceeds limit.",
                "section": "Section 80C",
                "details": {"disallowed_excess": 25000.0},
                "remediation": "Cap deduction at limit.",
            }
        ]

        portfolio = FindingGenerator.generate_unified_portfolio(
            reconciliation_result=rec_res,
            tax_validation_findings=tax_findings,
        )

        summary = portfolio["summary"]
        self.assertEqual(summary["total_findings"], 2)
        self.assertEqual(summary["total_financial_impact"], 25500.0)
        self.assertEqual(summary["overall_audit_status"], "ACTION_REQUIRED")


if __name__ == "__main__":
    unittest.main()

