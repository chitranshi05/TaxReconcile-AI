"""
backend/app/services/analysis/finding_generator.py

Unified Finding Generation Framework.

Transforms disparate anomalies, reconciliation mismatches, tax violations,
and missing income occurrences into a cohesive, structured portfolio of audit findings.
"""

from __future__ import annotations

from typing import Any
from app.services.analysis.risk_scorer import RiskScorer


class FindingGenerator:
    """
    Transforms raw operational discrepancies into standardized, prioritized findings.
    """

    @classmethod
    def generate_findings_from_reconciliation(
        cls,
        reconciliation_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extract structured findings from reconciliation results (amount mismatches,
        bank-only entries, ledger-only entries, and potential matches).
        """
        findings: list[dict[str, Any]] = []
        counter = 1

        matches = reconciliation_result.get("matches", [])
        bank_only = reconciliation_result.get("bank_only", [])
        ledger_only = reconciliation_result.get("ledger_only", [])

        # 1. Amount Mismatches
        mismatches = [m for m in matches if m.get("status") == "AMOUNT_MISMATCH"]
        for m in mismatches:
            variance = abs(float(m.get("amount_variance", 0.0)))
            b_tx = m.get("bank_transaction", {})
            l_tx = m.get("ledger_transaction", {})
            b_amt = abs(float(b_tx.get("amount") or b_tx.get("debit") or b_tx.get("credit") or 0.0))
            l_amt = abs(float(l_tx.get("amount") or l_tx.get("debit") or l_tx.get("credit") or 0.0))

            risk = RiskScorer.score_transaction(m)

            findings.append({
                "finding_id": f"FND-REC-{counter:03d}",
                "category": "RECONCILIATION_DISCREPANCY",
                "severity": "HIGH" if variance >= 5000.0 else "MEDIUM",
                "title": f"Amount Mismatch of ₹{variance:,.2f}",
                "description": (
                    f"Transaction on {b_tx.get('transaction_date')} has differing monetary amounts: "
                    f"Bank statement reports ₹{b_amt:,.2f} while ledger reports ₹{l_amt:,.2f} (Variance: ₹{variance:,.2f})."
                ),
                "financial_impact": round(variance, 2),
                "statutory_reference": None,
                "source": "RECONCILIATION_ENGINE",
                "affected_records": [b_tx, l_tx],
                "remediation": "Investigate bank deduction slip or ledger voucher to identify whether fee, discount, or entry error caused the discrepancy.",
                "risk_score": risk["risk_score"],
            })
            counter += 1

        # 2. Bank-Only Unmatched Entries (Missing in Ledger)
        if bank_only:
            total_bank_only_amt = sum(
                abs(float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0))
                for t in bank_only
            )
            findings.append({
                "finding_id": f"FND-REC-{counter:03d}",
                "category": "RECONCILIATION_DISCREPANCY",
                "severity": "HIGH" if total_bank_only_amt >= 50000.0 else "MEDIUM",
                "title": f"{len(bank_only)} Unrecorded Bank Transaction(s)",
                "description": (
                    f"{len(bank_only)} transaction(s) totalling ₹{total_bank_only_amt:,.2f} appear on the bank "
                    "statement without corresponding entries in the company ledger."
                ),
                "financial_impact": round(total_bank_only_amt, 2),
                "statutory_reference": "Section 68 (Unexplained Credits)",
                "source": "BANK_STATEMENT",
                "affected_records": bank_only[:10],
                "remediation": "Pass missing ledger journal entries to reflect all bank outflows, incoming client remittances, or bank fees.",
                "risk_score": min(85.0, 50.0 + (len(bank_only) * 3)),
            })
            counter += 1

        # 3. Ledger-Only Unmatched Entries (Missing in Bank)
        if ledger_only:
            total_ledger_only_amt = sum(
                abs(float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0))
                for t in ledger_only
            )
            findings.append({
                "finding_id": f"FND-REC-{counter:03d}",
                "category": "RECONCILIATION_DISCREPANCY",
                "severity": "MEDIUM",
                "title": f"{len(ledger_only)} Uncleared Ledger Transaction(s)",
                "description": (
                    f"{len(ledger_only)} entry/entries totalling ₹{total_ledger_only_amt:,.2f} recorded in company "
                    "books have not cleared or credited into the bank statement."
                ),
                "financial_impact": round(total_ledger_only_amt, 2),
                "statutory_reference": None,
                "source": "COMPANY_LEDGER",
                "affected_records": ledger_only[:10],
                "remediation": "Review outstanding cheques issued/received, follow up on uncollected debtor invoices, or write off voided cheques.",
                "risk_score": min(65.0, 35.0 + (len(ledger_only) * 2)),
            })
            counter += 1

        # 4. Ambiguous Potential Matches
        potentials = [m for m in matches if m.get("status") == "POTENTIAL_MATCH"]
        if potentials:
            findings.append({
                "finding_id": f"FND-REC-{counter:03d}",
                "category": "RECONCILIATION_DISCREPANCY",
                "severity": "LOW",
                "title": f"{len(potentials)} Potential Match Candidate(s) Requiring Confirmation",
                "description": (
                    f"{len(potentials)} transaction pairing(s) matched via fuzzy description, domain semantics, "
                    "or date tolerance and require human sign-off."
                ),
                "financial_impact": round(sum(abs(float(m.get("amount_variance") or 0.0)) for m in potentials), 2),
                "statutory_reference": None,
                "source": "RECONCILIATION_ENGINE",
                "affected_records": potentials[:10],
                "remediation": "Review the potential match candidates in the reconciliation workspace and click approve or reject.",
                "risk_score": 25.0,
            })
            counter += 1

        return findings

    @classmethod
    def generate_findings_from_anomalies(
        cls,
        anomaly_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extract structured findings from statistical and ML anomaly detection outputs.
        """
        findings: list[dict[str, Any]] = []
        counter = 1
        anomalies = anomaly_result.get("anomalies", [])

        large_outliers = [t for t in anomalies if "UNUSUALLY_LARGE_AMOUNT" in t.get("anomaly_flags", [])]
        if large_outliers:
            total_amt = sum(abs(float(t.get("amount") or t.get("debit") or t.get("credit") or 0.0)) for t in large_outliers)
            findings.append({
                "finding_id": f"FND-ANOM-{counter:03d}",
                "category": "TRANSACTION_ANOMALY",
                "severity": "HIGH",
                "title": f"{len(large_outliers)} Statistical Outlier Transaction(s)",
                "description": (
                    f"{len(large_outliers)} transaction(s) totalling ₹{total_amt:,.2f} significantly exceed "
                    "normal statistical IQR expenditure and deposit bounds."
                ),
                "financial_impact": round(total_amt, 2),
                "statutory_reference": "Section 285BA (SFT) / General Audit Risk",
                "source": "ANOMALY_DETECTOR",
                "affected_records": large_outliers[:10],
                "remediation": "Verify invoices, contracts, and board approvals for all high-value outlier transactions.",
                "risk_score": 70.0,
            })
            counter += 1

        round_transfers = [t for t in anomalies if "REPEATED_ROUND_AMOUNT" in t.get("anomaly_flags", [])]
        if round_transfers:
            findings.append({
                "finding_id": f"FND-ANOM-{counter:03d}",
                "category": "TRANSACTION_ANOMALY",
                "severity": "MEDIUM",
                "title": f"Repeated Round-Figure Transfers ({len(round_transfers)} instances)",
                "description": (
                    f"{len(round_transfers)} transaction(s) feature identical round numbers. "
                    "Repeated round amounts frequently attract auditor queries regarding loan transfers or cash structuring."
                ),
                "financial_impact": round(sum(abs(float(t.get("amount") or 0.0)) for t in round_transfers), 2),
                "statutory_reference": "Section 269SS / 269T (Loan advances and repayments)",
                "source": "ANOMALY_DETECTOR",
                "affected_records": round_transfers[:10],
                "remediation": "Confirm whether round amounts represent loans, advances, or personal drawings, and ensure statutory loan agreements are documented.",
                "risk_score": 45.0,
            })
            counter += 1

        ml_outliers = [t for t in anomalies if t.get("is_ml_anomaly")]
        if ml_outliers:
            findings.append({
                "finding_id": f"FND-ANOM-{counter:03d}",
                "category": "TRANSACTION_ANOMALY",
                "severity": "HIGH",
                "title": f"Multivariate Isolation Forest ML Outliers ({len(ml_outliers)} flagged)",
                "description": (
                    f"Machine learning anomaly detector identified {len(ml_outliers)} multivariate outliers "
                    "based on anomalous combinations of transaction size, day of month, day of week, and daily frequency."
                ),
                "financial_impact": round(sum(abs(float(t.get("amount") or 0.0)) for t in ml_outliers), 2),
                "statutory_reference": None,
                "source": "ISOLATION_FOREST_ML",
                "affected_records": ml_outliers[:10],
                "remediation": "Review transaction timing and purpose for unexplained non-routine activity.",
                "risk_score": 60.0,
            })
            counter += 1

        return findings

    @classmethod
    def generate_unified_portfolio(
        cls,
        reconciliation_result: dict[str, Any] | None = None,
        anomaly_result: dict[str, Any] | None = None,
        tax_validation_findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Compile all findings across reconciliation, anomaly detection, and tax rules into
        a centralized, scored audit findings report.
        """
        all_findings: list[dict[str, Any]] = []

        if reconciliation_result:
            all_findings.extend(cls.generate_findings_from_reconciliation(reconciliation_result))

        if anomaly_result:
            all_findings.extend(cls.generate_findings_from_anomalies(anomaly_result))

        if tax_validation_findings:
            for idx, tf in enumerate(tax_validation_findings):
                raw_sev = str(tf.get("severity", "MEDIUM")).upper()
                mapped_sev = "CRITICAL" if raw_sev in ("ERROR", "CRITICAL") else ("HIGH" if raw_sev == "HIGH" else ("MEDIUM" if raw_sev == "WARNING" else "LOW"))
                all_findings.append({
                    "finding_id": f"FND-TAX-{idx+1:03d}",
                    "category": "STATUTORY_NON_COMPLIANCE",
                    "severity": mapped_sev,
                    "title": tf.get("title", "Tax Rule Finding"),
                    "description": tf.get("description", ""),
                    "financial_impact": float(tf.get("details", {}).get("disallowed_excess") or tf.get("details", {}).get("variance") or 0.0),
                    "statutory_reference": tf.get("section"),
                    "source": "TAX_RULE_ENGINE",
                    "affected_records": [tf.get("details", {})],
                    "remediation": tf.get("remediation", ""),
                    "risk_score": 85.0 if mapped_sev == "CRITICAL" else (65.0 if mapped_sev == "HIGH" else (40.0 if mapped_sev == "MEDIUM" else 20.0)),
                })

        # Summary statistics
        total_impact = sum(f.get("financial_impact", 0.0) for f in all_findings)
        critical_count = sum(1 for f in all_findings if f["severity"] == "CRITICAL")
        high_count = sum(1 for f in all_findings if f["severity"] == "HIGH")
        medium_count = sum(1 for f in all_findings if f["severity"] == "MEDIUM")
        low_count = sum(1 for f in all_findings if f["severity"] in ("LOW", "INFO"))

        # Overall portfolio risk score
        if all_findings:
            avg_risk = round(sum(f.get("risk_score", 0.0) for f in all_findings) / len(all_findings), 1)
        else:
            avg_risk = 0.0

        return {
            "summary": {
                "total_findings": len(all_findings),
                "total_financial_impact": round(total_impact, 2),
                "critical_findings_count": critical_count,
                "high_findings_count": high_count,
                "medium_findings_count": medium_count,
                "low_findings_count": low_count,
                "average_risk_score": avg_risk,
                "overall_audit_status": "ACTION_REQUIRED" if (critical_count + high_count > 0) else ("ATTENTION_RECOMMENDED" if medium_count > 0 else "CLEAN"),
            },
            "findings": all_findings,
        }

